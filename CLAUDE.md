# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

**WebSocket Screen Streamer** 是一个基于 Python 的屏幕录制与实时推流工具。通过 FFmpeg 捕获屏幕或窗口内容，编码为 FLV 格式，并通过 WebSocket 推送给客户端。

**核心特性：**
- 按需启动：第一个客户端连接时才启动 FFmpeg，节省资源
- 自动关闭：所有客户端断开后自动关闭 FFmpeg
- 多源支持：屏幕、窗口、窗口区域录制
- 崩溃恢复：滑动窗口算法监控 FFmpeg 崩溃并自动重启
- WebSocket 推流：使用 WebSocket 实时推送 FLV 视频流

**技术栈：**
- Python 3.7+
- FFmpeg (gdigrab for Windows)
- WebSocket (websockets + Flask-Sock)
- asyncio (异步编程)

## 环境设置

### 安装依赖

```bash
# 安装生产依赖
pip install -r requirements.txt

# 安装开发依赖（测试、代码检查）
pip install -r requirements-dev.txt
```

### FFmpeg 安装

**Windows:**
1. 下载 FFmpeg: https://ffmpeg.org/download.html
2. 解压并将 `ffmpeg.exe` 放置到项目根目录的 `ffmpeg/` 文件夹下

**Linux:**
```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg

# CentOS/RHEL
sudo yum install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

## 常用命令

### 运行程序

```bash
# 使用默认配置文件运行
python -m src.main

# 指定配置文件
python -m src.main --config config/config.json

# 列出所有可见窗口（辅助功能）
python -m src.main --list-windows
```

### 测试命令

```bash
# 运行所有测试
pytest tests/ -v

# 运行单元测试
pytest tests/unit/ -v

# 运行集成测试
pytest tests/integration/ -v

# 生成覆盖率报告
pytest --cov=src --cov-report=html tests/

# 快速测试（跳过慢速测试）
pytest tests/ -m "not slow" -v

# 使用测试运行脚本
python run_tests.py all        # 所有测试
python run_tests.py unit       # 单元测试
python run_tests.py cov        # 覆盖率报告
```

### 单个测试运行

```bash
# 运行特定模块测试
pytest tests/unit/test_config.py -v
pytest tests/unit/test_recorder.py -v
pytest tests/unit/test_process.py -v
pytest tests/unit/test_streamer.py -v

# 运行特定测试类
pytest tests/unit/test_config.py::TestConfigParser -v

# 运行特定测试方法
pytest tests/unit/test_config.py::TestConfigParser::test_parse_valid_config -v
```

### 代码质量检查

```bash
# Pylint 代码检查
pylint src/

# Flake8 代码风格检查
flake8 src/

# mypy 类型检查
mypy src/
```

## 架构概览

### 分层架构

```
┌─────────────────────────────────────────────────────────────┐
│                        主程序入口                            │
│                     src/main.py                             │
│   - 命令行参数解析                                           │
│   - 配置加载                                                  │
│   - 组件初始化                                                │
│   - 生命周期管理                                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      WebSocket 推流层                        │
│                src/streamer/ws_server.py                     │
│   - WebSocket 服务器                                          │
│   - 客户端连接管理                                            │
│   - 按需启动/停止 FFmpeg                                      │
│   - 流数据分发                                                │
│   (依赖: ClientManager, StreamForwarder)                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        录制层                                │
│              src/recorder/ffmpeg_recorder.py                 │
│   - 实现 BaseRecorder 接口                                    │
│   - FFmpeg 进程管理                                          │
│   - 崩溃处理和重启                                            │
│   (依赖: ProcessManager, HealthMonitor, FFmpegCommandBuilder) │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       进程管理层                              │
│            src/process/process_manager.py                    │
│   - 通用子进程管理器                                          │
│   - 启动/停止进程                                              │
│   - 非阻塞输出读取                                            │
│   (依赖: HealthMonitor)                                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      配置管理层                               │
│           src/config/config_parser.py                        │
│   - 配置文件加载                                              │
│   - 参数验证                                                  │
│   - 默认值应用                                                │
│   (依赖: ConfigValidator)                                     │
└─────────────────────────────────────────────────────────────┘
```

### 模块职责

**src/config/** - 配置管理
- `ConfigParser`: 配置解析器
- `ConfigValidator`: 配置验证器
- 定义 `ConfigData` 等数据类

**src/recorder/** - 录制器
- `BaseRecorder`: 录制器抽象接口
- `FFmpegRecorder`: FFmpeg 录制器实现
- `FFmpegCommandBuilder`: FFmpeg 命令构建器
- `WindowHelper`: 窗口查找辅助工具

**src/process/** - 进程管理
- `ProcessManager`: 通用进程管理器
- `HealthMonitor`: 健康监控器（滑动窗口崩溃检测）

**src/streamer/** - 推流
- `WebSocketStreamer`: WebSocket 服务器（使用 websockets 库）
- `HybridStreamer`: 混合流服务器（HTTP-FLV + WebSocket-FLV）
- `FlaskWsServer`: Flask WebSocket 服务器（使用 Flask-Sock）
- `ClientManager`: 客户端连接管理
- `StreamForwarder`: 流数据转发器
- `GOPBuffer`: GOP 缓冲器（缓存关键帧，确保新客户端正确播放）

**src/utils/** - 工具
- `setup_logger()`: 日志配置
- `get_logger()`: 获取命名日志记录器

**src/exceptions.py** - 自定义异常
- `ConfigValidationError`: 配置验证错误
- `RecorderStartupError`: 录制器启动错误
- `ProcessManagerError`: 进程管理错误
- `WindowNotFoundError`: 窗口未找到错误
- `StreamError`: 推流错误

## 核心工作流

### 程序启动流程

```
1. 加载配置
   ├─> ConfigParser.parse()
   └─> ConfigValidator.validate()

