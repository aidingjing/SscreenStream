[根目录](../../CLAUDE.md) > [src](../) > **recorder**

---

# 录制模块 (recorder)

## 模块职责

录制模块是 FFmpeg 交互的核心，负责：
1. 定义录制器抽象接口 (`BaseRecorder`)
2. 实现 FFmpeg 录制器 (`FFmpegRecorder`)
3. 构建 FFmpeg 命令行参数 (`FFmpegCommandBuilder`)
4. 提供窗口查找辅助功能 (`WindowHelper`)

## 入口与启动

### 主要入口点

**BaseRecorder 抽象类** (`base_recorder.py`)
- 定义所有录制器必须实现的通用接口
- 使用抽象基类 (ABC) 强制子类实现方法

**FFmpegRecorder 类** (`ffmpeg_recorder.py`)
- 实现 `BaseRecorder` 接口
- 组合 `ProcessManager` 和 `HealthMonitor`
- 通过依赖注入接收 `FFmpegCommandBuilder`

**FFmpegCommandBuilder 类** (`ffmpeg_builder.py`)
- 根据配置构建 FFmpeg 命令行参数
- 支持多种录制源类型（屏幕、窗口、区域）
- 策略模式：通过 `__call__` 方法适配 `ProcessManager` 接口

### 初始化流程

```python
# 1. 创建配置对象
config = ConfigParser("config/config.example.json").parse()

# 2. 创建日志记录器
logger = setup_logger(config)

# 3. 创建录制器（不启动 FFmpeg）
recorder = FFmpegRecorder(config, logger)

# 4. 设置窗口助手（窗口录制时需要）
if config.source.source.type == "window":
    window_helper = WindowHelper(logger)
    recorder.command_builder.window_helper = window_helper

# 5. 启动录制（在 WebSocketStreamer 中按需启动）
state = recorder.start()
```

## 对外接口

### BaseRecorder (抽象接口)

**抽象方法：**

```python
@abstractmethod
def start(self) -> RecorderState:
    """启动录制

    Returns:
        RecorderState: 录制器状态

    Raises:
        RecorderStartupError: 启动失败
    """
    pass

@abstractmethod
def stop(self, timeout: int = 5) -> bool:
    """停止录制

    Args:
        timeout: 等待超时时间（秒）

    Returns:
        bool: 是否成功停止
    """
    pass

@abstractmethod
def get_state(self) -> RecorderState:
    """获取当前状态

    Returns:
        RecorderState: 录制器状态
    """
    pass

@abstractmethod
def is_running(self) -> bool:
    """检查是否正在录制

    Returns:
        bool: 是否运行中
    """
    pass

@abstractmethod
def read_output(self, size: int = -1) -> bytes:
    """读取录制输出数据

    Args:
        size: 读取字节数

    Returns:
        bytes: 视频数据
    """
    pass
```

### FFmpegRecorder

**方法签名：**
```python
def __init__(self, config: ConfigData, logger: logging.Logger)
def start(self) -> RecorderState
def stop(self, timeout: int = 5) -> bool
def get_state(self) -> RecorderState
def is_running(self) -> bool
def read_output(self, size: int = 4096) -> bytes
def handle_crash(self) -> bool
def get_health_monitor(self) -> HealthMonitor
```

**职责：**
- 实现 `BaseRecorder` 接口
- 组合 `ProcessManager` 和 `HealthMonitor`
- 委托命令构建给 `FFmpegCommandBuilder`
- 处理崩溃和重启逻辑

### FFmpegCommandBuilder

**方法签名：**
```python
def __init__(self, config: ConfigData, window_helper: Optional["WindowHelper"] = None)
def build(self) -> List[str]
def __call__(self) -> List[str]  # 使对象可调用
```

**职责：**
- 根据配置构建 FFmpeg 命令行参数
- 支持多种录制源类型
- 通过 `__call__` 适配 `ProcessManager` 的策略接口

**命令结构：**
```bash
ffmpeg.exe \
  -f gdigrab \
  -framerate 30 \
  -rtbufsize 100M \
  -i desktop \
  -c:v libx264 \
  -preset ultrafast \
  -tune zerolatency \
  -profile:v baseline \
  -level 3.1 \
  -pix_fmt yuv420p \
  -b:v 2M \
  -g 30 \
  -c:a aac \
  -b:a 128k \
  -ar 44100 \
  -f flv \
  -flvflags no_duration_filesize \
  pipe:1
```

## 关键依赖与配置

### 内部依赖

- `src/process/process_manager.py` - `ProcessManager` 进程管理
- `src/process/health_monitor.py` - `HealthMonitor` 健康监控
- `src/config/config_parser.py` - `ConfigData` 配置数据
- `src/exceptions.py` - `RecorderStartupError` 异常类

### 外部依赖

- `subprocess` - FFmpeg 进程启动
- `threading` - 输出读取线程
- `typing` - 类型注解

### FFmpeg 依赖

- **FFmpeg 可执行文件**：必须手动放置在 `ffmpeg/` 目录下
- **gdigrab**：Windows 屏幕捕获引擎（仅支持 Windows）
- **编码器**：libx264 (视频), aac (音频)

### 配置参数

从 `ConfigData` 读取：
- `ffmpeg_path` - FFmpeg 可执行文件路径
- `video_codec` - 视频编码器
- `audio_codec` - 音频编码器
- `bitrate` - 视频比特率
- `framerate` - 帧率
- `preset` - 编码速度预设
- `tune` - 编码调优
- `source` - 录制源配置
- `crash_threshold` - 崩溃阈值
- `crash_window` - 崩溃时间窗口

## 数据模型

### RecorderState (dataclass)

