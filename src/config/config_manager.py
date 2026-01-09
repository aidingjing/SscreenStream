"""
配置文件管理器

负责配置文件的生命周期管理，包括：
- 扫描和发现配置文件
- 添加、删除、重命名配置
- 配置文件热加载监听
- 配置元数据管理
"""

import os
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import logging

from .config_parser import ConfigParser
from .config_validator import ConfigValidator
from src.exceptions import ConfigValidationError


@dataclass
class ConfigMetadata:
    """配置文件元数据"""

    name: str  # 实例名称
    path: str  # 配置文件路径
    description: str = ""  # 描述
    created_at: datetime = field(default_factory=datetime.now)
    modified_at: datetime = field(default_factory=datetime.now)
    is_valid: bool = True
    error_message: Optional[str] = None

    # 配置摘要（用于UI显示）
    source_type: Optional[str] = None
    port: Optional[int] = None
    server_path: Optional[str] = None  # WebSocket 路由路径


class ConfigManager:
    """配置文件管理器

    管理配置文件的生命周期，包括 CRUD 操作和热加载
    """

    def __init__(self, config_dir: str, logger: Optional[logging.Logger] = None):
        """初始化配置管理器

        Args:
            config_dir: 配置文件目录路径
            logger: 日志记录器
        """
        self.config_dir = Path(config_dir)
        self.logger = logger or logging.getLogger(__name__)

        # 确保配置目录存在
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # 配置缓存 {name: ConfigMetadata}
        self._configs: Dict[str, ConfigMetadata] = {}

        # 配置验证器
        self.validator = ConfigValidator()

        # 文件监听器回调列表
        self._change_callbacks = []

        self.logger.info(f"配置管理器初始化完成，目录: {self.config_dir}")

    def scan_configs(self) -> List[ConfigMetadata]:
        """扫描配置目录，加载所有配置文件

        Returns:
            List[ConfigMetadata]: 配置元数据列表
        """
        self.logger.info("扫描配置目录...")

        # 清空缓存
        self._configs.clear()

        # 查找所有 .json 文件
        config_files = list(self.config_dir.glob("*.json"))

        for config_path in config_files:
            # 跳过非配置文件（如 .example.json）
            if config_path.name.endswith(".example.json"):
                continue

            try:
                metadata = self._load_metadata_from_file(config_path)
                self._configs[metadata.name] = metadata
                self.logger.debug(f"加载配置: {metadata.name} from {config_path}")
            except Exception as e:
                self.logger.error(f"加载配置失败 {config_path}: {e}")

        self.logger.info(f"扫描完成，找到 {len(self._configs)} 个配置文件")
        return list(self._configs.values())

    def _load_metadata_from_file(self, config_path: Path) -> ConfigMetadata:
        """从文件加载配置元数据

        Args:
            config_path: 配置文件路径

        Returns:
            ConfigMetadata: 配置元数据
        """
        # 实例名称 = 文件名（不含扩展名）
        instance_name = config_path.stem

        # 文件时间戳
        created_at = datetime.fromtimestamp(config_path.stat().st_ctime)
        modified_at = datetime.fromtimestamp(config_path.stat().st_mtime)

        # 尝试加载配置
        try:
            parser = ConfigParser(str(config_path), self.validator)
            config_data = parser.parse()

            # 读取描述（如果有）
            description = getattr(config_data, 'description', '')

            # 提取配置摘要
            source_type = config_data.source.source.type if config_data.source else None
            port = config_data.server_port
            server_path = config_data.server_path

            return ConfigMetadata(
                name=instance_name,
                path=str(config_path),
                description=description,
                created_at=created_at,
                modified_at=modified_at,
                is_valid=True,
                source_type=source_type,
                port=port,
                server_path=server_path
            )

        except Exception as e:
            # 配置无效
            return ConfigMetadata(
                name=instance_name,
                path=str(config_path),
                created_at=created_at,
                modified_at=modified_at,
                is_valid=False,
                error_message=str(e)
            )

    def load_config(self, name: str) -> Any:
        """加载指定名称的配置

        Args:
            name: 实例名称

        Returns:
            ConfigData: 配置数据对象

        Raises:
            FileNotFoundError: 配置不存在
            ConfigValidationError: 配置无效
        """
        if name not in self._configs:
            raise FileNotFoundError(f"配置不存在: {name}")

        metadata = self._configs[name]

        if not metadata.is_valid:
            raise ConfigValidationError(f"配置无效: {metadata.error_message}")

        parser = ConfigParser(metadata.path, self.validator)
        return parser.parse()

    def add_config(self, source_path: str, name: str, description: str = "") -> ConfigMetadata:
        """添加新配置文件

        Args:
            source_path: 源配置文件路径
            name: 实例名称
            description: 配置描述

        Returns:
            ConfigMetadata: 配置元数据

        Raises:
            FileNotFoundError: 源文件不存在
            ConfigValidationError: 配置无效
            ValueError: 实例名称已存在
        """
        self.logger.info(f"添加配置: {name} from {source_path}")

        # 检查名称是否已存在
        if name in self._configs:
            raise ValueError(f"实例名称已存在: {name}")

        # 验证源文件
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"源文件不存在: {source_path}")

        # 验证配置
        try:
            parser = ConfigParser(str(source), self.validator)
            config_data = parser.parse()
        except Exception as e:
            raise ConfigValidationError(f"配置验证失败: {e}")

        # 目标路径
        target_path = self.config_dir / f"{name}.json"

        # 复制文件
        shutil.copy2(source, target_path)

        # 如果有描述，添加到配置文件
        if description:
            self._add_description_to_config(target_path, description)

        # 创建元数据
        metadata = ConfigMetadata(
            name=name,
            path=str(target_path),
            description=description,
            created_at=datetime.now(),
            modified_at=datetime.now(),
            is_valid=True,
            source_type=config_data.source.source.type,
            port=config_data.server_port
        )

        # 添加到缓存
        self._configs[name] = metadata

        # 通知变更
        self._notify_change("added", name)

        self.logger.info(f"配置添加成功: {name}")
        return metadata

    def _add_description_to_config(self, config_path: Path, description: str):
        """向配置文件添加描述字段

        Args:
            config_path: 配置文件路径
            description: 描述文本
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            config['description'] = description

            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

        except Exception as e:
            self.logger.warning(f"添加描述失败: {e}")

    def remove_config(self, name: str) -> None:
        """删除配置文件

        Args:
            name: 实例名称

        Raises:
            FileNotFoundError: 配置不存在
        """
        self.logger.info(f"删除配置: {name}")

        if name not in self._configs:
            raise FileNotFoundError(f"配置不存在: {name}")

        metadata = self._configs[name]
        config_path = Path(metadata.path)

        # 删除文件
        if config_path.exists():
            config_path.unlink()

        # 从缓存移除
        del self._configs[name]

        # 通知变更
        self._notify_change("removed", name)

        self.logger.info(f"配置删除成功: {name}")

    def update_config(self, name: str, new_name: Optional[str] = None,
                     new_description: Optional[str] = None) -> ConfigMetadata:
        """更新配置元数据

        Args:
            name: 实例名称
            new_name: 新名称（可选）
            new_description: 新描述（可选）

        Returns:
            ConfigMetadata: 更新后的元数据

        Raises:
            FileNotFoundError: 配置不存在
            ValueError: 新名称已存在
        """
        self.logger.info(f"更新配置: {name}")

        if name not in self._configs:
            raise FileNotFoundError(f"配置不存在: {name}")

        metadata = self._configs[name]
        config_path = Path(metadata.path)

        # 重命名
        if new_name and new_name != name:
            if new_name in self._configs:
                raise ValueError(f"实例名称已存在: {new_name}")

            new_path = self.config_dir / f"{new_name}.json"
            config_path.rename(new_path)

            # 更新路径
            metadata.path = str(new_path)
            metadata.name = new_name

            # 更新缓存键
            del self._configs[name]
            self._configs[new_name] = metadata

            name = new_name

        # 更新描述
        if new_description is not None:
            metadata.description = new_description
            self._add_description_to_config(Path(metadata.path), new_description)

        # 更新修改时间
        metadata.modified_at = datetime.now()

        # 通知变更
        self._notify_change("updated", name)

        self.logger.info(f"配置更新成功: {name}")
        return metadata

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """验证配置字典

        Args:
            config: 配置字典

        Returns:
            bool: 是否有效
        """
        try:
            self.validator.validate(config)
            return True
        except ConfigValidationError:
            return False

    def get_all_configs(self) -> List[ConfigMetadata]:
        """获取所有配置

        Returns:
            List[ConfigMetadata]: 配置元数据列表
        """
        return list(self._configs.values())

    def get_config(self, name: str) -> Optional[ConfigMetadata]:
        """获取指定配置

        Args:
            name: 实例名称

        Returns:
            Optional[ConfigMetadata]: 配置元数据，不存在返回 None
        """
        return self._configs.get(name)

    def register_change_callback(self, callback):
        """注册配置变更回调

        Args:
            callback: 回调函数，签名为 callback(event_type, config_name)
        """
        self._change_callbacks.append(callback)

    def _notify_change(self, event_type: str, config_name: str):
        """通知配置变更

        Args:
            event_type: 事件类型 (added, removed, updated)
            config_name: 配置名称
        """
        for callback in self._change_callbacks:
            try:
                callback(event_type, config_name)
            except Exception as e:
                self.logger.error(f"回调函数执行失败: {e}")

    def check_path_conflict(
        self,
        port: int,
        path: str,
        exclude_name: Optional[str] = None
    ) -> Optional[str]:
        """检查路径冲突

        Args:
            port: 端口号
            path: 路径
            exclude_name: 排除的配置名称（用于编辑时排除自己）

        Returns:
            Optional[str]: 如果冲突，返回占用者名称；否则返回 None
        """
        # 路径不区分大小写
        path_lower = path.lower()

        for config_name, metadata in self._configs.items():
            # 排除自己
            if exclude_name and config_name == exclude_name:
                continue

            # 检查端口和路径是否都相同
            if (
                metadata.port == port
                and metadata.server_path
                and metadata.server_path.lower() == path_lower
            ):
                return config_name

        return None
