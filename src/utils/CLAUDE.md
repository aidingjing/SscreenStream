[根目录](../../CLAUDE.md) > [src](../) > **utils**

---

# 工具模块 (utils)

## 模块职责

工具模块提供：
1. 统一的日志配置和管理 (`logger.py`)
2. 路径处理辅助功能 (`path_helper.py`)
3. 项目级通用工具函数

## 入口与启动

### 主要入口点

**setup_logger 函数** (`logger.py`)
- 配置统一的日志记录系统
- 支持控制台和文件输出
- 自动创建日志文件目录

**get_logger 函数** (`logger.py`)
- 获取命名日志记录器
- 支持子模块日志

**PathHelper 类** (`path_helper.py`)
- 路径处理辅助功能
- 相对路径和绝对路径转换

## 对外接口

### setup_logger

**函数签名：**
```python
def setup_logger(config: ConfigData) -> logging.Logger
```

**职责：**
- 创建名为 "ScreenStreamer" 的根日志记录器
- 配置日志级别（从 `ConfigData.log_level` 读取）
- 添加控制台处理器（始终）
- 添加文件处理器（如果 `ConfigData.log_file` 存在）
- 设置统一的日志格式

**日志格式：**
```
%(asctime)s - %(name)s - %(levelname)s - %(message)s
示例：2025-01-09 12:00:00 - ScreenStreamer - INFO - 服务器已启动
```

**使用示例：**
```python
from src.config.config_parser import ConfigParser
from src.utils.logger import setup_logger

# 加载配置
config = ConfigParser("config/config.example.json").parse()

# 设置日志
logger = setup_logger(config)

# 使用日志
logger.info("这是一条信息日志")
logger.warning("这是一条警告日志")
logger.error("这是一条错误日志")
```

### get_logger

**函数签名：**
```python
def get_logger(name: Optional[str] = None) -> logging.Logger
```

**职责：**
- 获取命名日志记录器
- 支持子模块日志（使用点号分隔）

**使用示例：**
```python
from src.utils.logger import get_logger

# 获取根日志记录器
root_logger = get_logger()

# 获取子模块日志记录器
config_logger = get_logger("config")
recorder_logger = get_logger("recorder")

# 使用日志
config_logger.info("配置加载成功")
recorder_logger.debug("FFmpeg 进程已启动")
```

**日志命名层次：**
```
ScreenStreamer (根)
├─ ScreenStreamer.config
├─ ScreenStreamer.recorder
├─ ScreenStreamer.process
├─ ScreenStreamer.streamer
└─ ScreenStreamer.utils
```

## 关键依赖与配置

### 内部依赖

- `src/config/config_parser.py` - `ConfigData` 配置数据

### 外部依赖

- `logging` - Python 标准日志库
- `sys` - 系统标准输出
- `pathlib` - 路径处理

### 配置参数

从 `ConfigData` 读取：
- `log_level` - 日志级别（DEBUG, INFO, WARNING, ERROR, CRITICAL）
- `log_file` - 日志文件路径（可选，相对或绝对路径）

## 日志配置详情

### 日志级别

| 级别 | 数值 | 用途 |
|------|------|------|
| DEBUG | 10 | 开发调试信息 |
| INFO | 20 | 正常运行信息 |
| WARNING | 30 | 警告信息（可恢复错误） |
| ERROR | 40 | 错误信息（严重错误） |
| CRITICAL | 50 | 严重错误（程序可能崩溃） |

### 日志处理器

**控制台处理器（ConsoleHandler）：**
- 始终启用
- 输出到 `sys.stdout`
- 级别：DEBUG
- 格式：`%(asctime)s - %(name)s - %(levelname)s - %(message)s`

**文件处理器（FileHandler）：**
- 可选（`log_file` 配置时启用）
- 输出到指定文件
- 级别：DEBUG
- 模式：追加（'a'）
- 编码：UTF-8
- 自动创建日志文件目录

### 日志格式化

**格式字符串：**
```python
fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
datefmt = '%Y-%m-%d %H:%M:%S'
```

