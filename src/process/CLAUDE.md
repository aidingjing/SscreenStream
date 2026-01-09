[根目录](../../CLAUDE.md) > [src](../) > **process**

---

# 进程管理模块 (process)

## 模块职责

进程管理模块负责：
1. 管理任意子进程的生命周期（启动、停止、状态查询）
2. 监控进程健康状态（崩溃检测、重启策略）
3. 提供通用的进程管理接口（不依赖 FFmpeg）
4. 支持策略注入（命令构建器可定制）

## 入口与启动

### 主要入口点

**ProcessManager 类** (`process_manager.py`)
- 通用的子进程管理器
- 通过依赖注入接收命令构建器
- 支持优雅终止和强制终止
- 提供非阻塞的输出读取

**HealthMonitor 类** (`health_monitor.py`)
- 通用的健康监控器
- 滑动窗口算法记录崩溃次数
- 自动清理超出时间窗口的记录
- 判断是否应该重启

### 初始化流程

```python
# 1. 创建命令构建器（策略）
cmd_builder = lambda: ["ffmpeg.exe", "-f", "gdigrab", "-i", "desktop", ...]

# 2. 创建进程管理器
process_manager = ProcessManager(
    cmd_builder=cmd_builder,  # 注入命令构建策略
    logger=logger
)

# 3. 创建健康监控器
health_monitor = HealthMonitor(
    threshold=3,    # 崩溃阈值
    window=60,      # 时间窗口（秒）
    logger=logger
)

# 4. 启动进程
state = process_manager.start()
print(f"进程已启动，PID: {state.pid}")

# 5. 读取输出（非阻塞）
data = process_manager.read_output(4096)

# 6. 停止进程
success = process_manager.stop(timeout=5)
```

## 对外接口

### ProcessManager

**方法签名：**
```python
def __init__(self, cmd_builder: Callable[[], List[str]], logger: logging.Logger)
def start(self) -> ProcessState
def stop(self, timeout: int = 5) -> bool
def get_state(self) -> ProcessState
def is_running(self) -> bool
def read_output(self, size: int = 4096) -> bytes
def read_stderr(self) -> str
def get_return_code(self) -> Optional[int]
```

**职责：**
- 管理子进程生命周期
- 启动进程（使用 `subprocess.Popen`）
- 停止进程（先 `terminate()`，超时后 `kill()`）
- 非阻塞读取 stdout 和 stderr
- 查询进程状态和返回码

**策略注入：**
```python
# ProcessManager 通过构造函数注入命令构建策略
def __init__(self, cmd_builder: Callable[[], List[str]], logger: logging.Logger):
    self.cmd_builder = cmd_builder  # 策略注入

# 调用策略获取命令
cmd = self.cmd_builder()  # 返回 ["ffmpeg.exe", ...]
```

### HealthMonitor

**方法签名：**
```python
def __init__(self, threshold: int, window: int, logger: logging.Logger)
def record_crash(self) -> None
def should_restart(self) -> bool
def is_threshold_exceeded(self) -> bool
def reset(self) -> None
def get_crash_count(self) -> int
```

**职责：**
- 记录进程崩溃时间和次数
- 判断是否应该重启（崩溃次数未超阈值）
- 自动清理超出时间窗口的崩溃记录
- 进程正常停止后重置监控状态

**滑动窗口算法：**
```python
def _cleanup_old_crashes(self) -> None:
    """清理超出时间窗口的崩溃记录"""
    cutoff = datetime.now() - timedelta(seconds=self.window)
    self.crash_history = [
        crash_time for crash_time in self.crash_history
        if crash_time > cutoff
    ]
```

## 关键依赖与配置

### 内部依赖

- `src/exceptions.py` - `ProcessManagerError` 异常类

### 外部依赖

- `subprocess` - 子进程管理
- `threading` - 读取线程（可选）
- `datetime`, `timedelta` - 时间窗口计算
- `typing` - 类型注解

