"""
主窗口 - 多实例推流管理器

提供可视化的实例管理界面
"""

import logging
from typing import Optional
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QLabel, QStatusBar, QToolBar,
    QAction, QMessageBox, QAbstractItemView, QApplication, QDialog, QMenu, QShortcut
)
from PyQt5.QtCore import QTimer, pyqtSignal, Qt
from PyQt5.QtGui import QIcon, QKeySequence

from src.instance.instance_manager import InstanceManager
from src.instance.streaming_instance import InstanceStatus, InstanceInfo
from src.config.config_manager import ConfigManager
from src.gui.config_dialog import ConfigDialog


class MainWindow(QMainWindow):
    """主窗口

    多实例推流管理器的主界面
    """

    # 信号：窗口关闭时通知
    window_closed = pyqtSignal()

    def __init__(
        self,
        config_manager: ConfigManager,
        instance_manager: InstanceManager,
        logger: Optional[logging.Logger] = None
    ):
        """初始化主窗口

        Args:
            config_manager: 配置管理器
            instance_manager: 实例管理器
            logger: 日志记录器
        """
        super().__init__()

        self.config_manager = config_manager
        self.instance_manager = instance_manager
        self.logger = logger or logging.getLogger(__name__)

        # 窗口标志设置：只显示最小化和关闭按钮，移除最大化按钮
        self.setWindowFlags(
            Qt.Window |
            Qt.WindowMinimizeButtonHint |
            Qt.WindowCloseButtonHint
        )

        # 窗口设置
        self.setWindowTitle("Screen Streamer - 多实例推流管理器")
        self.setMinimumSize(900, 600)
        self.resize(1200, 800)

        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        main_layout = QVBoxLayout(central_widget)

        # 创建工具栏
        self._create_toolbar()

        # 创建实例列表表格
        self.table = self._create_instance_table()
        main_layout.addWidget(self.table)

        # 创建状态栏
        self._create_status_bar()

        # 状态刷新定时器
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self._refresh_status)
        self.refresh_timer.start(1000)  # 每秒刷新一次

        # 初始化数据
        self._load_instances()

        # 设置快捷键
        self._setup_shortcuts()

        self.logger.info("主窗口初始化完成")

    def _create_toolbar(self):
        """创建工具栏"""
        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # 添加配置按钮
        add_config_action = QAction("➕ 添加配置", self)
        add_config_action.setToolTip("添加新的配置文件")
        add_config_action.triggered.connect(self._on_add_config)
        toolbar.addAction(add_config_action)

        toolbar.addSeparator()

        # 全部启动按钮
        self.start_all_action = QAction("▶ 全部启动", self)
        self.start_all_action.setToolTip("启动所有已停止的实例")
        self.start_all_action.triggered.connect(self._on_start_all)
        toolbar.addAction(self.start_all_action)

        # 全部停止按钮
        self.stop_all_action = QAction("■ 全部停止", self)
        self.stop_all_action.setToolTip("停止所有运行中的实例")
        self.stop_all_action.triggered.connect(self._on_stop_all)
        toolbar.addAction(self.stop_all_action)

        toolbar.addSeparator()

        # 刷新按钮
        refresh_action = QAction("🔄 刷新", self)
        refresh_action.setToolTip("刷新实例状态")
        refresh_action.triggered.connect(self._refresh_status)
        toolbar.addAction(refresh_action)

        # 最小化到托盘按钮
        minimize_action = QAction("🔽 最小化到托盘", self)
        minimize_action.setToolTip("最小化到系统托盘")
        minimize_action.triggered.connect(self._on_minimize_to_tray)
        toolbar.addAction(minimize_action)

    def _setup_shortcuts(self):
        """设置键盘快捷键"""
        # Ctrl+N: 添加新配置
        shortcut_add = QShortcut(QKeySequence("Ctrl+N"), self)
        shortcut_add.activated.connect(self._on_add_config)

        # F5: 刷新
        shortcut_refresh = QShortcut(QKeySequence("F5"), self)
        shortcut_refresh.activated.connect(self._refresh_status)

        # Ctrl+R: 刷新
        shortcut_refresh2 = QShortcut(QKeySequence("Ctrl+R"), self)
        shortcut_refresh2.activated.connect(self._refresh_status)

        # Delete: 删除选中的实例
        shortcut_delete = QShortcut(QKeySequence("Delete"), self)
        shortcut_delete.activated.connect(self._on_delete_selected)

        # Enter: 启动选中的实例
        shortcut_start = QShortcut(QKeySequence("Return"), self)
        shortcut_start.activated.connect(self._on_start_selected)

        # Escape: 关闭对话框或最小化到托盘
        shortcut_escape = QShortcut(QKeySequence("Escape"), self)
        shortcut_escape.activated.connect(self._on_escape)

        # Ctrl+Q: 退出应用
        shortcut_quit = QShortcut(QKeySequence("Ctrl+Q"), self)
        shortcut_quit.activated.connect(self._on_quit)

    def _on_delete_selected(self):
        """删除选中的实例"""
        selected_items = self.table.selectedItems()
        if not selected_items:
            return

        row = selected_items[0].row()
        name_item = self.table.item(row, 1)
        if name_item:
            instance_name = name_item.text()
            self._on_delete_instance(instance_name)

    def _on_start_selected(self):
        """启动选中的实例"""
        selected_items = self.table.selectedItems()
        if not selected_items:
            return

        row = selected_items[0].row()
        name_item = self.table.item(row, 1)
        if name_item:
            instance_name = name_item.text()
            self._on_start_instance(instance_name)

    def _on_escape(self):
        """Escape 键处理"""
        # 如果有打开的对话框，关闭它
        # 否则最小化到托盘
        self._on_minimize_to_tray()

    def _on_quit(self):
        """退出应用"""
        # 确认对话框
        reply = QMessageBox.question(
            self,
            "确认退出",
            "确定要退出应用吗？\n\n"
            "这将停止所有运行中的实例。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # 停止所有实例
            self.instance_manager.stop_all()

            # 退出应用
            QApplication.quit()

    def _create_instance_table(self) -> QTableWidget:
        """创建实例列表表格

        Returns:
            QTableWidget: 表格控件
        """
        table = QTableWidget()

        # 设置列
        columns = [
            "#", "实例名称", "状态", "端口", "路径", "源类型",
            "客户端", "运行时间", "操作"
        ]
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(columns)

        # 设置列宽
        table.setColumnWidth(0, 50)   # #
        table.setColumnWidth(1, 150)  # 实例名称
        table.setColumnWidth(2, 100)  # 状态
        table.setColumnWidth(3, 80)   # 端口
        table.setColumnWidth(4, 120)  # 路径（新增）
        table.setColumnWidth(5, 120)  # 源类型
        table.setColumnWidth(6, 80)   # 客户端
        table.setColumnWidth(7, 100)  # 运行时间
        table.setColumnWidth(8, 150)  # 操作

        # 最后一列自动拉伸
        header = table.horizontalHeader()
        header.setStretchLastSection(True)

        # 设置选择模式
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)

        # 启用右键菜单
        table.setContextMenuPolicy(Qt.CustomContextMenu)
        table.customContextMenuRequested.connect(self._on_table_context_menu)

        return table

    def _create_status_bar(self):
        """创建状态栏"""
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)

        # 实例统计
        self.stats_label = QLabel("初始化中...")
        status_bar.addPermanentWidget(self.stats_label)

    def _load_instances(self):
        """加载实例数据"""
        # 扫描配置
        configs = self.config_manager.scan_configs()

        self.logger.info(f"找到 {len(configs)} 个配置文件")

        # 为每个配置创建实例（如果尚未创建）
        for config in configs:
            if config.is_valid and self.instance_manager.get_instance(config.name) is None:
                try:
                    self.instance_manager.create_instance(config.name)
                    self.logger.info(f"创建实例: {config.name}")
                except Exception as e:
                    self.logger.error(f"创建实例失败 {config.name}: {e}")

        # 刷新显示
        self._refresh_status()

    def _refresh_status(self):
        """刷新实例状态显示"""
        # 清空表格
        self.table.setRowCount(0)

        # 获取所有实例信息
        infos = self.instance_manager.get_all_infos()

        # 填充表格
        for row, info in enumerate(infos):
            self.table.insertRow(row)

            # 序号
            self.table.setItem(row, 0, QTableWidgetItem(str(row + 1)))

            # 实例名称
            self.table.setItem(row, 1, QTableWidgetItem(info.name))

            # 状态
            status_item = QTableWidgetItem(info.status.value)
            status_item.setText(self._get_status_icon(info.status) + " " + info.status.value)
            self.table.setItem(row, 2, status_item)

            # 端口
            self.table.setItem(row, 3, QTableWidgetItem(str(info.port)))

            # 路径（新增）
            self.table.setItem(row, 4, QTableWidgetItem(info.path))

            # 源类型
            self.table.setItem(row, 5, QTableWidgetItem(info.source_type))

            # 客户端数量
            self.table.setItem(row, 6, QTableWidgetItem(str(info.client_count)))

            # 运行时间
            uptime_str = self._format_uptime(info.uptime)
            self.table.setItem(row, 7, QTableWidgetItem(uptime_str))

            # 操作按钮
            actions_widget = self._create_actions_widget(info)
            self.table.setCellWidget(row, 8, actions_widget)

        # 更新状态栏统计
        self._update_status_bar()

        # 更新按钮状态
        self._update_button_states()

    def _get_status_icon(self, status: InstanceStatus) -> str:
        """获取状态图标

        Args:
            status: 实例状态

        Returns:
            str: 状态图标
        """
        icons = {
            InstanceStatus.RUNNING: "🟢",
            InstanceStatus.STOPPED: "⚪",
            InstanceStatus.STARTING: "🟡",
            InstanceStatus.STOPPING: "🟠",
            InstanceStatus.ERROR: "🔴"
        }
        return icons.get(status, "⚪")

    def _format_uptime(self, uptime: Optional[float]) -> str:
        """格式化运行时间

        Args:
            uptime: 运行时间（秒）

        Returns:
            str: 格式化的时间字符串
        """
        if uptime is None:
            return "-"

        hours = int(uptime // 3600)
        minutes = int((uptime % 3600) // 60)
        seconds = int(uptime % 60)

        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _create_actions_widget(self, info: InstanceInfo) -> QWidget:
        """创建操作按钮组

        Args:
            info: 实例信息

        Returns:
            QWidget: 按钮组容器
        """
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 2, 4, 2)

        if info.status == InstanceStatus.RUNNING:
            # 停止按钮
            stop_btn = QPushButton("■")
            stop_btn.setToolTip("停止实例")
            stop_btn.setFixedSize(30, 24)
            stop_btn.clicked.connect(lambda: self._on_stop_instance(info.name))
            layout.addWidget(stop_btn)

            # 重启按钮
            restart_btn = QPushButton("🔄")
            restart_btn.setToolTip("重启实例")
            restart_btn.setFixedSize(30, 24)
            restart_btn.clicked.connect(lambda: self._on_restart_instance(info.name))
            layout.addWidget(restart_btn)

        elif info.status == InstanceStatus.STOPPED:
            # 启动按钮
            start_btn = QPushButton("▶")
            start_btn.setToolTip("启动实例")
            start_btn.setFixedSize(30, 24)
            start_btn.clicked.connect(lambda: self._on_start_instance(info.name))
            layout.addWidget(start_btn)

        elif info.status == InstanceStatus.ERROR:
            # 启动按钮
            start_btn = QPushButton("▶")
            start_btn.setToolTip("重新启动实例")
            start_btn.setFixedSize(30, 24)
            start_btn.clicked.connect(lambda: self._on_start_instance(info.name))
            layout.addWidget(start_btn)

        layout.addStretch()
        return widget

    def _update_status_bar(self):
        """更新状态栏统计"""
        total = len(self.instance_manager.get_all_infos())
        running = self.instance_manager.get_running_count()
        stopped = self.instance_manager.get_stopped_count()
        errors = self.instance_manager.get_error_count()

        text = f"实例总数: {total} | 运行中: {running} | 已停止: {stopped} | 错误: {errors}"
        self.stats_label.setText(text)

    def _update_button_states(self):
        """更新按钮启用/禁用状态"""
        has_stopped = self.instance_manager.get_stopped_count() > 0
        has_running = self.instance_manager.get_running_count() > 0

        self.start_all_action.setEnabled(has_stopped)
        self.stop_all_action.setEnabled(has_running)

    # ==================== 槽函数 ====================

    def _on_add_config(self):
        """添加配置"""
        # 获取所有现有配置（用于模板选择）
        existing_configs = self.config_manager.get_all_configs()

        # 创建配置对话框
        dialog = ConfigDialog(
            config_dir=str(self.config_manager.config_dir),
            config_manager=self.config_manager,  # 新增：传递配置管理器
            existing_configs=existing_configs,  # 新增：传递现有配置列表
            parent=self,
            logger=self.logger
        )

        # 连接信号
        dialog.config_added.connect(self._on_config_added)

        # 显示对话框
        result = dialog.exec_()

        # 如果成功添加且选择了自动启动
        if result == QDialog.Accepted and dialog.get_auto_start():
            name = dialog.name_edit.text().strip()
            if name and self.instance_manager.get_instance(name):
                try:
                    self.instance_manager.start_instance(name)
                    self._refresh_status()
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"启动实例失败: {e}")

    def _on_config_added(self, name: str):
        """配置添加成功处理

        Args:
            name: 配置名称
        """
        self.logger.info(f"配置已添加: {name}")

        # 重新加载配置
        self._load_instances()

        # 刷新显示
        self._refresh_status()

    def _on_start_all(self):
        """启动所有实例"""
        stopped_count = self.instance_manager.get_stopped_count()

        reply = QMessageBox.question(
            self,
            "确认启动",
            f"确定要启动 {stopped_count} 个已停止的实例吗？",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                for info in self.instance_manager.get_all_infos():
                    if info.status == InstanceStatus.STOPPED:
                        self.instance_manager.start_instance(info.name)

                self._refresh_status()
                QMessageBox.information(self, "完成", "所有实例启动完成")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"启动失败: {e}")

    def _on_stop_all(self):
        """停止所有实例"""
        running_count = self.instance_manager.get_running_count()

        reply = QMessageBox.question(
            self,
            "确认停止",
            f"确定要停止 {running_count} 个运行中的实例吗？",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                self.instance_manager.stop_all()
                self._refresh_status()
                QMessageBox.information(self, "完成", "所有实例已停止")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"停止失败: {e}")

    def _on_start_instance(self, name: str):
        """启动指定实例

        Args:
            name: 实例名称
        """
        try:
            self.instance_manager.start_instance(name)
            self._refresh_status()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"启动实例失败: {e}")

    def _on_stop_instance(self, name: str):
        """停止指定实例

        Args:
            name: 实例名称
        """
        try:
            self.instance_manager.stop_instance(name)
            self._refresh_status()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"停止实例失败: {e}")

    def _on_restart_instance(self, name: str):
        """重启指定实例

        Args:
            name: 实例名称
        """
        try:
            self.instance_manager.restart_instance(name)
            self._refresh_status()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"重启实例失败: {e}")

    def _on_minimize_to_tray(self):
        """最小化到托盘"""
        self.hide()
        self.logger.info("窗口已最小化到托盘")

    def _on_table_context_menu(self, pos):
        """表格右键菜单

        Args:
            pos: 鼠标位置
        """
        # 获取点击的行
        item = self.table.itemAt(pos)
        if not item:
            return

        row = item.row()
        name_item = self.table.item(row, 1)  # 实例名称列
        if not name_item:
            return

        instance_name = name_item.text()
        info = self.instance_manager.get_instance_info(instance_name)

        if not info:
            return

        # 创建右键菜单
        menu = QMenu(self)

        # 启动实例
        if info.status == InstanceStatus.STOPPED:
            start_action = QAction("▶ 启动实例", self)
            start_action.triggered.connect(lambda: self._on_start_instance(instance_name))
            menu.addAction(start_action)

        # 停止实例
        if info.status == InstanceStatus.RUNNING:
            stop_action = QAction("■ 停止实例", self)
            stop_action.triggered.connect(lambda: self._on_stop_instance(instance_name))
            menu.addAction(stop_action)

            # 重启实例
            restart_action = QAction("🔄 重启实例", self)
            restart_action.triggered.connect(lambda: self._on_restart_instance(instance_name))
            menu.addAction(restart_action)

        # 错误状态可以重新启动
        if info.status == InstanceStatus.ERROR:
            start_action = QAction("▶ 重新启动实例", self)
            start_action.triggered.connect(lambda: self._on_start_instance(instance_name))
            menu.addAction(start_action)

        # 添加分隔线
        menu.addSeparator()

        # 查看配置文件
        view_config_action = QAction("📄 查看配置文件", self)
        view_config_action.triggered.connect(lambda: self._on_view_config(instance_name))
        menu.addAction(view_config_action)

        # 删除实例
        delete_action = QAction("🗑️ 删除实例", self)
        delete_action.triggered.connect(lambda: self._on_delete_instance(instance_name))
        menu.addAction(delete_action)

        # 显示菜单
        menu.exec_(self.table.viewport().mapToGlobal(pos))

    def _on_view_config(self, name: str):
        """查看配置文件

        Args:
            name: 实例名称
        """
        try:
            config_path = self.config_manager.config_dir / f"{name}.json"

            if not config_path.exists():
                QMessageBox.warning(self, "错误", f"配置文件不存在: {config_path}")
                return

            # 使用系统默认程序打开配置文件
            import os
            os.startfile(str(config_path))

            self.logger.info(f"查看配置: {name}")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开配置文件失败: {e}")

    def _on_delete_instance(self, name: str):
        """删除实例

        Args:
            name: 实例名称
        """
        # 确认对话框
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除实例 '{name}' 吗？\n\n"
            f"这将：\n"
            f"• 停止实例（如果正在运行）\n"
            f"• 删除配置文件\n"
            f"• 从列表中移除",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                # 停止实例
                instance = self.instance_manager.get_instance(name)
                if instance and instance.status != InstanceStatus.STOPPED:
                    self.instance_manager.stop_instance(name)

                # 删除配置文件
                config_path = self.config_manager.config_dir / f"{name}.json"
                if config_path.exists():
                    config_path.unlink()

                # 移除实例
                self.instance_manager.remove_instance(name)

                self.logger.info(f"删除实例: {name}")

                # 刷新显示
                self._load_instances()
                self._refresh_status()

                QMessageBox.information(self, "完成", f"实例 '{name}' 已删除")

            except Exception as e:
                QMessageBox.critical(self, "错误", f"删除实例失败: {e}")

    def closeEvent(self, event):
        """窗口关闭事件

        Args:
            event: 关闭事件
        """
        # 不关闭应用，只是隐藏窗口
        self.hide()
        self.window_closed.emit()
        event.ignore()
        self.logger.info("窗口已隐藏（未退出应用）")

    def force_show(self) -> None:
        """强制显示窗口并提升到最顶层"""
        # 确保窗口不是最小化状态
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized)

        # 显示窗口
        self.show()

        # 强制窗口到最前面（多次调用以确保在Windows上生效）
        self.raise_()
        self.activateWindow()

        # 在Windows上，使用延迟再次激活以确保获得焦点
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(50, self._delayed_activate)
        QTimer.singleShot(100, self._delayed_activate)

    def _delayed_activate(self) -> None:
        """延迟激活窗口（Windows兼容）"""
        self.raise_()
        self.activateWindow()