```python
@dataclass
class RecorderState:
    is_running: bool
    start_time: Optional[datetime]
    client_count: int
```

### ProcessState (组合使用)

```python
class ProcessState:
    is_running: bool
    pid: Optional[int]
    start_time: Optional[datetime]
    client_count: int
```

## 设计模式

### 策略模式

**FFmpegCommandBuilder** 作为策略注入到 `ProcessManager`：
```python
# ProcessManager 接收命令构建函数
process_manager = ProcessManager(
    cmd_builder=self.command_builder.build,  # 策略注入
    logger=logger
)
```

### 组合模式

**FFmpegRecorder** 组合多个组件：
```python
class FFmpegRecorder(BaseRecorder):
    def __init__(self, config, logger):
        self.command_builder = FFmpegCommandBuilder(config)  # 命令构建策略
        self.process_manager = ProcessManager(...)            # 进程管理
        self.health_monitor = HealthMonitor(...)              # 健康监控
```

## 测试与质量

### 测试文件

- `tests/unit/test_recorder.py` - 单元测试

### 测试覆盖

- FFmpeg 录制器启动/停止测试
- 命令构建测试（不同录制源）
- 状态查询测试
- 输出读取测试
- 崩溃处理测试

### 测试策略

**Mock 对象隔离：**
- Mock `ProcessManager` 避免启动真实 FFmpeg
- Mock `WindowHelper` 避免操作系统窗口 API 调用
- 使用 `pytest-mock` 的 `mocker` fixture

**示例测试：**
```python
def test_recorder_start(mock_recorder):
    """测试录制器启动"""
    # Arrange
    mock_process_manager = mock_recorder._mock_process_manager

    # Act
    state = mock_recorder.start()

    # Assert
    assert state.is_running
    assert state.start_time is not None
    mock_process_manager.start.assert_called_once()
```

### 运行测试

```bash
# 单元测试
pytest tests/unit/test_recorder.py

# 带覆盖率
pytest --cov=src/recorder tests/unit/test_recorder.py

# 单个测试类
pytest tests/unit/test_recorder.py::TestFFmpegRecorder

# 单个测试方法
pytest tests/unit/test_recorder.py::TestFFmpegRecorder::test_start
```

## 常见问题 (FAQ)

### Q1: FFmpeg 启动失败怎么办？

A: 检查：
1. FFmpeg 可执行文件是否在 `ffmpeg/` 目录
2. 配置文件中的 `ffmpeg_path` 是否正确
3. FFmpeg 版本是否支持 gdigrab
4. 查看日志文件了解详细错误

### Q2: 如何添加新的录制源类型？

A: 步骤如下：
1. 在 `config_parser.py` 中添加新的配置 dataclass (如 `CameraSourceConfig`)
2. 在 `config_validator.py` 中添加验证逻辑
3. 在 `ffmpeg_builder.py` 的 `_build_input_args()` 中添加新分支
4. 更新 `WindowHelper`（如需要窗口查找功能）
5. 添加测试

**示例：添加摄像头录制**
```python
# 1. config_parser.py
@dataclass
class CameraSourceConfig:
    type: str
    device_name: str
    resolution: Optional[str] = None

# 2. ffmpeg_builder.py
def _build_input_args(self) -> List[str]:
    # ...
    elif source_type == "camera":
        args.extend(["-f", "dshow", "-i", f"video={config.source.device_name}"])
```

### Q3: 如何修改 FFmpeg 编码参数？

A: 修改 `ffmpeg_builder.py` 中的构建方法：
```python
def _build_video_args(self) -> List[str]:
    args = []
    args.extend(["-c:v", self.config.video_codec])
    args.extend(["-preset", self.config.preset])
    # 添加自定义参数
    args.extend(["-crf", "23"])  # 恒定质量因子
    return args
```

### Q4: 如何实现硬件编码？

A: 修改命令构建器使用硬件编码器：
```python
# 在配置中设置
"video_codec": "h264_nvenc"  # NVIDIA
# 或 "video_codec": "h264_qsv"  # Intel Quick Sync

# 在 ffmpeg_builder.py 中调整参数
def _build_video_args(self) -> List[str]:
    args = []
    if self.config.video_codec == "h264_nvenc":
        args.extend(["-c:v", "h264_nvenc"])
        args.extend(["-preset", "p1"])  # NVmpeg 预设
        args.extend(["-tune", "ll"])    # 低延迟
    else:
        # 软件编码
        args.extend(["-c:v", self.config.video_codec])
        args.extend(["-preset", self.config.preset])
    return args
```

### Q5: 如何实现录制回放（录制到文件）？

A: 创建新的录制器实现 `FileRecorder`：
```python
class FileRecorder(BaseRecorder):
    def __init__(self, config, logger, output_path):
        self.output_path = output_path
        # ...

    def start(self) -> RecorderState:
        # 修改命令构建器，输出到文件而非 stdout
        cmd = self.command_builder.build()
        cmd[-1] = self.output_path  # 替换 pipe:1
        # ...
```

## 相关文件清单

### 核心文件

- `src/recorder/__init__.py` - 模块初始化
- `src/recorder/base_recorder.py` - 录制器抽象接口 (85 行)
- `src/recorder/ffmpeg_recorder.py` - FFmpeg 录制器实现 (181 行)
- `src/recorder/ffmpeg_builder.py` - FFmpeg 命令构建器 (277 行)
- `src/recorder/window_helper.py` - 窗口查找辅助工具

### 测试文件

- `tests/unit/test_recorder.py` - 单元测试
- `tests/conftest.py` - 测试配置和 fixtures

## 变更记录 (Changelog)

### 2025-01-09
- 初始化模块文档
- 记录所有接口和数据模型
- 整理设计模式和扩展指南
