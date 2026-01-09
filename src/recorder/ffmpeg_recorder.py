"""
FFmpeg 录制器实现

实现 BaseRecorder 接口，组合通用模块
"""

from typing import Optional
import logging

from src.recorder.base_recorder import BaseRecorder, RecorderState
from src.process.process_manager import ProcessManager, ProcessState
from src.process.health_monitor import HealthMonitor
from src.recorder.ffmpeg_builder import FFmpegCommandBuilder
from src.config.config_parser import ConfigData
from src.exceptions import RecorderStartupError


class FFmpegRecorder(BaseRecorder):
    """FFmpeg 录制器实现

    职责：
    1. 实现 BaseRecorder 接口
    2. 组合 ProcessManager 和 FFmpegCommandBuilder
    3. 向外暴露统一的录制器接口

    设计模式：
    - 策略模式：通过 FFmpegCommandBuilder 注入命令构建策略
    - 组合模式：组合 ProcessManager 和 HealthMonitor
    """

    def __init__(self, config: ConfigData, logger: logging.Logger):
        """初始化 FFmpeg 录制器

        Args:
            config: 配置数据对象
            logger: 日志记录器
        """
        self.config = config
        self.logger = logger

        # 创建 FFmpeg 命令构建器
        self.command_builder = FFmpegCommandBuilder(config)

        # 创建进程管理器（注入命令构建策略）
        self.process_manager = ProcessManager(
            cmd_builder=self.command_builder.build,
            logger=logger
        )

        # 创建健康监控器
        self.health_monitor = HealthMonitor(
            threshold=config.crash_threshold,
            window=config.crash_window,
            logger=logger
        )

        self.logger.info("FFmpeg 录制器已初始化")

    def start(self) -> RecorderState:
        """启动 FFmpeg 录制

        Returns:
            RecorderState: 录制器状态

        Raises:
            RecorderStartupError: 启动失败
        """
        try:
            self.logger.info("正在启动 FFmpeg 录制...")

            # 启动 FFmpeg 进程
            process_state = self.process_manager.start()

            self.logger.info(
                f"FFmpeg 录制已启动，PID: {process_state.pid}"
            )

            # 返回录制器状态
            return RecorderState(
                is_running=True,
                start_time=process_state.start_time,
                client_count=0
            )

        except Exception as e:
            self.logger.error(f"FFmpeg 启动失败: {e}")

            # 记录崩溃
            self.health_monitor.record_crash()

            raise RecorderStartupError(f"启动 FFmpeg 失败: {e}")

    def stop(self, timeout: int = 5) -> bool:
        """停止 FFmpeg 录制

        Args:
            timeout: 等待超时时间（秒）

        Returns:
            bool: 是否成功停止
        """
        self.logger.info("正在停止 FFmpeg 录制...")

        try:
            success = self.process_manager.stop(timeout)

            if success:
                self.logger.info("FFmpeg 录制已停止")
                # 重置健康监控器（进程正常停止）
                self.health_monitor.reset()
            else:
                self.logger.warning("FFmpeg 停止超时，已强制终止")

            return success

        except Exception as e:
            self.logger.error(f"停止 FFmpeg 失败: {e}")
            return False

    def get_state(self) -> RecorderState:
        """获取录制状态

        Returns:
            RecorderState: 录制器状态
        """
        process_state = self.process_manager.get_state()

        return RecorderState(
            is_running=process_state.is_running,
            start_time=process_state.start_time,
            client_count=process_state.client_count
        )

    def is_running(self) -> bool:
        """检查是否运行中

        Returns:
            bool: 是否运行中
        """
        return self.process_manager.is_running()

    def read_output(self, size: int = 4096) -> bytes:
        """读取 FFmpeg 输出

        Args:
            size: 读取字节数

        Returns:
            bytes: 视频数据
        """
        return self.process_manager.read_output(size)

    def handle_crash(self) -> bool:
        """处理崩溃

        Returns:
            bool: True 表示应该重启，False 表示应该停止
        """
        self.logger.warning("检测到 FFmpeg 进程崩溃")

        # 记录崩溃
        self.health_monitor.record_crash()

        # 判断是否应该重启
        should_restart = self.health_monitor.should_restart()

        if should_restart:
            self.logger.info("准备重启 FFmpeg...")
        else:
            self.logger.error("崩溃次数超阈值，停止服务")

        return should_restart

    def get_health_monitor(self) -> HealthMonitor:
        """获取健康监控器

        Returns:
            HealthMonitor: 健康监控器实例
        """
        return self.health_monitor
