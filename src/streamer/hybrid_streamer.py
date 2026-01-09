"""
混合流媒体服务器（HTTP + WebSocket）

- HTTP-FLV：用于 flv.js 播放
- WebSocket-FLV：用于其他客户端
"""

import asyncio
import logging
from typing import Optional
from aiohttp import web
import websockets
from websockets.server import WebSocketServerProtocol

from src.recorder.base_recorder import BaseRecorder
from src.streamer.client_manager import ClientManager
from src.config.config_parser import ConfigData


class HybridStreamer:
    """混合流媒体服务器（HTTP + WebSocket）

    职责：
    1. HTTP 服务器提供 FLV 流（flv.js 推荐）
    2. WebSocket 服务器提供备用接口
    3. 共享同一个 FFmpeg 进程
    """

    def __init__(
        self,
        config: ConfigData,
        recorder: BaseRecorder,
        logger: logging.Logger
    ):
        self.config = config
        self.recorder = recorder
        self.logger = logger

        # HTTP 应用
        self.app = web.Application()
        self.app.router.add_get('/live.flv', self.handle_http_flv)
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None

        # WebSocket 相关
        self.ws_clients: list = []
        self.ws_server: Optional[websockets.WebSocketServer] = None

        # 流转发
        self.http_clients: set = set()
        self.streaming = False

        self.logger.info("混合流媒体服务器已初始化")

    async def start(self) -> None:
        """启动 HTTP 和 WebSocket 服务器"""
        # 启动 HTTP 服务器
        self.logger.info(
            f"正在启动 HTTP 服务器，监听 {self.config.host}:8080..."
        )
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(
            self.runner,
            self.config.host,
            8080  # HTTP 端口
        )
        await self.site.start()
        self.logger.info(
            f"✅ HTTP 服务器已启动，监听 {self.config.host}:8080"
        )

        # 启动 WebSocket 服务器（备用）
        self.logger.info(
            f"正在启动 WebSocket 服务器，监听 {self.config.host}:8765..."
        )
        self.ws_server = await websockets.serve(
            self.handle_ws_client,
            self.config.host,
            8765
        )
        self.logger.info(
            f"✅ WebSocket 服务器已启动，监听 {self.config.host}:8765"
        )

        # 启动流转发任务
        asyncio.create_task(self.stream_loop())

        self.logger.info("⚠️  FFmpeg 未启动，等待客户端连接...")

    async def stop(self) -> None:
        """停止所有服务"""
        self.logger.info("正在关闭混合流媒体服务器...")

        # 停止流转发
        self.streaming = False

        # 停止 FFmpeg
        if self.recorder.is_running():
            await asyncio.to_thread(self.recorder.stop)

        # 停止 HTTP 服务器
        if self.runner:
            await self.runner.cleanup()

        # 停止 WebSocket 服务器
        if self.ws_server:
            self.ws_server.close()
            await self.ws_server.wait_closed()

        self.logger.info("混合流媒体服务器已关闭")

    async def handle_http_flv(self, request: web.Request) -> web.Response:
        """处理 HTTP-FLV 请求（flv.js 标准方式）"""
        self.logger.info("📡 HTTP-FLV 客户端连接")

        # 启动 FFmpeg（如果未运行）
        if not self.recorder.is_running():
            await asyncio.to_thread(self.recorder.start)

        # 创建流式响应
        response = web.StreamResponse(
            status=200,
            reason='OK',
            headers={
                'Content-Type': 'video/x-flv',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*',
            }
        )
        await response.prepare(request)

        # 添加到客户端集合
        self.http_clients.add(response)
        self.logger.info(f"HTTP-FLV 客户端已添加，当前客户端数: {len(self.http_clients)}")

        try:
            # 持续发送数据
            while True:
                data = await asyncio.to_thread(self.recorder.read_output, 8192)
                if data:
                    await response.write(data)
                else:
                    await asyncio.sleep(0.01)
        except (ConnectionResetError, ConnectionAbortedError):
            self.logger.info("HTTP-FLV 客户端断开")
        finally:
            self.http_clients.discard(response)
            self.logger.info(
                f"HTTP-FLV 客户端已移除，剩余客户端: {len(self.http_clients)}"
            )

            # 如果没有客户端了，计划关闭
            if len(self.http_clients) == 0:
                self.logger.info("所有客户端已断开，30秒后将关闭 FFmpeg...")
                await asyncio.sleep(30)
                if len(self.http_clients) == 0 and self.recorder.is_running():
                    await asyncio.to_thread(self.recorder.stop)

        return response

    async def handle_ws_client(self, websocket: WebSocketServerProtocol, path: str = "") -> None:
        """处理 WebSocket 客户端（备用）"""
        self.logger.info("📡 WebSocket 客户端连接")

        # 启动 FFmpeg（如果未运行）
        if not self.recorder.is_running():
            await asyncio.to_thread(self.recorder.start)

        self.ws_clients.append(websocket)
        self.logger.info(
            f"WebSocket 客户端已添加，当前客户端数: {len(self.ws_clients)}"
        )

        try:
            await websocket.wait_closed()
        finally:
            self.ws_clients.remove(websocket)
            self.logger.info(
                f"WebSocket 客户端已移除，剩余客户端: {len(self.ws_clients)}"
            )

    async def stream_loop(self) -> None:
        """流转发循环（仅用于 WebSocket）"""
        while True:
            # 只在有 HTTP 客户端时启动 FFmpeg
            if len(self.http_clients) > 0 and not self.recorder.is_running():
                await asyncio.to_thread(self.recorder.start)

            # 读取数据并发送给 WebSocket 客户端
            if len(self.ws_clients) > 0 and self.recorder.is_running():
                try:
                    data = await asyncio.to_thread(self.recorder.read_output, 8192)
                    if data:
                        # 发送给所有 WebSocket 客户端
                        for ws in self.ws_clients[:]:  # 创建副本
                            try:
                                await ws.send(data)
                            except Exception:
                                self.ws_clients.remove(ws)
                except Exception as e:
                    self.logger.error(f"流转发错误: {e}")

            await asyncio.sleep(0.01)
