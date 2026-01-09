"""
推流实例类

封装单个推流服务的完整生命周期，包括：
- WebSocket 服务器
- FFmpeg 录制器
- 独立的 asyncio 事件循环
- 状态监控和日志记录
"""

import asyncio
import threading
import logging
from datetime import datetime
from enum import Enum
from typing import Optional, Callable, List, Dict, Any
from dataclasses import dataclass, field

from src.config.config_parser import ConfigData
from src.recorder.ffmpeg_recorder import FFmpegRecorder
from src.streamer.ws_server import WebSocketStreamer


class InstanceStatus(Enum):
    """实例状态枚举"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class InstanceInfo:
    """实例信息数据类"""
    name: str
    status: InstanceStatus
    port: int
    path: str  # WebSocket 路由路径
    source_type: str
    client_count: int = 0
    uptime: Optional[float] = None
    error: Optional[str] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    bitrate: Optional[str] = None
    framerate: Optional[int] = None


class StreamingInstance:
    """推流实例类

    封装单个推流服务的完整生命周期
    """

    def __init__(
        self,
        name: str,
        config: ConfigData,
        port: int,
        logger: Optional[logging.Logger] = None
    ):
        """初始化推流实例

        Args:
            name: 实例名称
            config: 配置数据
            port: WebSocket 服务器端口
            logger: 日志记录器
        """
        self.name = name
        self.config = config
        self.port = port
        self.logger = logger or logging.getLogger(f"instance.{name}")

        # 实例状态
        self._status = InstanceStatus.STOPPED
        self._error_message: Optional[str] = None

        # 启动时间（用于计算运行时间）
        self._start_time: Optional[datetime] = None

        # 线程和事件循环
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stop_event = threading.Event()

        # 组件
        self.recorder: Optional[FFmpegRecorder] = None
        self.server: Optional[WebSocketStreamer] = None

        # 日志列表（用于UI显示）
        self._logs: List[str] = []
        self._max_logs = 1000  # 最多保留1000条日志

        # 状态变更回调
        self._status_callbacks: List[Callable[[InstanceStatus, InstanceStatus], None]] = []

    @property
    def status(self) -> InstanceStatus:
        """获取当前状态"""
        return self._status

    def get_info(self) -> InstanceInfo:
        """获取实例信息

        Returns:
            InstanceInfo: 实例信息
        """
        uptime = None
        if self._start_time and self._status == InstanceStatus.RUNNING:
            uptime = (datetime.now() - self._start_time).total_seconds()

        client_count = 0
        if self.server:
            client_count = self.server.client_manager.get_client_count()

        return InstanceInfo(
            name=self.name,
            status=self._status,
            port=self.port,
            path=self.config.server_path,  # 添加路径信息
            source_type=self.config.source.source.type,
            client_count=client_count,
            uptime=uptime,
            error=self._error_message,
            video_codec=self.config.video_codec,
            audio_codec=self.config.audio_codec,
            bitrate=self.config.bitrate,
            framerate=self.config.framerate
        )

    def get_log(self) -> List[str]:
        """获取日志列表

        Returns:
            List[str]: 日志列表
        """
        return self._logs.copy()

    def register_status_callback(self, callback: Callable[[InstanceStatus, InstanceStatus], None]):
        """注册状态变更回调

        Args:
            callback: 回调函数，签名为 callback(old_status, new_status)
        """
        self._status_callbacks.append(callback)

    def start(self) -> None:
        """启动实例（在新线程中运行）

        Raises:
            RuntimeError: 实例已在运行
        """
        if self._status != InstanceStatus.STOPPED:
            raise RuntimeError(f"实例未处于停止状态: {self._status}")

        self.logger.info(f"启动实例: {self.name}")

        # 设置状态为启动中
        self._set_status(InstanceStatus.STARTING)

        # 创建并启动线程
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_in_thread,
            name=f"Instance-{self.name}",
            daemon=True
        )
        self._thread.start()

    def _run_in_thread(self):
        """在线程中运行异步事件循环"""
        # 创建新的事件循环
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        # 运行启动协程
        try:
            self._loop.run_until_complete(self._start_async())
        except Exception as e:
            self.logger.error(f"实例运行异常: {e}", exc_info=True)
            self._error_message = str(e)
            self._set_status(InstanceStatus.ERROR)
        finally:
            # 清理
            self._loop.close()

    async def _start_async(self):
        """异步启动实例"""
        try:
            self._log(f"[INFO] 启动推流实例: {self.name}")

            # 创建录制器
            self._log(f"[INFO] 初始化 FFmpeg 录制器...")
            self.recorder = FFmpegRecorder(self.config, self.logger)

            # 修改配置的端口为分配的端口
            self.config.server_port = self.port

            # 创建 WebSocket 服务器
            self._log(f"[INFO] 初始化 WebSocket 服务器，端口: {self.port}")
            self.server = WebSocketStreamer(self.config, self.recorder, self.logger)

            # 启动服务器
            await self.server.start()

            # 记录启动时间
            self._start_time = datetime.now()

            # 设置状态为运行中
            self._set_status(InstanceStatus.RUNNING)
            self._log(f"[INFO] 实例启动成功: {self.name}")

            # 等待停止信号
            while not self._stop_event.is_set():
                await asyncio.sleep(0.5)

        except Exception as e:
            self.logger.error(f"启动失败: {e}", exc_info=True)
            self._error_message = str(e)
            self._set_status(InstanceStatus.ERROR)
            self._log(f"[ERROR] 启动失败: {e}")

    def stop(self, timeout: float = 5.0) -> None:
        """停止实例

        Args:
            timeout: 等待停止的超时时间（秒）
        """
        if self._status == InstanceStatus.STOPPED:
            return

        self.logger.info(f"停止实例: {self.name}")
        self._set_status(InstanceStatus.STOPPING)

        # 发送停止信号
        self._stop_event.set()

        # 等待线程结束
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

            # 如果超时，强制停止
            if self._thread.is_alive():
                self.logger.warning(f"实例停止超时，强制停止: {self.name}")

        # 清理资源
        if self._loop and not self._loop.is_closed():
            # 如果事件循环还在运行，调度停止协程
            try:
                asyncio.run_coroutine_threadsafe(self._stop_async(), self._loop)
            except Exception as e:
                self.logger.error(f"停止协程失败: {e}")

        # 设置状态为已停止
        self._set_status(InstanceStatus.STOPPED)
        self._log(f"[INFO] 实例已停止: {self.name}")

    async def _stop_async(self):
        """异步停止实例"""
        try:
            if self.server:
                await self.server.stop()
            if self.recorder:
                self.recorder.stop()
        except Exception as e:
            self.logger.error(f"停止异常: {e}")

    def restart(self) -> None:
        """重启实例"""
        self.logger.info(f"重启实例: {self.name}")

        # 停止
        self.stop()

        # 等待停止完成
        if self._thread:
            self._thread.join(timeout=5.0)

        # 启动
        self.start()

    def _set_status(self, new_status: InstanceStatus):
        """设置状态并通知回调

        Args:
            new_status: 新状态
        """
        old_status = self._status
        self._status = new_status

        # 通知回调
        for callback in self._status_callbacks:
            try:
                callback(old_status, new_status)
            except Exception as e:
                self.logger.error(f"状态回调失败: {e}")

    def _log(self, message: str):
        """记录日志

        Args:
            message: 日志消息
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] {message}"

        # 添加到日志列表
        self._logs.append(log_line)

        # 限制日志数量
        if len(self._logs) > self._max_logs:
            self._logs = self._logs[-self._max_logs:]

        # 记录到 logger
        self.logger.info(message)
