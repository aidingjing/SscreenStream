"""
录制器抽象接口

定义所有录制器必须实现的通用接口
"""

from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime
from dataclasses import dataclass


@dataclass
class RecorderState:
    """录制器状态（通用）"""
    is_running: bool
    start_time: Optional[datetime]
    client_count: int


class BaseRecorder(ABC):
    """录制器抽象接口

    所有录制器实现必须继承此类，保证接口一致性

    实现类示例：
    - FFmpegRecorder: FFmpeg 录制器
    - OBRecorder: OBS 录制器（未来扩展）
    - DirectXRecorder: DirectX 录制器（未来扩展）
    """

    @abstractmethod
    def start(self) -> RecorderState:
        """启动录制

        Returns:
            RecorderState: 录制器状态

        Raises:
            RecorderStartupError: 启动失败
        """
        pass

    @abstractmethod
    def stop(self, timeout: int = 5) -> bool:
        """停止录制

        Args:
            timeout: 等待超时时间（秒）

        Returns:
            bool: 是否成功停止
        """
        pass

    @abstractmethod
    def get_state(self) -> RecorderState:
        """获取当前状态

        Returns:
            RecorderState: 录制器状态
        """
        pass

    @abstractmethod
    def is_running(self) -> bool:
        """检查是否正在录制

        Returns:
            bool: 是否运行中
        """
        pass

    @abstractmethod
    def read_output(self, size: int = -1) -> bytes:
        """读取录制输出数据

        Args:
            size: 读取字节数

        Returns:
            bytes: 视频数据
        """
        pass
