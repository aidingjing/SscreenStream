"""
配置对话框

用于添加新配置的图形界面对话框
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QTextEdit, QPushButton,
    QFileDialog, QMessageBox, QCheckBox, QGroupBox,
    QScrollArea, QWidget
)
from PyQt5.QtCore import Qt, pyqtSignal


class ConfigDialog(QDialog):
    """添加配置对话框"""

    # 信号：配置添加成功
    config_added = pyqtSignal(str)  # 参数：配置名称

    def __init__(
        self,
        config_dir: str,
        parent=None,
        logger: Optional[Any] = None
    ):
        """初始化配置对话框

        Args:
            config_dir: 配置文件目录
            parent: 父窗口
            logger: 日志记录器
        """
        super().__init__(parent)

        self.config_dir = Path(config_dir)
        self.logger = logger
        self.config_data: Optional[Dict[str, Any]] = None

        self.setWindowTitle("添加配置")
        self.setMinimumSize(600, 500)
        self.resize(700, 600)

        self._init_ui()

    def _init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)

        # 文件选择组
        file_group = QGroupBox("配置文件")
        file_layout = QHBoxLayout(file_group)

        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("选择配置文件...")
        self.file_path_edit.setReadOnly(True)

        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.clicked.connect(self._on_browse_file)

        file_layout.addWidget(self.file_path_edit)
        file_layout.addWidget(self.browse_btn)

        layout.addWidget(file_group)

        # 配置信息组
        info_group = QGroupBox("配置信息")
        info_layout = QFormLayout(info_group)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("自动从文件名提取")
        self.name_edit.textChanged.connect(self._on_name_changed)

        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)
        self.description_edit.setPlaceholderText("（可选）配置描述...")

        self.auto_start_checkbox = QCheckBox("添加后自动启动此实例")

        info_layout.addRow("实例名称*:", self.name_edit)
        info_layout.addRow("描述:", self.description_edit)
        info_layout.addRow("", self.auto_start_checkbox)

        layout.addWidget(info_group)

        # 配置预览组
        preview_group = QGroupBox("配置预览")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(200)
        self.preview_text.setPlaceholderText("选择配置文件后在此显示内容...")

        preview_layout.addWidget(self.preview_text)
        layout.addWidget(preview_group)

        # 验证状态
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: gray;")
        layout.addWidget(self.status_label)

        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.ok_btn = QPushButton("确定")
        self.ok_btn.setEnabled(False)
        self.ok_btn.clicked.connect(self._on_ok)
        self.ok_btn.setMinimumWidth(100)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        self.cancel_btn.setMinimumWidth(100)

        button_layout.addWidget(self.ok_btn)
        button_layout.addWidget(self.cancel_btn)

        layout.addLayout(button_layout)

    def _on_browse_file(self):
        """浏览文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择配置文件",
            str(Path.home()),
            "JSON Files (*.json);;All Files (*)"
        )

        if file_path:
            self._load_config_file(file_path)

    def _load_config_file(self, file_path: str):
        """加载配置文件

        Args:
            file_path: 配置文件路径
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.config_data = json.load(f)

            # 显示文件路径
            self.file_path_edit.setText(file_path)

            # 自动提取名称
            file_name = Path(file_path).stem
            if not self.name_edit.text():
                self.name_edit.setText(file_name)

            # 显示配置预览
            preview = json.dumps(self.config_data, indent=2, ensure_ascii=False)
            self.preview_text.setText(preview)

            # 验证配置
            self._validate_config()

        except json.JSONDecodeError as e:
            self._show_error(f"配置文件格式错误: {e}")
            self.config_data = None
            self.preview_text.clear()
            self.ok_btn.setEnabled(False)

        except Exception as e:
            self._show_error(f"读取文件失败: {e}")
            self.config_data = None
            self.preview_text.clear()
            self.ok_btn.setEnabled(False)

    def _validate_config(self):
        """验证配置"""
        if not self.config_data:
            self._show_error("请先选择配置文件")
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

        # 检查服务器配置
        if 'port' not in self.config_data['server']:
            self._show_warning("配置未指定端口，将自动分配")

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

        # 配置有效
        self._show_success("配置有效，可以添加")
        self.ok_btn.setEnabled(True)

    def _on_name_changed(self, text: str):
        """名称改变时检查是否已存在

        Args:
            text: 实例名称
        """
        if not text:
            return

        # 检查名称是否已存在
        config_path = self.config_dir / f"{text}.json"
        if config_path.exists():
            self._show_warning(f"配置 '{text}' 已存在，将覆盖")

    def _on_ok(self):
        """确定按钮点击"""
        name = self.name_edit.text().strip()

        if not name:
            QMessageBox.warning(self, "错误", "请输入实例名称")
            return

        if not self.config_data:
            QMessageBox.warning(self, "错误", "请先选择配置文件")
            return

        try:
            # 添加可选字段
            self.config_data['instance_name'] = name

            description = self.description_edit.toPlainText().strip()
            if description:
                self.config_data['description'] = description

            # 复制配置文件到 configs 目录
            target_path = self.config_dir / f"{name}.json"

            # 确保目录存在
            self.config_dir.mkdir(parents=True, exist_ok=True)

            # 写入配置文件
            with open(target_path, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, indent=2, ensure_ascii=False)

            self.logger.info(f"添加配置: {name} -> {target_path}")

            # 发送信号
            self.config_added.emit(name)

            # 关闭对话框
            self.accept()

            QMessageBox.information(
                self,
                "成功",
                f"配置 '{name}' 添加成功！\n\n"
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
