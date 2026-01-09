"""
客户端连接管理器

管理所有 WebSocket 客户端连接
"""

import uuid
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field
import logging


@dataclass
class ConnectionInfo:
    """客户端连接信息"""
    client_id: str
    websocket: 'WebSocketServerProtocol'  # 类型注解（字符串避免循环导入）
    connect_time: datetime
    is_authenticated: bool = True


class ClientManager:
    """客户端连接管理器

    职责：
    1. 管理所有客户端连接
    2. 维护客户端列表
    3. 统计连接数
    """

    def __init__(self, shutdown_timeout: int, logger: logging.Logger):
        """初始化管理器

        Args:
            shutdown_timeout: 关闭超时时间（秒）
            logger: 日志记录器
        """
        self.shutdown_timeout = shutdown_timeout
        self.logger = logger
        self.clients: Dict[str, ConnectionInfo] = {}

        self.logger.debug(
            f"客户端管理器已初始化，关闭超时: {shutdown_timeout}秒"
        )

    def add_client(
        self,
        client_id: str,
        websocket: 'WebSocketServerProtocol'
    ) -> ConnectionInfo:
        """添加客户端

        Args:
            client_id: 客户端 ID
            websocket: WebSocket 连接对象

        Returns:
            ConnectionInfo: 连接信息对象
        """
        conn_info = ConnectionInfo(
            client_id=client_id,
            websocket=websocket,
            connect_time=datetime.now()
        )

        self.clients[client_id] = conn_info

        self.logger.info(
            f"客户端已添加: {client_id}，"
            f"当前连接数: {len(self.clients)}"
        )

        return conn_info

    def remove_client(self, client_id: str) -> None:
        """移除客户端

        Args:
            client_id: 客户端 ID
        """
        if client_id in self.clients:
            del self.clients[client_id]

            self.logger.info(
                f"客户端已移除: {client_id}，"
                f"剩余连接数: {len(self.clients)}"
            )

    def get_client(self, client_id: str) -> Optional[ConnectionInfo]:
        """获取客户端信息

        Args:
            client_id: 客户端 ID

        Returns:
            Optional[ConnectionInfo]: 客户端信息，不存在返回 None
        """
        return self.clients.get(client_id)

    def get_all_clients(self) -> Dict[str, ConnectionInfo]:
        """获取所有客户端

        Returns:
            Dict[str, ConnectionInfo]: 客户端字典
        """
        return self.clients.copy()

    def get_client_count(self) -> int:
        """获取客户端数量

        Returns:
            int: 客户端数量
        """
        return len(self.clients)

    async def broadcast(self, data: bytes) -> None:
        """向所有客户端广播数据

        Args:
            data: 要发送的数据
        """
        if not self.clients:
            return

        # 记录发送前的客户端数
        initial_count = len(self.clients)

        # 创建客户端列表副本（避免迭代时修改字典）
        client_items = list(self.clients.items())

        # 遍历所有客户端
        failed_clients = []

        for client_id, conn_info in client_items:
            try:
                await conn_info.websocket.send(data)
            except Exception as e:
                self.logger.error(
                    f"发送数据到客户端 {client_id} 失败: {e}"
                )
                failed_clients.append(client_id)

        # 移除失败的客户端
        for client_id in failed_clients:
            self.remove_client(client_id)

        if failed_clients:
            self.logger.warning(
                f"广播完成，成功: {initial_count - len(failed_clients)}/{initial_count}，"
                f"失败: {len(failed_clients)}"
            )

    def is_empty(self) -> bool:
        """检查是否有客户端连接

        Returns:
            bool: True 表示没有客户端
        """
        return len(self.clients) == 0

    def generate_client_id(self) -> str:
        """生成唯一的客户端 ID

        Returns:
            str: 客户端 ID
        """
        return str(uuid.uuid4())

    def clear_all(self) -> None:
        """清除所有客户端连接"""
        count = len(self.clients)
        self.clients.clear()

        if count > 0:
            self.logger.info(f"已清除所有客户端连接，共 {count} 个")

    def get_client_ids(self) -> List[str]:
        """获取所有客户端 ID 列表

        Returns:
            List[str]: 客户端 ID 列表
        """
        return list(self.clients.keys())

    async def send_to_client(self, client_id: str, data: bytes) -> bool:
        """向指定客户端发送数据

        Args:
            client_id: 客户端 ID
            data: 要发送的数据

        Returns:
            bool: 发送是否成功
        """
        conn_info = self.get_client(client_id)
        if not conn_info:
            return False

        try:
            await conn_info.websocket.send(data)
            return True
        except Exception as e:
            self.logger.error(f"发送数据到客户端 {client_id} 失败: {e}")
            self.remove_client(client_id)
            return False
