"""
通用子进程管理器

管理任意子进程的生命周期，支持策略注入
"""

import subprocess
import threading
from typing import Callable, List, Optional
from datetime import datetime

from src.exceptions import ProcessManagerError
import logging


class ProcessState:
    """进程状态对象"""

    def __init__(
        self,
        is_running: bool,
        pid: Optional[int],
        start_time: Optional[datetime],
        client_count: int = 0
    ):
        self.is_running = is_running
        self.pid = pid
        self.start_time = start_time
        self.client_count = client_count


class ProcessManager:
    """通用子进程管理器

    职责：
    1. 管理任意子进程的生命周期
    2. 不依赖具体的命令构建方式
    3. 通过依赖注入接收命令构建器
    """

    def __init__(
        self,
        cmd_builder: Callable[[], List[str]],
        logger: logging.Logger
    ):
        """初始化进程管理器

        Args:
            cmd_builder: 命令构建函数（策略注入）
                         返回命令行参数列表，如 ["ffmpeg.exe", ...]
            logger: 日志记录器
        """
        self.cmd_builder = cmd_builder
        self.logger = logger
        self.process: Optional[subprocess.Popen] = None
        self.start_time: Optional[datetime] = None

        # 读取线程（用于异步读取 stdout）
        self._read_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> ProcessState:
        """启动子进程

        Returns:
            ProcessState: 进程状态

        Raises:
            ProcessManagerError: 启动失败
        """
        if self.is_running():
            self.logger.warning("进程已在运行中，跳过启动")
            return self.get_state()

        # 获取命令
        cmd = self.cmd_builder()
        self.logger.info(f"启动进程: {' '.join(cmd)}")

        try:
            # 启动进程
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0  # 无缓冲，实时输出
            )
            self.start_time = datetime.now()

            self.logger.info(
                f"进程已启动，PID: {self.process.pid}"
            )

            return ProcessState(
                is_running=True,
                pid=self.process.pid,
                start_time=self.start_time,
                client_count=0
            )

        except Exception as e:
            self.logger.error(f"进程启动失败: {e}")
            raise ProcessManagerError(f"启动进程失败: {e}")

    def stop(self, timeout: int = 5) -> bool:
        """停止子进程

        Args:
            timeout: 等待超时时间（秒）

        Returns:
            bool: 是否成功停止
        """
        if not self.process:
            self.logger.warning("进程未运行，无需停止")
            return True

        pid = self.process.pid
        self.logger.info(f"正在停止进程 (PID: {pid})...")

        try:
            # 1. 尝试优雅终止（发送 SIGTERM）
            self.process.terminate()

            try:
                # 等待进程退出
                self.process.wait(timeout=timeout)
                self.logger.info(f"进程已优雅终止 (PID: {pid})")
                return True

            except subprocess.TimeoutExpired:
                # 2. 超时则强制终止（发送 SIGKILL）
                self.logger.warning(
                    f"进程未在 {timeout} 秒内退出，强制终止..."
                )
                self.process.kill()

                # 等待进程退出
                self.process.wait(timeout=2)
                self.logger.info(f"进程已强制终止 (PID: {pid})")
                return True

        except Exception as e:
            self.logger.error(f"停止进程失败: {e}")
            return False

        finally:
            # 清理资源
            self.process = None
            self.start_time = None

    def get_state(self) -> ProcessState:
        """获取进程状态

        Returns:
            ProcessState: 进程状态
        """
        if not self.process:
            return ProcessState(
                is_running=False,
                pid=None,
                start_time=None,
                client_count=0
            )

        # 检查进程是否还在运行
        is_running = self.process.poll() is None

        return ProcessState(
            is_running=is_running,
            pid=self.process.pid if is_running else None,
            start_time=self.start_time,
            client_count=0
        )

    def is_running(self) -> bool:
        """检查进程是否运行

        Returns:
            bool: 是否运行中
        """
        if not self.process:
            return False
        return self.process.poll() is None

    def read_output(self, size: int = 4096) -> bytes:
        """读取进程输出

        Args:
            size: 读取字节数

        Returns:
            bytes: 输出数据，如果进程未运行返回空字节
        """
        if not self.process or not self.process.stdout:
            return b''

        try:
            # 使用非阻塞读取
            import os

            # 检查文件描述符是否有数据可读
            fd = self.process.stdout.fileno()

            # 尝试非阻塞读取
            try:
                # 使用 os.read 进行非阻塞读取
                data = os.read(fd, size)
                return data if data else b''
            except BlockingIOError:
                # 没有数据可读
                return b''
            except OSError:
                # Windows 管道不支持非阻塞，使用普通读取
                # 先检查是否有数据（使用 peek）
                if hasattr(self.process.stdout, 'peek'):
                    available = self.process.stdout.peek(1)
                    if not available:
                        return b''

                # 使用 read1 读取（最多读取 size 字节，不会阻塞等待填满缓冲区）
                data = self.process.stdout.read1(size)
                return data if data else b''

        except Exception as e:
            self.logger.error(f"读取进程输出失败: {e}")
            return b''

    def read_stderr(self) -> str:
        """读取进程错误输出

        Returns:
            str: 错误输出
        """
        if not self.process or not self.process.stderr:
            return ""

        try:
            # 非阻塞读取错误输出
            import os

            fd = self.process.stderr.fileno()

            try:
                # 使用 os.read 进行非阻塞读取
                data = os.read(fd, 4096)
                return data.decode('utf-8', errors='ignore') if data else ""
            except BlockingIOError:
                # 没有数据可读
                return ""
            except OSError:
                # Windows 管道不支持非阻塞，使用普通读取
                data = self.process.stderr.read(4096)
                return data.decode('utf-8', errors='ignore') if data else ""

        except Exception as e:
            self.logger.error(f"读取进程错误输出失败: {e}")
            return ""

    def get_return_code(self) -> Optional[int]:
        """获取进程退出码

        Returns:
            Optional[int]: 退出码，如果进程仍在运行返回 None
        """
        if not self.process:
            return None
        return self.process.poll()