### 配置参数

**ProcessManager：**
- 无直接配置，通过注入的 `cmd_builder` 获取命令

**HealthMonitor：**
- `threshold` - 崩溃阈值（默认 3 次）
- `window` - 时间窗口（默认 60 秒）

## 数据模型

### ProcessState (dataclass)

```python
class ProcessState:
    is_running: bool
    pid: Optional[int]
    start_time: Optional[datetime]
    client_count: int = 0
```

**使用示例：**
```python
state = process_manager.get_state()
if state.is_running:
    print(f"进程运行中，PID: {state.pid}, 启动时间: {state.start_time}")
```

### 崩溃记录

```python
crash_history: List[datetime]  # 崩溃时间列表
```

**滑动窗口示例：**
```
当前时间: 2025-01-09 12:00:00
时间窗口: 60 秒
崩溃记录: [11:59:30, 11:59:45, 12:00:00]  # 3 次崩溃
阈值: 3 次
结果: 超过阈值，不应重启
```

## 核心算法

### 进程停止策略

**两阶段终止：**
```python
def stop(self, timeout: int = 5) -> bool:
    # 阶段 1: 优雅终止（SIGTERM）
    self.process.terminate()

    try:
        # 等待进程退出
        self.process.wait(timeout=timeout)
        return True  # 成功
    except subprocess.TimeoutExpired:
        # 阶段 2: 强制终止（SIGKILL）
        self.process.kill()
        self.process.wait(timeout=2)
        return True  # 强制终止成功
```

### 滑动窗口崩溃检测

**算法：**
1. 每次崩溃时记录当前时间
2. 清理超出时间窗口的旧记录
3. 检查剩余记录数是否超过阈值
4. 如果超过阈值，返回 `should_restart=False`

**时间线示例：**
```
时间窗口: 60 秒
阈值: 3 次

12:00:00  崩溃 #1 → 记录: [12:00:00] → 计数: 1 → 可以重启
12:00:20  崩溃 #2 → 记录: [12:00:00, 12:00:20] → 计数: 2 → 可以重启
12:00:40  崩溃 #3 → 记录: [12:00:00, 12:00:20, 12:00:40] → 计数: 3 → 可以重启
12:00:50  崩溃 #4 → 记录: [12:00:00, 12:00:20, 12:00:40, 12:00:50] → 计数: 4 → 停止服务
12:01:10  崩溃 #5 → 记录: [12:00:50, 12:01:10] → 计数: 2 → 可以重启（旧记录被清理）
```

### 非阻塞输出读取

**跨平台兼容：**
```python
def read_output(self, size: int = 4096) -> bytes:
    fd = self.process.stdout.fileno()

    try:
        # Unix/Linux: 使用 os.read 非阻塞读取
        data = os.read(fd, size)
        return data if data else b''
    except BlockingIOError:
        return b''
    except OSError:
        # Windows: 不支持非阻塞，使用 read1
        data = self.process.stdout.read1(size)
        return data if data else b''
```

## 测试与质量

### 测试文件

- `tests/unit/test_process.py` - 单元测试

### 测试覆盖

- 进程启动/停止测试
- 超时终止测试
- 状态查询测试
- 输出读取测试
- 崩溃监控测试（滑动窗口算法）
- 阈值超限测试

### 测试策略

**Mock 对象隔离：**
- Mock `subprocess.Popen` 避免启动真实进程
- 使用 `pytest-mock` 的 `mocker` fixture

**示例测试：**
```python
def test_process_start(mocker, mock_logger):
    """测试进程启动"""
    # Arrange
    mock_popen = mocker.MagicMock()
    mock_popen.pid = 12345
    mock_popen.poll.return_value = None  # 进程运行中
    mocker.patch('subprocess.Popen', return_value=mock_popen)

    cmd_builder = lambda: ["ffmpeg.exe", "-i", "desktop"]
    manager = ProcessManager(cmd_builder, mock_logger)

    # Act
    state = manager.start()

    # Assert
    assert state.is_running
    assert state.pid == 12345
    subprocess.Popen.assert_called_once_with(
        cmd_builder(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0
    )
```

