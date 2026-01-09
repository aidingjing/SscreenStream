[根目录](../../CLAUDE.md) > [src](../) > **config**

---

# 配置管理模块 (config)

## 模块职责

配置管理模块负责：
1. 加载和解析 JSON 配置文件
2. 验证配置参数的合法性和类型
3. 提供默认值和路径解析
4. 导出统一的配置数据对象 (ConfigData)

## 入口与启动

### 主要入口点

**ConfigParser 类** (`config_parser.py`)
- `__init__(config_path: str, validator: Optional[ConfigValidator] = None)` - 初始化解析器
- `parse() -> ConfigData` - 解析配置文件并返回配置对象

**ConfigValidator 类** (`config_validator.py`)
- `validate(config: Dict[str, Any])` - 验证配置字典

### 配置文件结构

```json
{
  "server": {
    "port": 8765,
    "host": "0.0.0.0"
  },
  "ffmpeg": {
    "video_codec": "libx264",
    "audio_codec": "aac",
    "bitrate": "2M",
    "framerate": 30,
    "preset": "ultrafast",
    "tune": "zerolatency"
  },
  "source": {
    "type": "screen|window|window_region",
    "display_index": 1,
    "window_title": "Notepad",
    "region": {"x": 0, "y": 0, "width": 1920, "height": 1080}
  },
  "process": {
    "crash_threshold": 3,
    "crash_window": 60,
    "shutdown_timeout": 30
  },
  "logging": {
    "level": "INFO",
    "file": "screen-streamer.log"
  }
}
```

## 对外接口

### ConfigParser

**方法签名：**
```python
def parse(self) -> ConfigData
```

**职责：**
1. 加载 JSON 文件
2. 应用默认值
3. 解析相对路径为绝对路径
4. 验证配置
5. 转换为 ConfigData 对象

**返回值：**
- `ConfigData` - 包含所有配置参数的 dataclass 对象

**异常：**
- `FileNotFoundError` - 配置文件不存在
- `json.JSONDecodeError` - JSON 格式错误
- `ConfigValidationError` - 配置验证失败

### ConfigValidator

**方法签名：**
```python
def validate(self, config: Dict[str, Any]) -> None
```

**验证规则：**
- 服务器端口：1024-65535
- 视频编码器：libx264, libx265, mpeg4, vp8, vp9
- 音频编码器：aac, mp3, libopus, pcm_s16le
- 比特率格式：`^\d+[KMkm]$` (如 "2M", "500K")
- 帧率：1-120
- 编码预设：ultrafast, superfast, veryfast, ... veryslow
- 编码调优：film, animation, grain, stillimage, fastdecode, zerolatency
- 日志级别：DEBUG, INFO, WARNING, ERROR, CRITICAL

## 关键依赖与配置

### 内部依赖

- `src/exceptions.py` - `ConfigValidationError` 异常类
- `dataclasses` - `ConfigData`, `SourceConfig`, `RegionConfig` 等数据类
- `json`, `pathlib` - 文件加载和路径处理

### 外部依赖

- `jsonschema>=4.0.0` (可选) - JSON Schema 验证

### 配置常量

所有默认值定义在 `ConfigValidator` 类中：
- `DEFAULT_SERVER_PORT = 8765`
- `DEFAULT_HOST = "0.0.0.0"`
- `DEFAULT_VIDEO_CODEC = "libx264"`
- `DEFAULT_AUDIO_CODEC = "aac"`
- `DEFAULT_BITRATE = "2M"`
- `DEFAULT_FRAMERATE = 30`
- `DEFAULT_PRESET = "ultrafast"`
- `DEFAULT_TUNE = "zerolatency"`
- `DEFAULT_CRASH_THRESHOLD = 3`
- `DEFAULT_CRASH_WINDOW = 60`
- `DEFAULT_SHUTDOWN_TIMEOUT = 30`

## 数据模型

### ConfigData (dataclass)

完整配置数据对象，包含所有配置参数：

```python
@dataclass
class ConfigData:
    # 服务器配置
    server_port: int
    host: str

    # FFmpeg 配置
    ffmpeg_path: str
    video_codec: str
    audio_codec: str
    bitrate: str
    framerate: int
    preset: str
    tune: str

    # 录制源配置
    source: SourceConfig

    # 进程管理配置
    crash_threshold: int
    crash_window: int
    shutdown_timeout: int

    # 日志配置
    log_level: str
    log_file: Optional[str]
```

