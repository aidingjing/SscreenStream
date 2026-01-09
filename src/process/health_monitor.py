"""
通用健康监控器

监控子进程的健康状态，实现崩溃检测和重启策略
"""

from datetime import datetime, timedelta
from typing import List
import logging


class HealthMonitor:
    """通用健康监控器

    职责：
    1. 监控任何进程的健康状态
    2. 记录崩溃次数和时间
    3. 判断是否应该重启
    """

    def __init__(self, threshold: int, window: int, logger: logging.Logger):
        """初始化监控器

        Args:
            threshold: 崩溃阈值（次）
            window: 时间窗口（秒）
            logger: 日志记录器
        """
        self.threshold = threshold
        self.window = window
        self.logger = logger
        self.crash_history: List[datetime] = []

        self.logger.debug(
            f"健康监控器已初始化: 阈值={threshold}次, 时间窗口={window}秒"
        )

    def record_crash(self) -> None:
        """记录一次崩溃"""
        now = datetime.now()
        self.crash_history.append(now)

        # 清理超出时间窗口的记录
        self._cleanup_old_crashes()

        crash_count = len(self.crash_history)
        self.logger.warning(
            f"记录进程崩溃，时间窗口内崩溃次数: {crash_count}/{self.threshold}"
        )

    def should_restart(self) -> bool:
        """判断是否应该重启

        Returns:
            bool: True 表示应该重启，False 表示应该停止服务
        """
        if not self.is_threshold_exceeded():
            self.logger.info("崩溃次数未超阈值，可以重启")
            return True

        self.logger.error(
            f"崩溃次数超阈值 ({len(self.crash_history)}/{self.threshold} "
            f"在 {self.window} 秒内)，停止服务"
        )
        return False

    def is_threshold_exceeded(self) -> bool:
        """检查是否超过崩溃阈值

        Returns:
            bool: True 表示超过阈值，应该停止服务
        """
        self._cleanup_old_crashes()
        return len(self.crash_history) >= self.threshold

    def reset(self) -> None:
        """重置监控状态（进程稳定运行后调用）"""
        if self.crash_history:
            self.logger.info(f"重置健康监控器，清除 {len(self.crash_history)} 条崩溃记录")
            self.crash_history.clear()

    def get_crash_count(self) -> int:
        """获取当前时间窗口内的崩溃次数

        Returns:
            int: 崩溃次数
        """
        self._cleanup_old_crashes()
        return len(self.crash_history)

    def _cleanup_old_crashes(self) -> None:
        """清理超出时间窗口的崩溃记录"""
        if not self.crash_history:
            return

        cutoff = datetime.now() - timedelta(seconds=self.window)
        original_count = len(self.crash_history)

        # 只保留时间窗口内的记录
        self.crash_history = [
            crash_time for crash_time in self.crash_history
            if crash_time > cutoff
        ]

        cleaned_count = original_count - len(self.crash_history)
        if cleaned_count > 0:
            self.logger.debug(f"清理 {cleaned_count} 条过期崩溃记录")