2. 初始化日志
   └─> setup_logger()

3. 创建窗口助手（如果需要）
   └─> WindowHelper (仅窗口录制)

4. 创建录制器（⚠️ 不启动 FFmpeg）
   └─> FFmpegRecorder(config, logger)

5. 创建 WebSocket 服务器
   └─> WebSocketStreamer(config, recorder, logger)

6. 启动服务器监听（⚠️ 只启动监听，不启动 FFmpeg）
   └─> await server.start()

7. 等待客户端连接
   └─> 第一个客户端连接时才启动 FFmpeg
```

### 客户端连接流程（延迟启动）

```
第一个客户端连接
    ├─> 添加客户端到 ClientManager
    ├─> 启动 FFmpeg 录制
    │   ├─> ProcessManager.start()
    │   └─> StreamForwarder.start_forwarding()
    └─> 开始推流

更多客户端连接
    ├─> 添加客户端到 ClientManager
    └─> 复用现有 FFmpeg 进程

客户端断开
    ├─> 从 ClientManager 移除客户端
    └─> 如果是最后一个客户端，启动关闭定时器（默认 30 秒）

超时关闭（无新客户端）
    ├─> 停止 StreamForwarder
    ├─> 停止 FFmpeg
    └─> 返回监听状态
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

## 关键设计模式

### 策略模式

**ProcessManager** 通过依赖注入接收命令构建器：
```python
# 录制器注入命令构建策略
process_manager = ProcessManager(
    cmd_builder=self.command_builder.build,  # 策略注入
    logger=logger
)
```

### 观察者模式

**WebSocketStreamer** 监听客户端连接状态变化：
```python
# 事件：客户端连接
if client_count == 1:
    await self._start_ffmpeg_if_needed()  # 响应：启动 FFmpeg

# 事件：客户端断开
if is_empty():
    await self._schedule_ffmpeg_shutdown()  # 响应：计划关闭 FFmpeg
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

### 抽象工厂模式

**BaseRecorder** 定义录制器接口，FFmpegRecorder 实现具体逻辑，方便扩展其他录制器（如 CameraRecorder）。

## FFmpeg 依赖

### FFmpeg 可执行文件

**必须手动放置**在项目根目录的 `ffmpeg/` 文件夹下：
```
ffmpeg/ffmpeg.exe       (Windows)
ffmpeg/ffmpeg           (Linux/Mac)
```

### FFmpeg 版本要求

- 必须支持 `gdigrab` (Windows) 或 `x11grab` (Linux)
- 必须支持 `libx264` 视频编码器
- 必须支持 `aac` 音频编码器

### FFmpeg 命令结构

```bash
ffmpeg.exe \
  -f gdigrab \                    # 输入格式（Windows 屏幕捕获）
  -framerate 30 \                 # 帧率
  -rtbufsize 100M \               # 实时缓冲区大小
  -i desktop \                    # 输入源（整个桌面）
  -c:v libx264 \                  # 视频编码器
  -preset ultrafast \             # 编码速度预设
  -tune zerolatency \             # 编码调优（低延迟）
  -profile:v baseline \           # H.264 配置文件
  -level 3.1 \                    # H.264 级别
  -pix_fmt yuv420p \              # 像素格式
  -b:v 2M \                       # 视频比特率
  -g 30 \                         # GOP 大小（关键帧间隔）
  -c:a aac \                      # 音频编码器
  -b:a 128k \                     # 音频比特率
  -ar 44100 \                     # 音频采样率
  -f flv \                        # 输出格式
  -flvflags no_duration_filesize \ # FLV 标志
  pipe:1                          # 输出到标准输出