**输出示例：**
```
2025-01-09 12:00:00 - ScreenStreamer - INFO - WebSocket Screen Streamer 启动
2025-01-09 12:00:01 - ScreenStreamer.config - INFO - 配置文件加载成功
2025-01-09 12:00:02 - ScreenStreamer.recorder - INFO - FFmpeg 录制器已初始化
2025-01-09 12:00:03 - ScreenStreamer.streamer - INFO - WebSocket 服务器已启动
2025-01-09 12:00:04 - ScreenStreamer.recorder - ERROR - FFmpeg 启动失败
```

## 测试与质量

### 测试文件

- 暂无专门测试文件（日志功能较简单）

### 测试覆盖

- 日志配置测试
- 文件处理器创建测试
- 日志级别设置测试

### 手动测试

```python
# 测试日志配置
from src.config.config_parser import ConfigParser
from src.utils.logger import setup_logger, get_logger

# 测试控制台日志
config = ConfigParser("config/config.example.json").parse()
logger = setup_logger(config)
logger.info("测试控制台日志")

# 测试文件日志
config.log_file = "test.log"
logger = setup_logger(config)
logger.info("测试文件日志")

# 测试子模块日志
module_logger = get_logger("test_module")
module_logger.info("测试子模块日志")
```

## 常见问题 (FAQ)

### Q1: 如何修改日志格式？

A: 修改 `logger.py` 中的格式化器：
```python
# 简化格式（无时间戳）
formatter = logging.Formatter(
    fmt='%(name)s - %(levelname)s - %(message)s'
)

# 详细格式（包含文件名和行号）
formatter = logging.Formatter(
    fmt='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
```

### Q2: 如何实现日志轮转（避免日志文件过大）？

A: 使用 `RotatingFileHandler`：
```python
from logging.handlers import RotatingFileHandler

def setup_logger(config: ConfigData) -> logging.Logger:
    # ...

    # 使用轮转文件处理器
    file_handler = RotatingFileHandler(
        log_file_path,
        mode='a',
        maxBytes=10*1024*1024,  # 10 MB
        backupCount=5,           # 保留 5 个备份
        encoding='utf-8'
    )

    # ...
```

### Q3: 如何按时间轮转日志（每天一个文件）？

A: 使用 `TimedRotatingFileHandler`：
```python
from logging.handlers import TimedRotatingFileHandler

file_handler = TimedRotatingFileHandler(
    log_file_path,
    when='midnight',      # 每天午夜轮转
    interval=1,           # 间隔 1 天
    backupCount=7,        # 保留 7 天
    encoding='utf-8'
)
```

### Q4: 如何过滤特定级别的日志？

A: 添加日志过滤器：
```python
class WarningFilter(logging.Filter):
    def filter(self, record):
        return record.levelno >= logging.WARNING

# 添加到处理器
file_handler.addFilter(WarningFilter())  # 只记录 WARNING 及以上
```

### Q5: 如何在测试时禁用日志？

A: 在测试中设置日志级别为 CRITICAL：
```python
import logging

def setup_test_logger():
    logger = logging.getLogger("ScreenStreamer")
    logger.setLevel(logging.CRITICAL)
    return logger
```

### Q6: 如何实现结构化日志（JSON 格式）？

A: 使用自定义格式化器：
```python
import json
from datetime import datetime

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "logger": record.name,
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno
        }
        return json.dumps(log_data)

# 使用
formatter = JsonFormatter()
file_handler.setFormatter(formatter)
```

## 相关文件清单

### 核心文件

- `src/utils/__init__.py` - 模块初始化
- `src/utils/logger.py` - 日志工具 (76 行)
- `src/utils/path_helper.py` - 路径辅助工具

### 测试文件

- 暂无专门测试文件

## 变更记录 (Changelog)

### 2025-01-09
- 初始化模块文档
- 记录所有接口和配置
- 整理日志格式和级别说明
- 添加日志轮转和过滤 FAQ