### SourceConfig (Union)

统一录制源配置，可能是以下类型之一：
- `ScreenSourceConfig` - 屏幕录制源
- `WindowSourceConfig` - 窗口录制源

### ScreenSourceConfig (dataclass)

```python
@dataclass
class ScreenSourceConfig:
    type: str  # "screen"
    display_index: int = 1
    region: Optional[RegionConfig] = None
```

### WindowSourceConfig (dataclass)

```python
@dataclass
class WindowSourceConfig:
    type: str  # "window", "window_bg", "window_region"
    window_title: Optional[str] = None
    window_title_pattern: Optional[str] = None
    window_class: Optional[str] = None
    find_by_substring: bool = False
    case_sensitive: bool = False
    region: Optional[RegionConfig] = None
    force_render: bool = False
    restore_position: bool = True
```

### RegionConfig (dataclass)

```python
@dataclass
class RegionConfig:
    x: int
    y: int
    width: int
    height: int
```

## 测试与质量

### 测试文件

- `tests/unit/test_config.py` - 单元测试
- `tests/integration/test_integration_config.py` - 集成测试

### 测试覆盖

- 配置文件加载测试
- 默认值应用测试
- 路径解析测试
- 验证规则测试（正常、边界、异常情况）
- 不同录制源类型配置测试

### 测试 Fixtures

- `temp_config_file` - 创建临时配置文件
- `mock_config` - Mock 配置对象
- `sample_config_json` - 示例配置 JSON
- `sample_window_config_json` - 窗口录制配置 JSON

### 运行测试

```bash
# 单元测试
pytest tests/unit/test_config.py

# 集成测试
pytest tests/integration/test_integration_config.py

# 带覆盖率
pytest --cov=src/config tests/unit/test_config.py
```

## 常见问题 (FAQ)

### Q1: 如何修改默认配置？

A: 修改 `ConfigValidator` 类中的类常量，如：
```python
DEFAULT_SERVER_PORT = 9000
DEFAULT_FRAMERATE = 60
```

### Q2: 如何添加新的配置项？

A: 步骤如下：
1. 在 `ConfigData` dataclass 中添加字段
2. 在 `ConfigValidator` 中添加验证规则
3. 在 `ConfigParser._convert_to_config_data()` 中解析字段
4. 添加相应的测试

### Q3: 如何添加新的录制源类型？

A: 步骤如下：
1. 在 `ConfigValidator._validate_source_config()` 中添加新类型验证
2. 创建新的 dataclass (如 `CameraSourceConfig`)
3. 在 `ConfigParser._parse_source_config()` 中添加解析逻辑
4. 更新 FFmpeg 命令构建器

### Q4: 配置文件路径找不到怎么办？

A: 检查：
1. 配置文件路径是否正确
2. 是否使用绝对路径或相对于项目根目录的路径
3. `ConfigParser` 会自动解析相对路径

### Q5: 如何支持环境变量配置？

A: 扩展 `ConfigParser` 的 `_load_json()` 方法：
```python
import os

def _load_json(self) -> Dict[str, Any]:
    # 读取 JSON
    config = super()._load_json()

    # 替换环境变量
    def replace_env(value):
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            env_var = value[2:-1]
            return os.getenv(env_var, value)
        return value

    # 递归替换
    return self._recursive_replace(config, replace_env)
```

## 相关文件清单

### 核心文件

- `src/config/__init__.py` - 模块初始化
- `src/config/config_parser.py` - 配置解析器 (389 行)
- `src/config/config_validator.py` - 配置验证器 (363 行)

### 配置文件

- `config/config.example.json` - 示例配置文件

### 测试文件

- `tests/fixtures/configs/valid_screen_config.json` - 屏幕录制配置示例
- `tests/fixtures/configs/valid_window_config.json` - 窗口录制配置示例
- `tests/unit/test_config.py` - 单元测试
- `tests/integration/test_integration_config.py` - 集成测试

## 变更记录 (Changelog)

### 2025-01-09
- 初始化模块文档
- 记录所有接口和数据模型
- 整理测试策略和 FAQ
