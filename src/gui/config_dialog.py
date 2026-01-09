"""
配置对话框

用于添加新配置的图形界面对话框
支持从现有配置选择模板，并提供可视化编辑功能
"""

import os
import json
import copy  # 新增：用于深拷贝
from pathlib import Path
from typing import Optional, Dict, Any, List
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QTextEdit, QPushButton,
    QFileDialog, QMessageBox, QCheckBox, QGroupBox,
    QScrollArea, QWidget, QListWidget, QListWidgetItem,
    QSplitter, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont


class ConfigDialog(QDialog):
    """添加配置对话框（增强版）"""

    # 信号：配置添加成功
    config_added = pyqtSignal(str)  # 参数：配置名称

    def __init__(
        self,
        config_dir: str,
        config_manager=None,  # 新增：配置管理器
        existing_configs: List = None,  # 新增：现有配置列表
        parent=None,
        logger: Optional[Any] = None
    ):
        """初始化配置对话框

        Args:
            config_dir: 配置文件目录
            config_manager: 配置管理器（用于获取配置列表和验证）
            existing_configs: 现有配置列表（用于模板选择）
            parent: 父窗口
            logger: 日志记录器
        """
        super().__init__(parent)

        self.config_dir = Path(config_dir)
        self.config_manager = config_manager
        self.existing_configs = existing_configs or []
        self.logger = logger

        # 当前编辑的配置数据
        self.config_data: Optional[Dict[str, Any]] = None
        self.template_config: Optional[Dict[str, Any]] = None
        self.template_name: Optional[str] = None  # 记录模板名称，用于检测覆盖

        self.setWindowTitle("添加配置")
        self.setMinimumSize(900, 700)
        self.resize(1000, 800)

        self._init_ui()

        # 如果有现有配置，加载到模板列表
        if self.existing_configs:
            self._load_template_list()

    def _init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)

        # 使用分割器：左侧模板列表，右侧编辑区域
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # === 左侧：模板选择区域 ===
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # 模板选择组
        template_group = QGroupBox("1. 选择模板配置")
        template_layout = QVBoxLayout(template_group)

        self.template_list = QListWidget()
        self.template_list.itemClicked.connect(self._on_template_selected)
        template_layout.addWidget(self.template_list)

        # 提示标签
        template_hint = QLabel("💡 提示：点击上方配置作为模板")
        template_hint.setStyleSheet("color: gray; font-size: 11px;")
        template_layout.addWidget(template_hint)

        left_layout.addWidget(template_group)

        # 或者浏览文件按钮
        file_group = QGroupBox("或浏览文件")
        file_layout = QVBoxLayout(file_group)

        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("或选择其他配置文件...")
        self.file_path_edit.setReadOnly(True)

        browse_layout = QHBoxLayout()
        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.clicked.connect(self._on_browse_file)
        browse_layout.addWidget(self.browse_btn)

        file_layout.addWidget(self.file_path_edit)
        file_layout.addLayout(browse_layout)

        left_layout.addWidget(file_group)
        left_layout.addStretch()

        # === 右侧：配置编辑区域 ===
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # 基本配置组
        info_group = QGroupBox("2. 编辑配置信息")
        info_layout = QFormLayout(info_group)

        # 实例名称
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("输入实例名称（如：desktop, cam-front）")
        self.name_edit.textChanged.connect(self._on_field_changed)
        info_layout.addRow("实例名称*:", self.name_edit)

        # 描述
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(60)
        self.description_edit.setPlaceholderText("（可选）配置描述...")
        self.description_edit.textChanged.connect(self._on_field_changed)
        info_layout.addRow("描述:", self.description_edit)

        # 端口
        self.port_edit = QLineEdit()
        self.port_edit.setPlaceholderText("默认 8765")
        self.port_edit.textChanged.connect(self._on_field_changed)
        info_layout.addRow("服务器端口:", self.port_edit)

        # 路径（新增）
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("默认 /")
        self.path_edit.setText("/")  # 默认值
        self.path_edit.textChanged.connect(self._on_path_changed)
        info_layout.addRow("路由路径*:", self.path_edit)

        # 路径验证状态
        self.path_status_label = QLabel()
        self.path_status_label.setStyleSheet("color: gray; font-size: 10px;")
        info_layout.addRow("", self.path_status_label)

        right_layout.addWidget(info_group)

        # 配置预览组
        preview_group = QGroupBox("3. 配置预览")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMinimumHeight(250)
        self.preview_text.setPlaceholderText("选择模板配置后在此显示内容...")
        # 设置等宽字体
        font = QFont("Consolas", 9)
        self.preview_text.setFont(font)

        preview_layout.addWidget(self.preview_text)
        right_layout.addWidget(preview_group)

        # 验证状态
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: gray;")
        right_layout.addWidget(self.status_label)

        # 自动启动复选框
        self.auto_start_checkbox = QCheckBox("添加后自动启动此实例")
        right_layout.addWidget(self.auto_start_checkbox)

        # 添加到分割器
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)  # 左侧占 1/3
        splitter.setStretchFactor(1, 2)  # 右侧占 2/3

        # === 底部按钮 ===
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.ok_btn = QPushButton("确定")
        self.ok_btn.setEnabled(False)
        self.ok_btn.clicked.connect(self._on_ok)
        self.ok_btn.setMinimumWidth(100)
        self.ok_btn.setStyleSheet("font-weight: bold;")

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        self.cancel_btn.setMinimumWidth(100)

        button_layout.addWidget(self.ok_btn)
        button_layout.addWidget(self.cancel_btn)

        layout.addLayout(button_layout)

    def _load_template_list(self):
        """加载模板配置列表"""
        self.template_list.clear()

        for config in self.existing_configs:
            # 创建列表项
            item_text = f"{config.name}"

            # 添加详细信息
            if config.port:
                item_text += f" (端口: {config.port})"
            if config.source_type:
                item_text += f" - {config.source_type}"

            item = QListWidgetItem(item_text)
            # 存储配置数据
            item.setData(Qt.UserRole, config)
            self.template_list.addItem(item)

    def _on_template_selected(self, item: QListWidgetItem):
        """模板选择事件处理

        Args:
            item: 列表项
        """
        config_metadata = item.data(Qt.UserRole)
        if not config_metadata:
            return

        # 加载配置文件
        try:
            self._load_config_file(config_metadata.path)
        except Exception as e:
            self._show_error(f"加载模板失败: {e}")
            self.logger.error(f"加载模板失败: {e}", exc_info=True)

    def _on_browse_file(self):
        """浏览文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择配置文件",
            str(Path.home()),
            "JSON Files (*.json);;All Files (*)"
        )

        if file_path:
            try:
                self._load_config_file(file_path)
            except Exception as e:
                self._show_error(f"加载文件失败: {e}")
                self.logger.error(f"加载文件失败: {e}", exc_info=True)

    def _load_config_file(self, file_path: str):
        """加载配置文件

        Args:
            file_path: 配置文件路径
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                original_config = json.load(f)

                # ✅ 使用深拷贝，避免修改原始模板配置
                self.config_data = copy.deepcopy(original_config)
                self.template_config = copy.deepcopy(original_config)

            # 记录模板名称
            self.template_name = Path(file_path).stem

            # 显示文件路径
            self.file_path_edit.setText(file_path)

            # 自动提取名称
            file_name = Path(file_path).stem
            if not self.name_edit.text():
                self.name_edit.setText(file_name)

            # 提取配置信息到表单
            self._populate_form_from_config()

            # 显示配置预览
            self._update_preview()

            # 验证配置
            self._validate_config()

        except json.JSONDecodeError as e:
            self._show_error(f"配置文件格式错误: {e}")
            self.config_data = None
            self.template_config = None
            self.template_name = None
            self.preview_text.clear()
            self.ok_btn.setEnabled(False)

    def _populate_form_from_config(self):
        """从配置数据填充表单"""
        if not self.config_data:
            return

        # 提取端口
        server = self.config_data.get('server', {})
        port = server.get('port')
        if port:
            self.port_edit.setText(str(port))

        # 提取路径
        path = server.get('path', '/')
        self.path_edit.setText(path)

        # 提取描述
        description = self.config_data.get('description', '')
        if description:
            self.description_edit.setText(description)

        # 验证路径冲突
        self._validate_path_conflict()

    def _on_field_changed(self):
        """字段改变事件处理"""
        # 实时更新预览
        if self.config_data:
            self._update_preview()

    def _on_path_changed(self, text: str):
        """路径改变事件处理

        Args:
            text: 路径文本
        """
        # 验证路径格式
        if not text:
            self.path_status_label.setText("⚠️ 路径不能为空")
            self.path_status_label.setStyleSheet("color: orange; font-size: 10px;")
        elif not text.startswith('/'):
            self.path_status_label.setText("⚠️ 路径必须以 / 开头")
            self.path_status_label.setStyleSheet("color: orange; font-size: 10px;")
        elif ".." in text:
            self.path_status_label.setText("⚠️ 路径不能包含 ..（防止路径遍历）")
            self.path_status_label.setStyleSheet("color: red; font-size: 10px;")
        elif any(char in text for char in [" ", "\\", "\n", "\r", "\t"]):
            self.path_status_label.setText("⚠️ 路径不能包含空格或特殊字符")
            self.path_status_label.setStyleSheet("color: red; font-size: 10px;")
        else:
            self.path_status_label.setText("✓ 路径格式正确")
            self.path_status_label.setStyleSheet("color: green; font-size: 10px;")

        # 验证路径冲突
        self._validate_path_conflict()

        # 更新预览
        if self.config_data:
            self._update_preview()

    def _validate_path_conflict(self):
        """验证路径冲突"""
        if not self.config_manager:
            return

        try:
            port = int(self.port_edit.text()) if self.port_edit.text() else None
            path = self.path_edit.text()

            if port and path:
                # 检查路径冲突
                conflict_name = self.config_manager.check_path_conflict(port, path)

                if conflict_name:
                    self.path_status_label.setText(
                        f"⚠️ 路径冲突：已被配置 '{conflict_name}' 占用"
                    )
                    self.path_status_label.setStyleSheet("color: red; font-size: 10px;")
                else:
                    self.path_status_label.setText("✓ 路径可用")
                    self.path_status_label.setStyleSheet("color: green; font-size: 10px;")

        except ValueError:
            pass  # 端口无效，稍后会验证

    def _update_preview(self):
        """更新配置预览"""
        if not self.config_data:
            return

        # 复制配置数据
        preview_config = self.config_data.copy()

        # 更新服务器配置
        preview_config.setdefault('server', {})

        if self.port_edit.text():
            try:
                preview_config['server']['port'] = int(self.port_edit.text())
            except ValueError:
                pass

        preview_config['server']['path'] = self.path_edit.text() or '/'

        # 更新描述
        description = self.description_edit.toPlainText().strip()
        if description:
            preview_config['description'] = description

        # 显示预览
        preview = json.dumps(preview_config, indent=2, ensure_ascii=False)
        self.preview_text.setText(preview)

    def _validate_config(self):
        """验证配置"""
        if not self.config_data:
            self._show_error("请先选择配置文件或模板")
            self.ok_btn.setEnabled(False)
            return

        # 检查必需字段
        required_fields = ['server', 'ffmpeg', 'source']
        missing_fields = [
            field for field in required_fields
            if field not in self.config_data
        ]

        if missing_fields:
            self._show_error(f"配置缺少必需字段: {', '.join(missing_fields)}")
            self.ok_btn.setEnabled(False)
            return

        # 验证路径格式
        path = self.path_edit.text().strip()
        if not path:
            self._show_error("请输入路由路径")
            self.ok_btn.setEnabled(False)
            return

        if not path.startswith('/'):
            self._show_error(f"路径必须以 / 开头，当前值: {path}")
            self.ok_btn.setEnabled(False)
            return

        # 检查路径安全性（防止路径遍历）
        if ".." in path:
            self._show_error(f"路径不能包含 ..（防止路径遍历攻击），当前值: {path}")
            self.ok_btn.setEnabled(False)
            return

        # 检查非法字符
        if any(char in path for char in [" ", "\\", "\n", "\r", "\t"]):
            self._show_error(f"路径不能包含空格或特殊字符，当前值: {path}")
            self.ok_btn.setEnabled(False)
            return

        # 验证端口
        port_text = self.port_edit.text().strip()
        if port_text:
            try:
                port = int(port_text)
                if not (1024 <= port <= 65535):
                    self._show_error(f"端口必须在 1024-65535 之间，当前值: {port}")
                    self.ok_btn.setEnabled(False)
                    return
            except ValueError:
                self._show_error(f"端口必须是整数，当前值: {port_text}")
                self.ok_btn.setEnabled(False)
                return

        # 检查源配置
        source = self.config_data.get('source', {})
        source_type = source.get('type')

        if not source_type:
            self._show_error("配置缺少 source.type 字段")
            self.ok_btn.setEnabled(False)
            return

        valid_types = ['screen', 'window', 'window_bg', 'window_region', 'network_stream']
        if source_type not in valid_types:
            self._show_warning(f"未知源类型: {source_type}")

        # 检查路径冲突
        if self.config_manager:
            port = int(self.port_edit.text()) if self.port_edit.text() else 8765
            conflict_name = self.config_manager.check_path_conflict(port, path)

            if conflict_name:
                self._show_error(f"路径冲突：已被配置 '{conflict_name}' 占用")
                self.ok_btn.setEnabled(False)
                return

        # 配置有效
        self._show_success("配置有效，可以添加")
        self.ok_btn.setEnabled(True)

    def _on_ok(self):
        """确定按钮点击"""
        name = self.name_edit.text().strip()

        if not name:
            QMessageBox.warning(self, "错误", "请输入实例名称")
            return

        # 检查是否使用了模板名称（会覆盖原模板）
        if self.template_name and name == self.template_name:
            reply = QMessageBox.warning(
                self,
                "⚠️ 警告：将覆盖原模板",
                f"您正在使用模板的原始名称 '{name}'。\n\n"
                f"如果保存，将覆盖原有的模板配置文件！\n\n"
                f"建议：\n"
                f"• 点击'否'，修改实例名称后保存\n"
                f"• 或者点击'是'覆盖原模板",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        # 检查配置是否已存在
        target_path = self.config_dir / f"{name}.json"
        if target_path.exists() and name != self.template_name:
            reply = QMessageBox.question(
                self,
                "配置已存在",
                f"配置文件 '{name}.json' 已存在，是否覆盖？\n\n"
                f"如果不想覆盖，请点击'否'并修改实例名称。",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        if not self.config_data:
            QMessageBox.warning(self, "错误", "请先选择配置文件或模板")
            return

        try:
            # 更新配置数据
            self.config_data.setdefault('server', {})

            # 更新端口
            if self.port_edit.text():
                try:
                    self.config_data['server']['port'] = int(self.port_edit.text())
                except ValueError:
                    pass

            # 更新路径
            self.config_data['server']['path'] = self.path_edit.text() or '/'

            # 添加描述
            description = self.description_edit.toPlainText().strip()
            if description:
                self.config_data['description'] = description

            # 确保目录存在
            self.config_dir.mkdir(parents=True, exist_ok=True)

            # 写入配置文件
            self.logger.info(f"准备写入配置文件: {name} -> {target_path}")
            self.logger.info(f"配置目录: {self.config_dir}")
            self.logger.info(f"文件是否存在（写入前）: {target_path.exists()}")

            with open(target_path, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, indent=2, ensure_ascii=False)

            self.logger.info(f"添加配置成功: {name} -> {target_path}")
            self.logger.info(f"文件是否存在（写入后）: {target_path.exists()}")
            self.logger.info(f"配置路径: {self.config_data['server']['path']}")

            # 发送信号
            self.config_added.emit(name)

            # 关闭对话框
            self.accept()

            QMessageBox.information(
                self,
                "成功",
                f"配置 '{name}' 添加成功！\n\n"
                f"连接 URL: ws://localhost:{self.config_data['server'].get('port', 8765)}{self.config_data['server']['path']}\n\n"
                f"配置文件: {target_path}"
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "错误",
                f"添加配置失败: {e}"
            )
            self.logger.error(f"添加配置失败: {e}", exc_info=True)

    def _show_error(self, message: str):
        """显示错误消息

        Args:
            message: 错误消息
        """
        self.status_label.setText(f"❌ {message}")
        self.status_label.setStyleSheet("color: red;")

    def _show_warning(self, message: str):
        """显示警告消息

        Args:
            message: 警告消息
        """
        self.status_label.setText(f"⚠️ {message}")
        self.status_label.setStyleSheet("color: orange;")

    def _show_success(self, message: str):
        """显示成功消息

        Args:
            message: 成功消息
        """
        self.status_label.setText(f"✅ {message}")
        self.status_label.setStyleSheet("color: green;")

    def get_auto_start(self) -> bool:
        """获取是否自动启动

        Returns:
            bool: 是否自动启动
        """
        return self.auto_start_checkbox.isChecked()
