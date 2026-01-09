"""
实例管理器

管理多个推流实例的生命周期，包括：
- 创建和销毁实例
- 启动、停止、重启实例
- 端口分配和管理
- 实例状态监控
"""

import socket
import logging
from typing import Dict, Optional, List
from threading import Lock

from .streaming_instance import StreamingInstance, InstanceStatus, InstanceInfo
from src.config.config_manager import ConfigManager
from src.config.config_parser import ConfigData


class InstanceManager:
    """实例管理器

    管理所有推流实例的生命周期
    """

    def __init__(
        self,
        config_manager: ConfigManager,
        base_port: int = 8765,
        logger: Optional[logging.Logger] = None
    ):
        """初始化实例管理器

        Args:
            config_manager: 配置管理器
            base_port: 起始端口号
            logger: 日志记录器
        """
        self.config_manager = config_manager
        self.base_port = base_port
        self.logger = logger or logging.getLogger(__name__)

        # 实例字典 {name: StreamingInstance}
        self._instances: Dict[str, StreamingInstance] = {}
        self._lock = Lock()  # 线程锁

        # 已分配的端口
        self._used_ports: set = set()

        self.logger.info(f"实例管理器初始化完成，起始端口: {base_port}")

    def create_instance(self, config_name: str) -> StreamingInstance:
        """创建实例

        Args:
            config_name: 配置名称

        Returns:
            StreamingInstance: 创建的实例

        Raises:
            FileNotFoundError: 配置不存在
            ValueError: 实例已存在
        """
        with self._lock:
            # 加载配置
            config = self.config_manager.load_config(config_name)

            # 检查实例是否已存在
            if config_name in self._instances:
                raise ValueError(f"实例已存在: {config_name}")

            # 分配端口
            port = self._allocate_port()

            self.logger.info(f"创建实例: {config_name}, 端口: {port}")

            # 创建实例
            instance = StreamingInstance(
                name=config_name,
                config=config,
                port=port,
                logger=self.logger
            )

            # 注册状态变更回调
            instance.register_status_callback(
                lambda old, new: self._on_instance_status_change(config_name, old, new)
            )

            # 保存实例
            self._instances[config_name] = instance

            return instance

    def remove_instance(self, name: str) -> None:
        """移除实例

        Args:
            name: 实例名称

        Raises:
            ValueError: 实例不存在
            RuntimeError: 实例正在运行
        """
        with self._lock:
            if name not in self._instances:
                raise ValueError(f"实例不存在: {name}")

            instance = self._instances[name]

            # 检查状态
            if instance.status != InstanceStatus.STOPPED:
                raise RuntimeError(f"实例正在运行，请先停止: {name}")

            # 释放端口
            if instance.port in self._used_ports:
                self._used_ports.remove(instance.port)

            # 移除实例
            del self._instances[name]

            self.logger.info(f"实例已移除: {name}")

    def start_instance(self, name: str) -> None:
        """启动实例

        Args:
            name: 实例名称

        Raises:
            ValueError: 实例不存在
            RuntimeError: 实例已在运行
        """
        if name not in self._instances:
            raise ValueError(f"实例不存在: {name}")

        instance = self._instances[name]

        if instance.status != InstanceStatus.STOPPED:
            raise RuntimeError(f"实例未处于停止状态: {instance.status}")

        self.logger.info(f"启动实例: {name}")
        instance.start()

    def stop_instance(self, name: str, timeout: float = 5.0) -> None:
        """停止实例

        Args:
            name: 实例名称
            timeout: 等待超时时间（秒）

        Raises:
            ValueError: 实例不存在
        """
        if name not in self._instances:
            raise ValueError(f"实例不存在: {name}")

        instance = self._instances[name]

        self.logger.info(f"停止实例: {name}")
        instance.stop(timeout=timeout)

    def restart_instance(self, name: str) -> None:
        """重启实例

        Args:
            name: 实例名称

        Raises:
            ValueError: 实例不存在
        """
        if name not in self._instances:
            raise ValueError(f"实例不存在: {name}")

        instance = self._instances[name]

        self.logger.info(f"重启实例: {name}")
        instance.restart()

    def get_instance(self, name: str) -> Optional[StreamingInstance]:
        """获取实例

        Args:
            name: 实例名称

        Returns:
            Optional[StreamingInstance]: 实例对象，不存在返回 None
        """
        return self._instances.get(name)

    def get_instance_status(self, name: str) -> Optional[InstanceStatus]:
        """获取实例状态

        Args:
            name: 实例名称

        Returns:
            Optional[InstanceStatus]: 实例状态，不存在返回 None
        """
        instance = self._instances.get(name)
        return instance.status if instance else None

    def get_instance_info(self, name: str) -> Optional[InstanceInfo]:
        """获取实例信息

        Args:
            name: 实例名称

        Returns:
            Optional[InstanceInfo]: 实例信息，不存在返回 None
        """
        instance = self._instances.get(name)
        return instance.get_info() if instance else None

    def get_all_statuses(self) -> Dict[str, InstanceStatus]:
        """获取所有实例状态

        Returns:
            Dict[str, InstanceStatus]: {实例名: 状态}
        """
        with self._lock:
            return {
                name: instance.status
                for name, instance in self._instances.items()
            }

    def get_all_infos(self) -> List[InstanceInfo]:
        """获取所有实例信息

        Returns:
            List[InstanceInfo]: 实例信息列表
        """
        with self._lock:
            return [
                instance.get_info()
                for instance in self._instances.values()
            ]

    def _allocate_port(self) -> int:
        """分配端口

        Returns:
            int: 分配的端口号

        Raises:
            RuntimeError: 无可用端口
        """
        # 从起始端口开始查找可用端口
        port = self.base_port

        while port < 65536:
            if port not in self._used_ports:
                # 检查端口是否被系统占用
                if self._is_port_available(port):
                    self._used_ports.add(port)
                    return port
            port += 1

        raise RuntimeError("无可用端口")

    def _is_port_available(self, port: int) -> bool:
        """检查端口是否可用

        Args:
            port: 端口号

        Returns:
            bool: 是否可用
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', port))
                return True
        except OSError:
            return False

    def _on_instance_status_change(
        self,
        name: str,
        old_status: InstanceStatus,
        new_status: InstanceStatus
    ):
        """实例状态变更回调

        Args:
            name: 实例名称
            old_status: 旧状态
            new_status: 新状态
        """
        self.logger.info(
            f"实例状态变更: {name} {old_status.value} -> {new_status.value}"
        )

        # 如果实例停止，释放端口
        if new_status == InstanceStatus.STOPPED:
            instance = self._instances.get(name)
            if instance and instance.port in self._used_ports:
                # 注意：这里不立即释放端口，允许重启时复用
                pass

    def get_running_count(self) -> int:
        """获取运行中的实例数量

        Returns:
            int: 运行中的实例数
        """
        count = 0
        for instance in self._instances.values():
            if instance.status == InstanceStatus.RUNNING:
                count += 1
        return count

    def get_stopped_count(self) -> int:
        """获取已停止的实例数量

        Returns:
            int: 已停止的实例数
        """
        count = 0
        for instance in self._instances.values():
            if instance.status == InstanceStatus.STOPPED:
                count += 1
        return count

    def get_error_count(self) -> int:
        """获取错误状态的实例数量

        Returns:
            int: 错误状态的实例数
        """
        count = 0
        for instance in self._instances.values():
            if instance.status == InstanceStatus.ERROR:
                count += 1
        return count

    def stop_all(self, timeout: float = 5.0) -> None:
        """停止所有实例

        Args:
            timeout: 单个实例等待超时时间
        """
        self.logger.info("停止所有实例")

        for name, instance in list(self._instances.items()):
            if instance.status != InstanceStatus.STOPPED:
                try:
                    instance.stop(timeout=timeout)
                except Exception as e:
                    self.logger.error(f"停止实例失败 {name}: {e}")

    def get_instance_logs(self, name: str) -> List[str]:
        """获取实例日志

        Args:
            name: 实例名称

        Returns:
            List[str]: 日志列表
        """
        instance = self._instances.get(name)
        return instance.get_log() if instance else []
