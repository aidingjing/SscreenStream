[根目录](../../CLAUDE.md) > [src](../) > **streamer**

---

# 推流模块 (streamer)

## 模块职责

推流模块负责：
1. 监听客户端 WebSocket 连接 (`WebSocketStreamer`)
2. 管理所有连接的客户端 (`ClientManager`)
3. 从录制器读取数据并分发给所有客户端 (`StreamForwarder`)
4. 按需启动/停止 FFmpeg（延迟启动策略）

## 入口与启动

### 主要入口点

**WebSocketStreamer 类** (`ws_server.py`)
- WebSocket 服务器核心
- 按需启动 FFmpeg（第一个客户端连接时启动）
- 超时关闭 FFmpeg（所有客户端断开后）
- 协调客户端管理和流转发

**ClientManager 类** (`client_manager.py`)
- 管理所有 WebSocket 客户端连接
- 维护客户端列表和连接信息
- 提供广播功能
- 生成唯一客户端 ID

**StreamForwarder 类** (`stream_forwarder.py`)
- 从录制器读取视频数据
- 将数据分发给所有客户端
- 异步读取和转发
- 统计转发字节数和包数

### 初始化流程

```python
# 1. 创建配置对象
config = ConfigParser("config/config.example.json").parse()

# 2. 创建日志记录器
logger = setup_logger(config)

# 3. 创建录制器（不启动 FFmpeg）
recorder = FFmpegRecorder(config, logger)

# 4. 创建 WebSocket 服务器
server = WebSocketStreamer(config, recorder, logger)

# 5. 启动服务器（⚠️ 只启动监听，不启动 FFmpeg）
await server.start()

# 6. 等待客户端连接（FFmpeg 会在第一个客户端连接时自动启动）
await wait_for_shutdown()
```

## 对外接口

### WebSocketStreamer

**方法签名：**
```python
def __init__(self, config: ConfigData, recorder: BaseRecorder, logger: logging.Logger)
async def start(self) -> None
async def stop(self) -> None
async def _handle_client(self, websocket: WebSocketServerProtocol, path: str = "") -> None
def get_status(self) -> dict
```

**职责：**
- 监听客户端连接
- 按需启动/停止 FFmpeg
- 协调客户端管理和流转发
- 实现超时关闭机制

**核心逻辑 - 延迟启动：**
```python
async def _handle_client(self, websocket, path=""):
    # 客户端连接时
    self.client_manager.add_client(client_id, websocket)

    # 如果是第一个客户端，启动 FFmpeg
    if self.client_manager.get_client_count() == 1:
        await self._start_ffmpeg_if_needed()

    # 取消关闭定时器（如果有）
    await self._cancel_shutdown_schedule()

    # 等待客户端断开（阻塞）
    await websocket.wait_closed()

    # 客户端断开时
    self.client_manager.remove_client(client_id)

    # 如果没有客户端了，计划关闭 FFmpeg
    if self.client_manager.is_empty():
        await self._schedule_ffmpeg_shutdown()
```

### ClientManager

**方法签名：**
```python
def __init__(self, shutdown_timeout: int, logger: logging.Logger)
def add_client(self, client_id: str, websocket: WebSocketServerProtocol) -> ConnectionInfo
def remove_client(self, client_id: str) -> None
def get_client(self, client_id: str) -> Optional[ConnectionInfo]
def get_all_clients(self) -> Dict[str, ConnectionInfo]
def get_client_count(self) -> int
async def broadcast(self, data: bytes) -> None
def is_empty(self) -> bool
def generate_client_id(self) -> str
def clear_all(self) -> None
def get_client_ids(self) -> List[str]
```

**职责：**
- 管理客户端连接集合
- 维护客户端连接信息
- 提供广播功能
- 统计客户端数量

### StreamForwarder

**方法签名：**
```python
def __init__(self, recorder: BaseRecorder, client_manager: ClientManager, logger: logging.Logger)
async def start_forwarding(self) -> None
async def stop_forwarding(self) -> None
def get_statistics(self) -> dict
```