```

## 配置文件

### 配置文件位置

```
config/config.example.json  # 示例配置文件
config/config.json          # 实际配置文件（需自行创建）
```

### 配置文件结构

```json
{
  "server": {
    "port": 8765,              // WebSocket 服务器端口
    "host": "0.0.0.0"          // 监听地址
  },
  "ffmpeg": {
    "video_codec": "libx264",  // 视频编码器
    "audio_codec": "aac",      // 音频编码器
    "bitrate": "2M",           // 视频比特率
    "framerate": 30,           // 帧率
    "preset": "ultrafast",     // 编码速度预设
    "tune": "zerolatency"      // 编码调优
  },
  "source": {
    "type": "screen",          // 录制源类型: screen|window|window_bg|window_region
    "display_index": 1,        // 显示器索引
    "region": null             // 录制区域 {x, y, width, height}
  },
  "process": {
    "crash_threshold": 3,      // 崩溃重启阈值
    "crash_window": 60,        // 崩溃时间窗口（秒）
    "shutdown_timeout": 30     // 客户端断开后关闭超时（秒）
  },
  "logging": {
    "level": "INFO",           // 日志级别
    "file": "screen-streamer.log"  // 日志文件
  }
}
```

### 录制源类型

**screen** - 屏幕录制
```json
{
  "source": {
    "type": "screen",
    "display_index": 1,
    "region": null
  }
}
```

**window** - 窗口录制
```json
{
  "source": {
    "type": "window",
    "window_title": "Notepad",
    "force_render": true,
    "restore_position": true
  }
}
```

**window_region** - 窗口区域录制
```json
{
  "source": {
    "type": "window_region",
    "window_title": "Notepad",
    "region": {"x": 0, "y": 0, "width": 800, "height": 600}
  }
}
```

## 测试策略

### 测试组织

```
tests/
├── unit/           # 单元测试
│   ├── test_config.py
│   ├── test_recorder.py
│   ├── test_process.py
│   └── test_streamer.py
├── integration/    # 集成测试
│   └── test_integration_*.py
├── conftest.py     # pytest 配置和 fixtures
└── fixtures/       # 测试数据
    └── configs/    # 测试配置文件
