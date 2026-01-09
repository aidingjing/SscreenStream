"""
Windows 托盘应用

提供 Windows 系统托盘图标和右键菜单功能
"""

import logging
import threading
from typing import Optional, Callable
from pathlib import Path

try:
    import pystray
    from PIL import Image, ImageDraw
    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False

from src.config.config_manager import ConfigManager
from src.instance.instance_manager import InstanceManager


class TrayApp:
    """Windows 托盘应用

    提供系统托盘图标和右键菜单功能
    """

    def __init__(
        self,
        config_manager: ConfigManager,
        instance_manager: InstanceManager,
        logger: Optional[logging.Logger] = None
    ):
        """初始化托盘应用

        Args:
            config_manager: 配置管理器
            instance_manager: 实例管理器
            logger: 日志记录器
        """
        if not PYSTRAY_AVAILABLE:
            raise RuntimeError("pystray 库未安装，请运行: pip install pystray")

        self.config_manager = config_manager
        self.instance_manager = instance_manager
        self.logger = logger or logging.getLogger(__name__)

        # 托盘图标
        self.icon: Optional[pystray.Icon] = None

        # 主窗口
        self.main_window = None

        # 运行状态
        self._running = False

        self.logger.info("托盘应用初始化完成")

    def create_icon(self) -> pystray.Icon:
        """创建托盘图标

        Returns:
            pystray.Icon: 托盘图标对象
        """
        # 创建图标图片
        icon_image = self._create_icon_image()

        # 创建菜单
        menu = pystray.Menu(
            pystray.MenuItem("显示主界面", self._on_show_main_window),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("添加配置...", self._on_add_config),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("启动所有实例", self._on_start_all),
            pystray.MenuItem("停止所有实例", self._on_stop_all),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("打开配置文件夹", self._on_open_config_folder),
            pystray.MenuItem("退出", self._on_exit)
        )

        # 创建图标
        icon = pystray.Icon(
            "Screen Streamer",
            icon_image,
            "Screen Streamer - 0 instances running",
            menu
        )

        return icon

    def _create_icon_image(self, size: int = 64) -> Image.Image:
        """创建图标图片

        Args:
            size: 图标大小

        Returns:
            Image.Image: 图标图片
        """
        # 创建一个简单的绿色圆形图标
        image = Image.new('RGB', (size, size), color=(255, 255, 255))
        draw = ImageDraw.Draw(image)

        # 绘制圆形
        margin = 4
        draw.ellipse(
            [(margin, margin), (size - margin, size - margin)],
            fill=(33, 150, 243),  # Material Blue
            outline=(255, 255, 255),
            width=2
        )

        return image

    def update_tooltip(self) -> None:
        """更新托盘图标提示"""
        if not self.icon:
            return

        statuses = self.instance_manager.get_all_statuses()

        running = sum(1 for s in statuses.values() if s.value == "running")
        stopped = sum(1 for s in statuses.values() if s.value == "stopped")
        errors = sum(1 for s in statuses.values() if s.value == "error")

        tooltip = f"Screen Streamer - {running} running, {stopped} stopped"

        if errors > 0:
            tooltip += f", {errors} errors"

        self.icon.tooltip = tooltip

    def run(self) -> None:
        """运行托盘应用（阻塞）"""
        self.logger.info("启动托盘应用")

        # 创建图标
        self.icon = self.create_icon()

        # 设置运行状态
        self._running = True

        # 运行（阻塞）
        self.icon.run()

        self._running = False
        self.logger.info("托盘应用已停止")

    def stop(self) -> None:
        """停止托盘应用"""
        self.logger.info("停止托盘应用")

        if self.icon:
            self.icon.stop()

        self._running = False

    def _on_show_main_window(self) -> None:
        """显示主窗口菜单项处理"""
        self.logger.info("显示主窗口")
        self._show_main_window()

    def _show_main_window(self) -> None:
        """显示主窗口"""
        # 如果窗口还未创建，创建窗口
        if self.main_window is None:
            try:
                from src.gui.main_window import MainWindow

                # 获取已存在的 QApplication 实例（在 main.py 主线程中创建）
                from PyQt5.QtWidgets import QApplication
                app = QApplication.instance()
                if app is None:
                    self.logger.error("QApplication 未初始化，无法显示主窗口")
                    return

                # 创建主窗口
                self.main_window = MainWindow(
                    self.config_manager,
                    self.instance_manager,
                    self.logger
                )

                self.logger.info("主窗口已创建")

            except ImportError:
                self.logger.error("PyQt5 未安装，无法显示主窗口")
                return
            except Exception as e:
                self.logger.error(f"创建主窗口失败: {e}")
                return

        # 显示窗口（强制提升到最顶层）
        if self.main_window:
            # 使用 Qt 信号槽机制，确保在主线程中执行
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(0, self.main_window.force_show)
            self.logger.info("主窗口已显示")

    def _on_add_config(self) -> None:
        """添加配置菜单项处理"""
        self.logger.info("添加配置")
        # TODO: 实现添加配置对话框

    def _on_start_all(self) -> None:
        """启动所有实例菜单项处理"""
        self.logger.info("启动所有实例")
        # TODO: 实现启动所有实例

    def _on_stop_all(self) -> None:
        """停止所有实例菜单项处理"""
        self.logger.info("停止所有实例")
        self.instance_manager.stop_all()

    def _on_open_config_folder(self) -> None:
        """打开配置文件夹菜单项处理"""
        import subprocess
        import os

        config_dir = str(self.config_manager.config_dir)

        self.logger.info(f"打开配置文件夹: {config_dir}")

        # 在 Windows 上打开文件夹
        if os.name == 'nt':
            subprocess.Popen(['explorer', config_dir])
        else:
            # Linux/Mac
            subprocess.Popen(['xdg-open', config_dir])

    def _on_exit(self) -> None:
        """退出菜单项处理"""
        self.logger.info("退出应用")

        # 停止所有实例
        self.instance_manager.stop_all()

        # 停止托盘应用
        self.stop()