**职责：**
- 从录制器读取视频数据
- 将数据分发给所有客户端
- 异步读取（使用 `asyncio.to_thread`）
- 统计转发字节数和包数

## 关键依赖与配置

### 内部依赖

- `src/recorder/base_recorder.py` - `BaseRecorder` 录制器接口
- `src/config/config_parser.py` - `ConfigData` 配置数据

### 外部依赖

- `websockets==11.0` - WebSocket 服务器
- `asyncio` - 异步 IO
- `uuid` - 生成客户端 ID
- `dataclasses` - `ConnectionInfo` 数据类

### 配置参数

从 `ConfigData` 读取：
- `server_port` - WebSocket 服务器端口（默认 8765）
- `host` - 监听地址（默认 "0.0.0.0"）
- `shutdown_timeout` - 客户端断开后关闭超时（默认 30 秒）

## 数据模型

### ConnectionInfo (dataclass)

```python
@dataclass
class ConnectionInfo:
    client_id: str
    websocket: WebSocketServerProtocol
    connect_time: datetime
    is_authenticated: bool = True
```

**使用示例：**
```python
conn_info = client_manager.get_client(client_id)
if conn_info:
    print(f"客户端 ID: {conn_info.client_id}")
    print(f"连接时间: {conn_info.connect_time}")
    print(f"已认证: {conn_info.is_authenticated}")
```

## 核心工作流

### 完整生命周期

```
1. 程序启动
   └─> 启动 WebSocket 监听（不启动 FFmpeg）

2. 第一个客户端连接
   ├─> 添加客户端到管理器
   ├─> 启动 FFmpeg 录制
   ├─> 启动流转发器
   └─> 开始推流

3. 更多客户端连接
   ├─> 添加客户端到管理器
   └─> 复用现有 FFmpeg 进程

4. 客户端陆续断开
   ├─> 从管理器移除客户端
   └─> 继续推流

5. 最后一个客户端断开
   ├─> 从管理器移除客户端
   ├─> 启动关闭定时器（默认 30 秒）
   └─> 等待超时或新客户端连接

6a. 超时后（无新客户端）
    ├─> 停止流转发器
    ├─> 停止 FFmpeg
    └─> 返回监听状态

6b. 超时前有新客户端
    ├─> 取消关闭定时器
    └─> 继续推流

7. 循环
    └─> 等待下次客户端连接
```

### 数据流向

```
FFmpeg 进程 (stdout)
    ↓
ProcessManager.read_output()
    ↓
FFmpegRecorder.read_output()
    ↓
StreamForwarder._read_and_forward()
    ├─> asyncio.to_thread(recorder.read_output, 8192)
    └─> ClientManager.broadcast(data)
         ↓
         向所有客户端发送
         ↓
所有 WebSocket 客户端
```

## 设计模式

### 观察者模式

**客户端连接状态变化触发 FFmpeg 启动/停止：**
```python
# 事件：客户端连接
if client_count == 1:
    await self._start_ffmpeg_if_needed()  # 响应：启动 FFmpeg

# 事件：客户端断开
if is_empty():
    await self._schedule_ffmpeg_shutdown()  # 响应：计划关闭 FFmpeg
```

### 责任链模式

**数据流经多个处理器：**
```
FFmpeg → ProcessManager → FFmpegRecorder → StreamForwarder → ClientManager → WebSocket Clients
```

## 测试与质量

### 测试文件

- `tests/unit/test_streamer.py` - 单元测试

### 测试覆盖

- WebSocket 服务器启动/停止测试
- 客户端连接/断开测试
- 延迟启动逻辑测试
- 超时关闭机制测试
- 流转发测试
- 客户端管理测试
- 广播功能测试

### 测试策略

**Mock 对象隔离：**
- Mock `websockets` 库避免真实网络连接
- Mock `BaseRecorder` 避免启动 FFmpeg
- 使用 `pytest-asyncio` 进行异步测试