### 运行测试

```bash
# 单元测试
pytest tests/unit/test_process.py

# 带覆盖率
pytest --cov=src/process tests/unit/test_process.py

# 单个测试类
pytest tests/unit/test_process.py::TestProcessManager

# 单个测试方法
pytest tests/unit/test_process.py::TestProcessManager::test_start
```

## 常见问题 (FAQ)

### Q1: 如何自定义命令构建器？

A: 提供一个返回命令行列表的可调用对象：
```python
# 方式 1: 使用 lambda
cmd_builder = lambda: ["ffmpeg.exe", "-i", "input.mp4", "pipe:1"]

# 方式 2: 使用函数
def build_cmd():
    return ["ffmpeg.exe", "-i", "input.mp4", "pipe:1"]

# 方式 3: 使用可调用类
class MyCommandBuilder:
    def __call__(self):
        return ["ffmpeg.exe", "-i", "input.mp4", "pipe:1"]

# 注入到 ProcessManager
manager = ProcessManager(cmd_builder=cmd_builder, logger=logger)
```

### Q2: 如何实现指数退避重启？

A: 在 `FFmpegRecorder.handle_crash()` 中添加退避逻辑：
```python
import asyncio

async def restart_with_backoff(self, attempt: int):
    """指数退避重启"""
    wait_time = min(2 ** attempt, 60)  # 最多等待 60 秒
    await asyncio.sleep(wait_time)
    await asyncio.to_thread(self.recorder.start)
```

### Q3: 如何处理进程崩溃时的输出日志？

A: 在 `ProcessManager` 中添加 stderr 日志记录：
```python
def read_stderr(self) -> str:
    """读取进程错误输出"""
    if not self.process or not self.process.stderr:
        return ""

    data = self.process.stderr.read(4096)
    if data:
        error_msg = data.decode('utf-8', errors='ignore')
        self.logger.error(f"FFmpeg stderr: {error_msg}")
        return error_msg
    return ""
```

### Q4: 如何实现进程池（多个 FFmpeg 进程）？

A: 扩展 `ProcessManager` 支持多进程：
```python
class ProcessPool:
    def __init__(self, pool_size: int, cmd_builder, logger):
        self.pool_size = pool_size
        self.managers = [
            ProcessManager(cmd_builder, logger)
            for _ in range(pool_size)
        ]

    def start_all(self) -> List[ProcessState]:
        return [manager.start() for manager in self.managers]

    def stop_all(self) -> List[bool]:
        return [manager.stop() for manager in self.managers]
```

### Q5: 如何监控进程资源使用（CPU、内存）？

A: 使用 `psutil` 库：
```python
import psutil

def get_resource_usage(self):
    """获取进程资源使用情况"""
    if not self.process:
        return None

    try:
        process = psutil.Process(self.process.pid)
        return {
            "cpu_percent": process.cpu_percent(),
            "memory_mb": process.memory_info().rss / 1024 / 1024,
            "num_threads": process.num_threads()
        }
    except psutil.NoSuchProcess:
        return None
```

## 相关文件清单

### 核心文件

- `src/process/__init__.py` - 模块初始化
- `src/process/process_manager.py` - 进程管理器 (268 行)
- `src/process/health_monitor.py` - 健康监控器 (108 行)

### 测试文件

- `tests/unit/test_process.py` - 单元测试
- `tests/conftest.py` - 测试配置和 fixtures

## 变更记录 (Changelog)

### 2025-01-09
- 初始化模块文档
- 记录所有接口和算法
- 整理滑动窗口崩溃检测策略
- 添加扩展 FAQ
