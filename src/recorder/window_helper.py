"""
Windows 窗口助手

提供 Windows 窗口查找和信息获取功能
"""

import ctypes
from ctypes import wintypes
from typing import Optional, List, Tuple
import re
import logging


class WindowHelper:
    """Windows 窗口助手

    职责：
    1. 查找窗口句柄
    2. 获取窗口信息
    3. 验证窗口状态
    """

    def __init__(self, logger: logging.Logger):
        """初始化助手

        Args:
            logger: 日志记录器
        """
        self.logger = logger
        self._setup_winapi()

    def _setup_winapi(self) -> None:
        """配置 Windows API"""
        try:
            self.user32 = ctypes.windll.user32

            # 配置 FindWindowW
            self.user32.FindWindowW.argtypes = [
                wintypes.LPCWSTR,  # 窗口类名
                wintypes.LPCWSTR   # 窗口标题
            ]
            self.user32.FindWindowW.restype = wintypes.HWND

            # 配置 GetWindowTextW
            self.user32.GetWindowTextW.argtypes = [
                wintypes.HWND,     # 窗口句柄
                wintypes.LPWSTR,   # 输出缓冲区
                wintypes.INT       # 缓冲区大小
            ]
            self.user32.GetWindowTextW.restype = wintypes.INT

            # 配置 GetWindowRect
            self.user32.GetWindowRect.argtypes = [
                wintypes.HWND,                          # 窗口句柄
                ctypes.POINTER(ctypes.c_long * 4)       # 输出矩形
            ]
            self.user32.GetWindowRect.restype = wintypes.BOOL

            # 配置 IsWindowVisible
            self.user32.IsWindowVisible.argtypes = [wintypes.HWND]
            self.user32.IsWindowVisible.restype = wintypes.BOOL

            # 配置 IsIconic（检查是否最小化）
            self.user32.IsIconic.argtypes = [wintypes.HWND]
            self.user32.IsIconic.restype = wintypes.BOOL

            # 配置 EnumWindows
            self.WNDENUMPROC = ctypes.WINFUNCTYPE(
                wintypes.BOOL,
                wintypes.HWND,
                wintypes.LPARAM
            )
            self.user32.EnumWindows.argtypes = [
                self.WNDENUMPROC,
                wintypes.LPARAM
            ]
            self.user32.EnumWindows.restype = wintypes.BOOL

            self.logger.debug("Windows API 配置成功")

        except Exception as e:
            self.logger.error(f"Windows API 配置失败: {e}")
            raise

    def find_window_by_title(
        self,
        title: str,
        exact_match: bool = True,
        case_sensitive: bool = False
    ) -> Optional[int]:
        """根据标题查找窗口句柄

        Args:
            title: 窗口标题
            exact_match: 是否精确匹配（False = 子串匹配）
            case_sensitive: 是否区分大小写

        Returns:
            Optional[int]: 窗口句柄，找不到返回 None
        """
        self.logger.info(f"查找窗口: '{title}' (精确={exact_match})")

        if exact_match:
            # 精确匹配
            hwnd = self.user32.FindWindowW(None, title)
            if hwnd:
                self.logger.info(f"找到窗口: HWND={hwnd}")
                return hwnd
        else:
            # 枚举所有窗口进行模糊匹配
            hwnd = self._enum_windows(title, case_sensitive)
            if hwnd:
                self.logger.info(f"找到窗口: HWND={hwnd}")
                return hwnd

        self.logger.warning(f"未找到窗口: '{title}'")
        return None

    def find_window_by_pattern(self, pattern: str) -> Optional[int]:
        """根据正则表达式查找窗口

        Args:
            pattern: 正则表达式

        Returns:
            Optional[int]: 窗口句柄
        """
        self.logger.info(f"使用正则查找窗口: '{pattern}'")

        try:
            regex = re.compile(pattern)
        except re.error as e:
            self.logger.error(f"无效的正则表达式: {e}")
            return None

        hwnd = self._enum_windows_regex(regex)

        if hwnd:
            self.logger.info(f"找到窗口: HWND={hwnd}")
            return hwnd

        self.logger.warning(f"未找到匹配窗口: '{pattern}'")
        return None

    def get_window_title(self, hwnd: int) -> str:
        """获取窗口标题

        Args:
            hwnd: 窗口句柄

        Returns:
            str: 窗口标题
        """
        buffer_size = 512
        buffer = ctypes.create_unicode_buffer(buffer_size)
        self.user32.GetWindowTextW(hwnd, buffer, buffer_size)
        return buffer.value

    def get_window_rect(self, hwnd: int) -> Tuple[int, int, int, int]:
        """获取窗口矩形区域

        Args:
            hwnd: 窗口句柄

        Returns:
            tuple: (left, top, right, bottom)
        """
        rect = ctypes.c_long * 4
        rect_buffer = rect()
        self.user32.GetWindowRect(hwnd, rect_buffer)
        return (rect_buffer[0], rect_buffer[1],
                rect_buffer[2], rect_buffer[3])

    def get_window_size(self, hwnd: int) -> Tuple[int, int]:
        """获取窗口大小

        Args:
            hwnd: 窗口句柄

        Returns:
            tuple: (width, height)
        """
        left, top, right, bottom = self.get_window_rect(hwnd)
        return (right - left, bottom - top)

    def is_window_visible(self, hwnd: int) -> bool:
        """检查窗口是否可见

        Args:
            hwnd: 窗口句柄

        Returns:
            bool: 是否可见
        """
        return bool(self.user32.IsWindowVisible(hwnd))

    def is_minimized(self, hwnd: int) -> bool:
        """检查窗口是否最小化

        Args:
            hwnd: 窗口句柄

        Returns:
            bool: 是否最小化
        """
        return bool(self.user32.IsIconic(hwnd))

    def validate_window(self, hwnd: int) -> bool:
        """验证窗口是否可用于录制

        Args:
            hwnd: 窗口句柄

        Returns:
            bool: 是否可用
        """
        if not hwnd:
            return False

        if not self.is_window_visible(hwnd):
            self.logger.warning(f"窗口 {hwnd} 不可见")
            return False

        if self.is_minimized(hwnd):
            self.logger.warning(f"窗口 {hwnd} 已最小化")
            return False

        return True

    def list_all_windows(self) -> List[Tuple[int, str]]:
        """列出所有窗口（用于调试）

        Returns:
            list: [(hwnd, title), ...]
        """
        windows = []

        def enum_callback(hwnd, lparam):
            if self.is_window_visible(hwnd):
                title = self.get_window_title(hwnd)
                if title:
                    windows.append((hwnd, title))
            return True

        callback = self.WNDENUMPROC(enum_callback)
        self.user32.EnumWindows(callback, 0)

        return windows

    def _enum_windows(
        self,
        target_title: str,
        case_sensitive: bool
    ) -> Optional[int]:
        """枚举窗口查找匹配项

        Args:
            target_title: 目标窗口标题
            case_sensitive: 是否区分大小写

        Returns:
            Optional[int]: 窗口句柄
        """
        found_hwnd = [None]

        def enum_callback(hwnd, lparam):
            """枚举回调"""
            title = self.get_window_title(hwnd)
            if not title:
                return True  # 继续枚举

            # 匹配逻辑
            if case_sensitive:
                match = target_title in title
            else:
                match = target_title.lower() in title.lower()

            if match:
                # 找到匹配，存储句柄并停止枚举
                found_hwnd[0] = hwnd
                return False  # 停止枚举

            return True  # 继续枚举

        callback = self.WNDENUMPROC(enum_callback)
        self.user32.EnumWindows(callback, 0)

        return found_hwnd[0]

    def _enum_windows_regex(self, pattern: re.Pattern) -> Optional[int]:
        """使用正则表达式枚举窗口

        Args:
            pattern: 编译后的正则表达式

        Returns:
            Optional[int]: 窗口句柄
        """
        found_hwnd = [None]

        def enum_callback(hwnd, lparam):
            title = self.get_window_title(hwnd)
            if not title:
                return True

            if pattern.search(title):
                found_hwnd[0] = hwnd
                return False

            return True

        callback = self.WNDENUMPROC(enum_callback)
        self.user32.EnumWindows(callback, 0)

        return found_hwnd[0]
