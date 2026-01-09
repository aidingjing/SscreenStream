"""
WebSocket 路由器

负责管理 WebSocket 路由表，根据端口和路径将客户端连接路由到对应的实例
"""

from typing import Dict, Tuple, Optional
import logging


class WebSocketRouter:
    """WebSocket 路由器

    管理多实例共享端口的路径路由
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        """初始化路由器

        Args:
            logger: 日志记录器
        """
        # 路由表：{(port, path): instance_name}
        self.routes: Dict[Tuple[int, str], str] = {}

        # 索引：{port: [paths]}
        self._port_index: Dict[int, list] = {}

        self.logger = logger or logging.getLogger(__name__)

    def add_route(self, port: int, path: str, instance_name: str) -> None:
        """添加路由

        Args:
            port: 端口号
            path: 路径
            instance_name: 实例名称

        Raises:
            ValueError: 路由已存在
        """
        key = (port, path)

        if key in self.routes:
            raise ValueError(
                f"路由已存在: {port}{path}（已被实例 '{self.routes[key]}' 占用）"
            )

        self.routes[key] = instance_name

        # 更新端口索引
        if port not in self._port_index:
            self._port_index[port] = []
        self._port_index[port].append(path)

        self.logger.info(f"添加路由: {port}{path} -> {instance_name}")

    def remove_route(self, port: int, path: str) -> bool:
        """移除路由

        Args:
            port: 端口号
            path: 路径

        Returns:
            bool: 是否成功移除
        """
        key = (port, path)

        if key not in self.routes:
            return False

        instance_name = self.routes[key]
        del self.routes[key]

        # 更新端口索引
        if port in self._port_index and path in self._port_index[port]:
            self._port_index[port].remove(path)

        self.logger.info(f"移除路由: {port}{path} -> {instance_name}")
        return True

    def get_instance(self, port: int, path: str) -> Optional[str]:
        """根据端口和路径获取实例名称

        Args:
            port: 端口号
            path: 路径

        Returns:
            Optional[str]: 实例名称，不存在返回 None
        """
        key = (port, path)
        return self.routes.get(key)

    def get_all_paths(self, port: int) -> list:
        """获取指定端口的所有路径

        Args:
            port: 端口号

        Returns:
            list: 路径列表
        """
        return self._port_index.get(port, []).copy()

    def get_all_routes(self) -> Dict[Tuple[int, str], str]:
        """获取所有路由

        Returns:
            Dict[Tuple[int, str], str]: 路由表副本
        """
        return self.routes.copy()

    def clear_port(self, port: int) -> int:
        """清除指定端口的所有路由

        Args:
            port: 端口号

        Returns:
            int: 清除的路由数量
        """
        count = 0

        # 收集要删除的键
        keys_to_delete = [
            (p, path) for (p, path) in self.routes.keys() if p == port
        ]

        # 删除路由
        for key in keys_to_delete:
            self.remove_route(key[0], key[1])
            count += 1

        self.logger.info(f"清除端口 {port} 的 {count} 个路由")
        return count

    def has_route(self, port: int, path: str) -> bool:
        """检查路由是否存在

        Args:
            port: 端口号
            path: 路径

        Returns:
            bool: 路由是否存在
        """
        return (port, path) in self.routes

    def get_instance_count(self, port: int) -> int:
        """获取指定端口的实例数量

        Args:
            port: 端口号

        Returns:
            int: 实例数量
        """
        return len(self._port_index.get(port, []))