**示例测试：**
```python
@pytest.mark.asyncio
async def test_client_connect_starts_ffmpeg(mock_server):
    """测试客户端连接时启动 FFmpeg"""
    # Arrange
    mock_websocket = MagicMock()
    mock_recorder = mock_server.recorder
    mock_recorder.is_running.return_value = False
    mock_recorder.start.return_value = RecorderState(True, datetime.now(), 1)

    # Act
    await mock_server._handle_client(mock_websocket)

    # Assert
    mock_recorder.start.assert_called_once()
```

### 运行测试

```bash
# 单元测试
pytest tests/unit/test_streamer.py

# 带覆盖率
pytest --cov=src/streamer tests/unit/test_streamer.py

# 异步测试
pytest -m asyncio tests/unit/test_streamer.py
```

## 常见问题 (FAQ)

### Q1: 如何修改 WebSocket 监听地址？

A: 修改配置文件：
```json
{
  "server": {
    "host": "127.0.0.1",  // 只监听本地
    "port": 8765
  }
}
```

### Q2: 如何实现客户端认证？

A: 在 `ClientManager` 中添加认证逻辑：
```python
async def _handle_client(self, websocket, path=""):
    # 检查认证令牌
    token = await websocket.recv()
    if not self._authenticate(token):
        await websocket.close(code=1008, reason="Unauthorized")
        return

    # 添加已认证的客户端
    client_id = self.client_manager.generate_client_id()
    conn_info = ConnectionInfo(
        client_id=client_id,
        websocket=websocket,
        connect_time=datetime.now(),
        is_authenticated=True
    )
```

### Q3: 如何限制最大客户端数量？

A: 在 `ClientManager` 中添加限制：
```python
def __init__(self, shutdown_timeout: int, max_clients: int, logger: logging.Logger):
    self.max_clients = max_clients
    # ...

def add_client(self, client_id, websocket):
    if len(self.clients) >= self.max_clients:
        raise StreamError("已达到最大客户端连接数")
    # ...
```

### Q4: 如何实现客户端心跳检测？

A: 在 `_handle_client` 中添加心跳逻辑：
```python
async def _handle_client(self, websocket, path=""):
    # 启动心跳任务
    heartbeat_task = asyncio.create_task(self._send_heartbeat(websocket))

    try:
        await websocket.wait_closed()
    finally:
        heartbeat_task.cancel()

async def _send_heartbeat(self, websocket):
    """发送心跳"""
    try:
        while True:
            await asyncio.sleep(30)  # 每 30 秒发送一次
            await websocket.ping()
    except asyncio.CancelledError:
        pass
```

### Q5: 如何实现数据压缩？

A: 在 `StreamForwarder` 中添加压缩：
```python
import zlib

async def _read_and_forward(self) -> None:
    while self._is_running:
        data = await asyncio.to_thread(self.recorder.read_output, 8192)

        # 压缩数据
        compressed = zlib.compress(data, level=3)

        # 添加压缩标志
        frame = b'\x01' + len(compressed).to_bytes(4, 'big') + compressed

        await self.client_manager.broadcast(frame)
```

### Q6: 如何支持多种推流协议（如 RTSP、RTMP）？

A: 创建新的服务器类实现相同接口：
```python
class RTSPStreamer:
    """RTSP 推流服务器"""

    def __init__(self, config, recorder, logger):
        self.config = config
        self.recorder = recorder
        self.logger = logger

    async def start(self):
        # 启动 RTSP 服务器
        pass

    async def stop(self):
        # 停止 RTSP 服务器
        pass
```

## 相关文件清单

### 核心文件

- `src/streamer/__init__.py` - 模块初始化
- `src/streamer/ws_server.py` - WebSocket 服务器 (260 行)
- `src/streamer/client_manager.py` - 客户端管理器 (185 行)
- `src/streamer/stream_forwarder.py` - 流转发器 (164 行)

### 测试文件

- `tests/unit/test_streamer.py` - 单元测试
- `tests/conftest.py` - 测试配置和 fixtures

## 变更记录 (Changelog)

### 2025-01-09
- 初始化模块文档
- 记录所有接口和工作流
- 整理延迟启动策略和超时关闭机制
- 添加扩展 FAQ