```

### 测试标记

```bash
# 运行特定类型的测试
pytest -m unit              # 单元测试
pytest -m integration       # 集成测试
pytest -m "not slow"        # 跳过慢速测试
pytest -m windows           # Windows 平台测试
```

### Mock 策略

- **Mock FFmpeg**: Mock `ProcessManager` 避免启动真实 FFmpeg
- **Mock WebSocket**: Mock `websockets` 库避免真实网络连接
- **Mock Window API**: Mock `WindowHelper` 避免操作系统窗口 API 调用

## 常见问题

### Q1: FFmpeg 启动失败？

**检查：**
1. FFmpeg 可执行文件是否在 `ffmpeg/` 目录
2. 配置文件中的 `ffmpeg_path` 是否正确
3. FFmpeg 版本是否支持 gdigrab
4. 查看日志文件 `screen-streamer.log` 了解详细错误

### Q2: 如何修改录制源？

**A:** 修改配置文件中的 `source` 字段：
- `"type": "screen"` - 屏幕录制
- `"type": "window"` - 窗口录制
- `"type": "window_region"` - 窗口区域录制

### Q3: 如何找到窗口标题？

**A:** 使用辅助命令：
```bash
python -m src.main --list-windows
```

### Q4: 如何调整视频质量？

**A:** 修改配置文件中的 FFmpeg 参数：
- `"bitrate": "2M"` - 提高比特率提高质量（如 "4M", "8M"）
- `"framerate": 30` - 提高帧率使视频更流畅（如 60）
- `"preset": "ultrafast"` - 降低编码速度提高压缩率（如 "fast", "medium"）

### Q5: 客户端连接后立即断开？

**检查：**
1. FFmpeg 是否启动成功（查看日志）
2. 端口是否被占用（修改配置文件中的 `port`）
3. 防火墙是否阻止连接

### Q6: 如何实现认证？

**A:** 在 `WebSocketStreamer._handle_client()` 中添加认证逻辑（详见 src/streamer/CLAUDE.md）

### Q7: 支持哪些推流协议？

**A:** 项目支持三种推流服务器：
1. **WebSocketStreamer** - 纯 WebSocket 推流（websockets 库）
2. **HybridStreamer** - 混合推流（HTTP-FLV + WebSocket-FLV）
3. **FlaskWsServer** - Flask 集成 WebSocket 推流（Flask-Sock）

### Q8: GOP 缓冲是什么？

**A:** `GOPBuffer` 缓存最近 1-2 个 GOP（Group of Pictures）的数据，包括：
- FLV Header 和 onMetadata
- 关键帧（I-frame）
- 依赖帧（P-frame、B-frame）

这确保新客户端连接时能立即接收完整的关键帧，避免播放黑屏或花屏。

## 项目结构

```
screen/
├── src/                         # 源代码
│   ├── config/                  # 配置管理模块
│   │   ├── config_parser.py     # 配置解析器
│   │   ├── config_validator.py  # 配置验证器
│   │   └── CLAUDE.md            # 模块文档
│   ├── recorder/                # 录制模块
│   │   ├── base_recorder.py     # 录制器抽象接口
│   │   ├── ffmpeg_recorder.py   # FFmpeg 录制器
│   │   ├── ffmpeg_builder.py    # FFmpeg 命令构建器
│   │   ├── window_helper.py     # 窗口查找辅助工具
│   │   └── CLAUDE.md            # 模块文档
│   ├── process/                 # 进程管理模块
│   │   ├── process_manager.py   # 进程管理器
│   │   ├── health_monitor.py    # 健康监控器
│   │   └── CLAUDE.md            # 模块文档
│   ├── streamer/                # 推流模块
│   │   ├── ws_server.py         # WebSocket 服务器
│   │   ├── hybrid_streamer.py   # 混合流服务器
│   │   ├── flask_ws_server.py   # Flask WebSocket 服务器
│   │   ├── client_manager.py    # 客户端管理器
│   │   ├── stream_forwarder.py  # 流转发器
│   │   ├── gop_buffer.py        # GOP 缓冲器
│   │   └── CLAUDE.md            # 模块文档
│   ├── utils/                   # 工具模块
│   │   ├── logger.py            # 日志工具
│   │   ├── path_helper.py       # 路径辅助工具
│   │   └── CLAUDE.md            # 模块文档
│   ├── main.py                  # 主程序入口
│   └── exceptions.py            # 自定义异常
│
├── config/                      # 配置文件目录
│   └── config.example.json      # 示例配置文件
│
├── tests/                       # 测试代码
│   ├── unit/                    # 单元测试
│   ├── integration/             # 集成测试
│   ├── fixtures/                # 测试数据
│   └── conftest.py              # pytest 配置
│
├── ffmpeg/                      # FFmpeg 可执行文件（需手动放置）
│
├── requirements.txt             # 生产依赖
├── requirements-dev.txt         # 开发依赖
├── pytest.ini                   # pytest 配置
├── run_tests.py                 # 测试运行脚本
├── .gitignore                   # Git 忽略规则
├── CLAUDE.md                    # 项目文档（本文件）
│
└── screen-streamer.log          # 日志文件（运行时生成）
```

## 模块级文档

- [配置管理模块](src/config/CLAUDE.md) - 配置加载、验证、数据模型
- [录制模块](src/recorder/CLAUDE.md) - FFmpeg 录制器、命令构建、窗口助手
- [进程管理模块](src/process/CLAUDE.md) - 进程管理、健康监控、崩溃检测
- [推流模块](src/streamer/CLAUDE.md) - WebSocket 服务器、客户端管理、流转发
- [工具模块](src/utils/CLAUDE.md) - 日志配置、路径处理

## 开发指南

### Git 忽略规则

项目使用 `.gitignore` 文件忽略以下内容：
- Python 缓存文件 (`__pycache__`, `*.pyc`)
- 虚拟环境 (`venv/`, `env/`)
- 日志文件 (`*.log`)
- IDE 配置文件 (`.vscode/`, `.idea/`)
- 实际配置文件（保留 `config.example.json`，忽略 `config/*.json`）
- FFmpeg 可执行文件（`ffmpeg/*.exe`, `ffmpeg/*.dll`）
- 测试覆盖率文件 (`.coverage`, `htmlcov/`)

**注意：**
- FFmpeg 可执行文件需要手动放置，不会提交到 Git
- 实际配置文件（`config/config.json`）不会提交，使用 `config.example.json` 作为模板
- 日志文件不会提交

### 添加新功能

1. **配置扩展**：在 `ConfigData` 中添加字段，在 `ConfigValidator` 中添加验证
2. **录制器扩展**：继承 `BaseRecorder` 实现新的录制器
3. **推流协议扩展**：创建新的服务器类（如 RTSPStreamer）

### 代码风格

- 遵循 PEP 8 规范
- 使用类型注解（Type Hints）
- 编写单元测试（覆盖率目标 > 80%）
- 更新文档字符串和 CLAUDE.md

### 调试技巧

1. **启用调试日志**：设置 `"level": "DEBUG"`
2. **查看日志文件**：`screen-streamer.log`
3. **使用 pytest 断点**：`pytest --pdb`
4. **Mock 组件隔离**：使用 `pytest-mock` Mock 外部依赖
