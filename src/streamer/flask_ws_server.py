"""
Flask WebSocket 流媒体服务器

使用 Flask + flask-sock 实现 WebSocket-FLV 推流
"""

import asyncio
import logging
from typing import Optional, Set
from flask import Flask
from flask_sock import Sock
from simple_websocket import Server

from src.recorder.base_recorder import BaseRecorder
from src.config.config_parser import ConfigData


class FlaskWebSocketStreamer:
    """Flask WebSocket 流媒体服务器

    职责：
    1. 提供 WebSocket 连接（/ws）
    2. 按需启动/停止 FFmpeg
    3. 转发 FLV 视频流给所有客户端
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

        # 创建 Flask 应用
        self.app = Flask(__name__)
        self.app.config['SOCK_SERVER_OPTIONS'] = {'ping_interval': 25}

        # 创建 WebSocket 扩展
        self.sock = Sock(self.app)

        # WebSocket 连接集合
        self.clients: Set[Server] = set()

        # 流转发任务
        self._forwarding_task: Optional[asyncio.Task] = None
        self._is_running = False

        # 注册路由
        self._setup_routes()

        self.logger.info("Flask WebSocket 推流服务器已初始化")

    def _setup_routes(self):
        """设置路由"""

        @self.app.route('/')
        def index():
            return """
            <html>
            <head><title>WebSocket Screen Streamer</title></head>
            <body>
                <h1>WebSocket-FLV 流媒体服务器</h1>
                <p>WebSocket 端点: <strong>ws://HOST:8765/ws</strong></p>
                <p>使用 flv.js 连接到此端点</p>
            </body>
            </html>
            """

        @self.sock.route('/ws')
        def websocket_connection(ws: Server):
            """处理 WebSocket 连接"""
            self.logger.info("🔗 客户端连接")

            # 添加客户端
            self.clients.add(ws)
            self.logger.info(f"客户端已添加，当前连接数: {len(self.clients)}")

            # 启动 FFmpeg（如果未运行）
            if not self.recorder.is_running() and len(self.clients) == 1:
                self.logger.info("🎬 启动 FFmpeg 录制...")
                self.recorder.start()
                self.logger.info("✅ FFmpeg 已启动")

                # 启动流转发任务
                if not self._is_running:
                    self._start_forwarding()

            try:
                # 保持连接，处理客户端消息（如果有）
                while True:
                    message = ws.receive()
                    if message is None:
                        break
            except Exception as e:
                self.logger.error(f"WebSocket 错误: {e}")
            finally:
                # 移除客户端
                self.clients.discard(ws)
                self.logger.info(f"🔌 客户端断开，剩余客户端: {len(self.clients)}")

                # 如果没有客户端了，计划关闭 FFmpeg
                if len(self.clients) == 0:
                    self.logger.info("⏳ 所有客户端已断开，30 秒后将关闭 FFmpeg...")
                    # 注意：实际超时逻辑在转发任务中处理

    def _start_forwarding(self):
        """启动流转发任务"""
        if self._is_running:
            return

        self._is_running = True
        self.logger.info("启动流转发器...")

        # 在新线程中运行异步任务
        import threading
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        def run_forwarding():
            loop.run_until_complete(self._forwarding_loop())

        thread = threading.Thread(target=run_forwarding, daemon=True)
        thread.start()

    async def _forwarding_loop(self):
        """流转发循环"""
        try:
            last_client_count = 0
            no_client_timer = 0
            log_counter = 0  # 减少日志输出

            while self._is_running:
                client_count = len(self.clients)

                # 检查是否有客户端
                if client_count == 0:
                    # 没有客户端，开始计时
                    if last_client_count > 0:
                        no_client_timer = 0
                        self.logger.info("开始无客户端计时...")

                    no_client_timer += 1

                    # 每 3 秒打印一次日志，而不是每次循环
                    if no_client_timer % 30 == 0:
                        self.logger.info(f"无客户端计时中... {no_client_timer / 10:.1f} 秒")

                    # 30 秒后关闭 FFmpeg
                    if no_client_timer >= 300:  # 30秒 (0.1秒 * 300)
                        self.logger.info("⏰ 超时到达，关闭 FFmpeg...")
                        if self.recorder.is_running():
                            self.recorder.stop()
                        self._is_running = False
                        break

                    await asyncio.sleep(0.1)
                    continue
                else:
                    # 有客户端，重置计时器
                    no_client_timer = 0

                # 读取并转发数据
                if self.recorder.is_running():
                    try:
                        # 在线程池中读取数据（避免阻塞）
                        data = await asyncio.to_thread(
                            self.recorder.read_output,
                            4096  # 读取 4KB 数据块
                        )

                        if data:
                            # 发送给所有客户端
                            dead_clients = set()
                            for client in self.clients:
                                try:
                                    client.send(data)
                                except Exception as e:
                                    self.logger.warning(f"发送失败，移除客户端: {e}")
                                    dead_clients.add(client)

                            # 清理断开的客户端
                            self.clients -= dead_clients

                            # 每 100 个包打印一次统计
                            log_counter += 1
                            if log_counter % 100 == 0:
                                self.logger.debug(f"已转发 {log_counter} 个数据包")

                    except Exception as e:
                        self.logger.error(f"读取失败: {e}")
                        await asyncio.sleep(0.1)

                last_client_count = client_count
                await asyncio.sleep(0.01)

        except Exception as e:
            self.logger.error(f"转发循环异常: {e}", exc_info=True)
        finally:
            self._is_running = False

    def run(self, host: str = "0.0.0.0", port: int = 8765, debug: bool = False):
        """运行 Flask 服务器"""
        self.logger.info(f"启动 Flask WebSocket 服务器，监听 {host}:{port}...")
        self.logger.info(f"WebSocket 端点: ws://{host}:{port}/ws")

        self.app.run(
            host=host,
            port=port,
            debug=debug,
            use_reloader=False,
            threaded=True
        )

    def stop(self):
        """停止服务器"""
        self.logger.info("正在关闭 Flask WebSocket 服务器...")
        self._is_running = False

        if self.recorder.is_running():
            self.recorder.stop()

        self.logger.info("Flask WebSocket 服务器已关闭")
