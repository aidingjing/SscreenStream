"""
视频流转发器

从录制器读取视频数据并转发给所有客户端
"""

import asyncio
import logging
from typing import Optional

from src.recorder.base_recorder import BaseRecorder
from src.streamer.client_manager import ClientManager
from src.streamer.gop_buffer import GOPBuffer


class StreamForwarder:
    """视频流转发器

    职责：
    1. 从 FFmpeg 进程读取视频数据
    2. 将数据分发给所有连接的客户端
    3. 处理数据分块和缓冲
    """

    def __init__(
        self,
        recorder: BaseRecorder,
        client_manager: ClientManager,
        logger: logging.Logger
    ):
        """初始化转发器

        Args:
            recorder: 录制器对象
            client_manager: 客户端管理器
            logger: 日志记录器
        """
        self.recorder = recorder
        self.client_manager = client_manager
        self.logger = logger

        # GOP 缓冲器（缓存最近 1-2 个 GOP 的数据）
        self.gop_buffer = GOPBuffer(logger, max_gop_count=2)

        # 转发任务
        self._forwarding_task: Optional[asyncio.Task] = None
        self._is_running = False

        # 统计信息
        self._total_bytes = 0
        self._packet_count = 0

    async def start_forwarding(self) -> None:
        """启动转发循环"""
        if self._is_running:
            self.logger.warning("转发器已在运行中")
            return

        self._is_running = True
        self._total_bytes = 0
        self._packet_count = 0

        # 注意：不再重置 GOP 缓冲器，因为可能在超时期间仍需要为新客户端提供数据
        # self.gop_buffer.reset()

        self.logger.info("启动流转发器...")

        # 创建转发任务
        self._forwarding_task = asyncio.create_task(
            self._read_and_forward()
        )

    async def stop_forwarding(self, reset_gop_buffer: bool = False) -> None:
        """停止转发循环"""
        if not self._is_running:
            return

        self.logger.info("正在停止流转发器...")
        self._is_running = False

        # 取消转发任务
        if self._forwarding_task and not self._forwarding_task.done():
            self._forwarding_task.cancel()

            try:
                await self._forwarding_task
            except asyncio.CancelledError:
                pass

        # 根据参数决定是否重置GOP缓冲区
        if reset_gop_buffer:
            self.gop_buffer.reset()
            self.logger.info("GOP 缓冲区已重置")

        self.logger.info(
            f"流转发器已停止，总字节数: {self._total_bytes}, "
            f"总包数: {self._packet_count}"
        )

    async def _read_and_forward(self) -> None:
        """读取 FFmpeg 输出并转发给客户端"""
        try:
            while self._is_running:
                # 读取录制器输出（始终读取，即使没有客户端也需要填充 GOP 缓冲）
                try:
                    data = await asyncio.to_thread(
                        self.recorder.read_output,
                        8192  # 读取 8KB 数据块
                    )
                except Exception as e:
                    self.logger.error(f"读取录制器输出失败: {e}")
                    await asyncio.sleep(0.1)
                    continue

                # 如果没有数据，等待一小段时间
                if not data:
                    await asyncio.sleep(0.01)
                    continue

                # 处理 GOP 缓存
                _, stream_data = self.gop_buffer.process_data(data)

                # 更新统计
                self._total_bytes += len(data)
                self._packet_count += 1

                # 只有在有客户端时才转发数据
                if not self.client_manager.is_empty():
                    await self.client_manager.broadcast(stream_data)
                else:
                    # 没有客户端时，继续处理数据以维护 GOP 缓冲
                    # 这样在超时期间，GOP 缓冲区仍然可用
                    pass

                # 定期打印统计（每 1000 个包）
                if self._packet_count % 1000 == 0:
                    stats = self.gop_buffer.get_statistics()
                    self.logger.debug(
                        f"转发统计: 包数={self._packet_count}, "
                        f"字节数={self._total_bytes}, "
                        f"客户端数={self.client_manager.get_client_count()}, "
                        f"GOP就绪={stats['ready']}, "
                        f"GOP数={stats['gop_count']}"
                    )

        except asyncio.CancelledError:
            self.logger.debug("转发任务被取消")
            raise

        except Exception as e:
            self.logger.error(f"转发循环异常: {e}", exc_info=True)

    async def send_initial_data_to_client(self, client_id: str) -> bool:
        """向指定客户端发送初始化数据（FLV Header + Metadata + GOP）

        Args:
            client_id: 客户端 ID

        Returns:
            bool: 发送是否成功
        """
        if not self.gop_buffer.is_ready():
            self.logger.warning(
                f"GOP 缓冲未就绪，无法发送给客户端 {client_id}"
            )
            return False

        initial_data = self.gop_buffer.get_initial_data()
        if not initial_data:
            return False

        try:
            conn_info = self.client_manager.get_client(client_id)
            if not conn_info:
                self.logger.warning(f"客户端 {client_id} 不存在")
                return False

            await conn_info.websocket.send(initial_data)
            self.logger.info(
                f"✅ 初始化数据已发送给客户端 {client_id} "
                f"({len(initial_data)} bytes)"
            )
            return True

        except Exception as e:
            self.logger.error(
                f"发送初始化数据到客户端 {client_id} 失败: {e}"
            )
            return False

    async def _forward_to_client(
        self,
        client_id: str,
        data: bytes
    ) -> bool:
        """转发数据到单个客户端（已废弃，改用 broadcast）

        Args:
            client_id: 客户端 ID
            data: 要发送的数据

        Returns:
            bool: 发送是否成功
        """
        # 此方法已废弃，使用 ClientManager.broadcast 代替
        return True

    def get_statistics(self) -> dict:
        """获取转发统计信息

        Returns:
            dict: 统计信息
        """
        gop_stats = self.gop_buffer.get_statistics()
        return {
            "total_bytes": self._total_bytes,
            "packet_count": self._packet_count,
            "is_running": self._is_running,
            "gop_ready": gop_stats['ready'],
            "gop_count": gop_stats['gop_count'],
            "header_size": gop_stats['header_size'],
            "metadata_size": gop_stats['metadata_size']
        }