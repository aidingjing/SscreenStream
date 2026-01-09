"""
WebSocket 推流服务器

监听客户端连接，按需启动/停止录制
"""

import asyncio
import logging
from typing import Optional

import websockets
from websockets.server import WebSocketServerProtocol

from src.recorder.base_recorder import BaseRecorder
from src.streamer.client_manager import ClientManager
from src.streamer.stream_forwarder import StreamForwarder
from src.config.config_parser import ConfigData


class WebSocketStreamer:
    """WebSocket 推流服务器

    职责：
    1. 监听客户端连接
    2. 按需启动/停止 FFmpeg
    3. 协调客户端管理和流转发

    核心逻辑：
    - 程序启动时不启动 FFmpeg
    - 第一个客户端连接时启动 FFmpeg
    - 所有客户端断开后等待超时，然后关闭 FFmpeg
    """

    def __init__(
        self,
        config: ConfigData,
        recorder: BaseRecorder,
        logger: logging.Logger
    ):
        """初始化服务器

        Args:
            config: 配置数据对象
            recorder: 录制器对象（⚠️ 此时 FFmpeg 未启动）
            logger: 日志记录器
        """
        self.config = config
        self.recorder = recorder
        self.logger = logger

        # 创建客户端管理器
        self.client_manager = ClientManager(
            shutdown_timeout=config.shutdown_timeout,
            logger=logger
        )

        # 流转发器（稍后创建）
        self.stream_forwarder: Optional[StreamForwarder] = None

        # WebSocket 服务器（稍后创建）
        self.server: Optional[websockets.WebSocketServer] = None

        # 关闭定时器
        self._shutdown_task: Optional[asyncio.Task] = None
        self._shutdown_cancel_event = asyncio.Event()

        # 标记FFmpeg是否已经启动过（用来区分是否是真正的第一次连接）
        self._ffmpeg_started = False

        self.logger.info("WebSocket 推流服务器已初始化")

    async def start(self) -> None:
        """启动 WebSocket 服务器"""
        self.logger.info(
            f"正在启动 WebSocket 服务器，"
            f"监听 {self.config.host}:{self.config.server_port}..."
        )

        # 启动 WebSocket 服务器
        self.server = await websockets.serve(
            self._handle_client,
            self.config.host,
            self.config.server_port
        )

        self.logger.info(
            f"✅ WebSocket 服务器已启动，"
            f"监听 {self.config.host}:{self.config.server_port}"
        )
        self.logger.info("⚠️  FFmpeg 未启动，等待客户端连接...")

    async def stop(self) -> None:
        """停止 WebSocket 服务器"""
        self.logger.info("正在关闭 WebSocket 服务器...")

        # 取消关闭定时器
        if self._shutdown_task and not self._shutdown_task.done():
            self._shutdown_task.cancel()

        # 停止流转发
        if self.stream_forwarder:
            await self.stream_forwarder.stop_forwarding(reset_gop_buffer=True)

        # 停止 FFmpeg（如果正在运行）
        if self.recorder.is_running():
            self.logger.info("正在停止 FFmpeg 录制...")
            await asyncio.to_thread(self.recorder.stop)

        # 关闭 WebSocket 服务器
        if self.server:
            self.server.close()
            await self.server.wait_closed()

        self.logger.info("WebSocket 服务器已关闭")

    async def _handle_client(
        self,
        websocket: WebSocketServerProtocol,
        path: str = ""  # 可选参数，兼容 websockets 11.0+
    ) -> None:
        """处理客户端连接（核心逻辑）"""
        client_id = self.client_manager.generate_client_id()
        self.logger.info(f"🔗 客户端连接: {client_id}")

        # ========== 客户端连接时 ==========
        try:
            # 判断是否为第一个客户端，且FFmpeg尚未启动
            is_first_client = (self.client_manager.get_client_count() == 0 and not self._ffmpeg_started)

            if is_first_client:
                # 第一个客户端：立即添加，启动 FFmpeg，直接接收完整流
                self.logger.info("第一个客户端连接，启动 FFmpeg 并直接推流")

                # 立即添加客户端到管理器
                self.client_manager.add_client(client_id, websocket)
                self.logger.info(
                    f"当前客户端数: {self.client_manager.get_client_count()}"
                )

                # 启动 FFmpeg
                await self._start_ffmpeg_if_needed()

                # 第一个客户端直接接收实时流（包含完整 Header + Metadata）
                # 不需要发送额外的初始化数据

            else:
                # 检查FFmpeg是否正在运行（包括超时期间）
                if self.recorder.is_running():
                    # FFmpeg正在运行，即使是超时期间，这也被视为后续客户端
                    self.logger.info("后续客户端连接，等待 GOP 缓冲就绪")

                    # 等待 GOP 缓冲就绪
                    await self._wait_for_gop_ready()

                    # GOP 就绪后，添加客户端
                    self.client_manager.add_client(client_id, websocket)
                    self.logger.info(
                        f"当前客户端数: {self.client_manager.get_client_count()}"
                    )

                    # 先发送初始化数据（Header + Metadata + GOP）
                    if self.stream_forwarder:
                        success = await self.stream_forwarder.send_initial_data_to_client(client_id)
                        if success:
                            self.logger.info(f"✅ 初始化数据已发送给客户端 {client_id}")
                        else:
                            self.logger.warning(f"⚠️ 初始化数据发送失败给客户端 {client_id}")
                else:
                    # FFmpeg不在运行，这是一个新的第一个客户端
                    self.logger.info("第一个客户端连接，启动 FFmpeg 并直接推流")

                    # 立即添加客户端到管理器
                    self.client_manager.add_client(client_id, websocket)
                    self.logger.info(
                        f"当前客户端数: {self.client_manager.get_client_count()}"
                    )

                    # 启动 FFmpeg
                    await self._start_ffmpeg_if_needed()

                    # 第一个客户端直接接收实时流（包含完整 Header + Metadata）
                    # 不需要发送额外的初始化数据

            # 取消关闭定时器（如果有）
            await self._cancel_shutdown_schedule()

            # 等待客户端断开（阻塞）
            await websocket.wait_closed()

        except Exception as e:
            self.logger.error(f"客户端 {client_id} 错误: {e}")

        finally:
            # ========== 客户端断开时 ==========
            # 移除客户端
            self.client_manager.remove_client(client_id)
            self.logger.info(
                f"🔌 客户端断开: {client_id}, "
                f"剩余客户端: {self.client_manager.get_client_count()}"
            )

            # 如果没有客户端了，计划关闭 FFmpeg
            if self.client_manager.is_empty():
                await self._schedule_ffmpeg_shutdown()

    async def _start_ffmpeg_if_needed(self) -> None:
        """按需启动 FFmpeg

        仅在以下情况下启动：
        1. 有客户端连接
        2. FFmpeg 未运行
        """
        if self.recorder.is_running():
            self.logger.info("FFmpeg 已在运行中，跳过启动")
            return

        try:
            self.logger.info("🎬 启动 FFmpeg 录制...")

            # 启动 FFmpeg（在线程池中执行，避免阻塞）
            await asyncio.to_thread(self.recorder.start)

            # 标记FFmpeg已启动
            self._ffmpeg_started = True

            # 启动流转发器
            self.stream_forwarder = StreamForwarder(
                recorder=self.recorder,
                client_manager=self.client_manager,
                logger=self.logger
            )
            await self.stream_forwarder.start_forwarding()

            self.logger.info("✅ FFmpeg 已启动，开始推流")

        except Exception as e:
            self.logger.error(f"❌ FFmpeg 启动失败: {e}")
            raise

    async def _wait_for_gop_ready(self, timeout: float = 10.0) -> None:
        """等待 GOP 缓冲就绪

        Args:
            timeout: 超时时间（秒）
        """
        if not self.stream_forwarder:
            return

        start_time = asyncio.get_event_loop().time()

        while not self.stream_forwarder.gop_buffer.is_ready():
            if asyncio.get_event_loop().time() - start_time > timeout:
                self.logger.warning(
                    f"等待 GOP 缓冲超时 ({timeout}秒)，客户端可能无法播放"
                )
                return

            await asyncio.sleep(0.1)

        stats = self.stream_forwarder.gop_buffer.get_statistics()
        self.logger.info(
            f"✅ GOP 缓冲已就绪，可以接收客户端连接 "
            f"(GOP数: {stats['gop_count']}, "
            f"Header: {stats['header_size']} bytes, "
            f"Metadata: {stats['metadata_size']} bytes)"
        )

    async def _schedule_ffmpeg_shutdown(self) -> None:
        """计划关闭 FFmpeg

        最后一个客户端断开后调用，等待超时时间后关闭
        """
        timeout = self.config.shutdown_timeout
        self.logger.info(
            f"⏳ 所有客户端已断开，{timeout} 秒后将关闭 FFmpeg..."
        )

        # 创建关闭任务
        self._shutdown_task = asyncio.create_task(
            self._shutdown_after_timeout(timeout)
        )

    async def _shutdown_after_timeout(self, timeout: int) -> None:
        """等待超时后关闭 FFmpeg"""
        try:
            # 等待超时或取消事件
            await asyncio.wait_for(
                self._shutdown_cancel_event.wait(),
                timeout=timeout
            )
            # 如果被取消（有新客户端连接），不执行关闭
            self.logger.info("取消关闭计划，有新客户端连接")

        except asyncio.TimeoutError:
            # 超时，执行关闭
            self.logger.info("⏰ 超时到达，关闭 FFmpeg...")
            await self._stop_ffmpeg()

    async def _cancel_shutdown_schedule(self) -> None:
        """取消关闭计划（有新客户端连接时调用）"""
        if self._shutdown_task and not self._shutdown_task.done():
            self._shutdown_task.cancel()
            self.logger.info("已取消 FFmpeg 关闭计划")

        # 重置取消事件
        self._shutdown_cancel_event.clear()

    async def _stop_ffmpeg(self) -> None:
        """停止 FFmpeg"""
        if not self.recorder.is_running():
            return

        try:
            # 停止流转发并重置GOP缓冲区
            if self.stream_forwarder:
                await self.stream_forwarder.stop_forwarding(reset_gop_buffer=True)
                self.stream_forwarder = None

            # 停止录制（在线程池中执行）
            await asyncio.to_thread(self.recorder.stop)

            # 重置FFmpeg启动标记，以便将来的新连接被视为第一个连接
            self._ffmpeg_started = False

            self.logger.info("✅ FFmpeg 已停止，等待下次客户端连接...")

        except Exception as e:
            self.logger.error(f"❌ FFmpeg 停止失败: {e}")

    def get_status(self) -> dict:
        """获取服务器状态

        Returns:
            dict: 状态信息
        """
        return {
            "server_running": self.server is not None,
            "ffmpeg_running": self.recorder.is_running(),
            "client_count": self.client_manager.get_client_count(),
            "forwarding_running": self.stream_forwarder is not None
        }