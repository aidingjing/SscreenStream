# Project Context

## Purpose

**WebSocket Screen Streamer** 是一个基于 Python 的屏幕录制与实时推流工具，通过 FFmpeg 捕获屏幕或窗口内容，编码为 FLV 格式，并通过 WebSocket 推送给客户端。

**核心目标：**
- 按需启动：第一个客户端连接时才启动 FFmpeg，节省系统资源
- 自动管理：所有客户端断开后自动关闭 FFmpeg 进程
- 多源支持：支持屏幕、窗口、窗口区域等多种录制源
- 稳定性：通过滑动窗口算法监控 FFmpeg 崩溃并自动重启
- 实时推流：使用 WebSocket 协议实时推送 FLV 视频流

## Tech Stack

### 核心技术
- **Python 3.7+** - 主要编程语言
- **asyncio** - 异步编程框架（Python 内置）
- **FFmpeg** - 视频捕获和编码
  - gdigrab（Windows 屏幕捕获）
  - libx264（H.264 视频编码）
  - aac（音频编码）

### WebSocket 框架
- **websockets 11.0** - 纯 WebSocket 服务器实现
- **Flask 3.0.0** - HTTP 服务器框架
- **Flask-Sock 0.7.0** - Flask WebSocket 集成

### 开发工具
- **pytest 7.4.3** - 测试框架
- **pytest-cov 4.1.0** - 测试覆盖率
- **pytest-asyncio 0.21.1** - 异步测试支持
- **pytest-mock 3.12.0** - Mock 工具
- **pylint 3.0.3** - 代码质量检查
- **flake8 6.1.0** - 代码风格检查
- **mypy 1.7.1** - 静态类型检查
- **jsonschema 4.0.0+** - JSON 配置验证

## Project Conventions

### Code Style

#### Python 代码规范
- **遵循 PEP 8 规范** - Python 官方代码风格指南
- **使用类型注解（Type Hints）** - 所有函数和方法都应添加参数和返回值类型注解
- **文档字符串** - 所有公共模块、类、方法都应包含 docstring
- **命名约定**：
  - 模块名：小写下划线（`config_parser`）
  - 类名：大驼峰（`ConfigParser`）
  - 函数/方法：小写下划线（`parse_config`）
  - 常量：大写下划线（`MAX_RETRIES`）

#### 代码质量标准
- **测试覆盖率目标**：> 80%
- **Pylint 评分目标**：> 8.0
- **Flake8**：无错误，警告最小化
- **类型检查**：mypy 无严重错误

#### 导入顺序
```python
# 1. 标准库
import asyncio
from pathlib import Path

# 2. 第三方库
import websockets
from flask import Flask

# 3. 本地模块
from src.config import ConfigParser
from src.recorder import FFmpegRecorder
```

### Architecture Patterns

#### 分层架构
项目采用严格的分层架构，从上到下依次为：

1. **主程序入口** (`src/main.py`)
   - 命令行参数解析
   - 配置加载
   - 组件初始化
   - 生命周期管理

2. **WebSocket 推流层** (`src/streamer/`)
   - WebSocket 服务器
   - 客户端连接管理
   - 按需启动/停止 FFmpeg
   - 流数据分发

3. **录制层** (`src/recorder/`)
   - 实现 BaseRecorder 接口
   - FFmpeg 进程管理
   - 崩溃处理和重启

4. **进程管理层** (`src/process/`)
   - 通用子进程管理器
   - 启动/停止进程
   - 非阻塞输出读取
   - 健康监控

5. **配置管理层** (`src/config/`)
   - 配置文件加载
   - 参数验证
   - 默认值应用

#### 设计模式应用

**策略模式**
- `ProcessManager` 通过依赖注入接收命令构建器
- 录制器注入命令构建策略，便于扩展

**观察者模式**
- `WebSocketStreamer` 监听客户端连接状态变化
- 事件：客户端连接/断开 → 响应：启动/关闭 FFmpeg

**组合模式**
- `FFmpegRecorder` 组合多个组件：
  - `FFmpegCommandBuilder` - 命令构建策略
  - `ProcessManager` - 进程管理
  - `HealthMonitor` - 健康监控

**抽象工厂模式**
- `BaseRecorder` 定义录制器接口
- `FFmpegRecorder` 实现具体逻辑
- 便于扩展其他录制器（如 CameraRecorder）

#### 核心设计原则

**KISS（简单至上）**
- 追求代码和设计的极致简洁
- 拒绝不必要的复杂性
- 优先选择最直观的解决方案

**YAGNI（精益求精）**
- 仅实现当前明确所需的功能
- 抵制过度设计和未来特性预留
- 删除未使用的代码和依赖

**DRY（杜绝重复）**
- 自动识别重复代码模式
- 主动建议抽象和复用
- 统一相似功能的实现方式

**SOLID 原则**
- **单一职责**：每个类只有一个改变的理由
- **开闭原则**：通过抽象扩展，而非修改现有代码
- **里氏替换**：子类型可替换父类型
- **接口隔离**：接口专一，避免"胖接口"
- **依赖倒置**：依赖抽象而非具体实现

#### 异步编程规范
- 使用 `asyncio` 进行异步操作
- WebSocket 连接使用 `async`/`await`
- 进程输出读取使用 `asyncio.to_thread()` 避免阻塞
- 所有异步方法必须以 `_a` 结尾或使用 `async def`

### Testing Strategy

#### 测试组织结构
```
tests/
├── unit/              # 单元测试 - 测试单个组件
├── integration/       # 集成测试 - 测试组件交互
├── fixtures/          # 测试数据和配置
└── conftest.py        # pytest 配置和 fixtures
```

#### 测试类型和标记
- `unit` - 单元测试：快速测试单个函数或类
- `integration` - 集成测试：测试多个组件协作
- `e2e` - 端到端测试：完整工作流测试
- `slow` - 慢速测试：执行时间较长的测试
- `windows` - Windows 平台特定测试

#### 运行测试
```bash
# 所有测试
pytest tests/ -v

# 特定类型测试
pytest -m unit              # 单元测试
pytest -m integration       # 集成测试
pytest -m "not slow"        # 跳过慢速测试

# 覆盖率报告
pytest --cov=src --cov-report=html tests/
```

#### Mock 策略
- **Mock FFmpeg**：使用 `pytest-mock` Mock `ProcessManager`，避免启动真实 FFmpeg
- **Mock WebSocket**：Mock `websockets` 库，避免真实网络连接
- **Mock Window API**：Mock `WindowHelper`，避免操作系统窗口 API 调用
- **Mock 文件系统**：使用 `tmp_path` fixture 隔离文件操作

#### 测试最佳实践
- **独立性**：每个测试应该独立运行，不依赖其他测试
- **可重复性**：多次运行结果应该一致
- **快速反馈**：单元测试应该快速完成（< 1 秒）
- **清晰命名**：测试方法名应该描述被测试的行为
- **AAA 模式**：Arrange（准备）→ Act（执行）→ Assert（断言）

### Git Workflow

#### 分支策略
- **master** - 主分支，保持稳定可发布状态
- **feature/*** - 功能分支（如 `feature/add-audio-support`）
- **bugfix/*** - 缺陷修复分支（如 `bugfix/fix-crash-on-startup`）
- **refactor/*** - 重构分支（如 `refactor/optimize-ffmpeg-command`）

#### 提交规范
使用 **Conventional Commits** 格式：
```
<type>(<scope>): <subject>

<body>

<footer>
```

**类型（type）：**
- `feat` - 新功能
- `fix` - 缺陷修复
- `refactor` - 重构（不改变功能）
- `docs` - 文档更新
- `test` - 测试相关
- `chore` - 构建/工具链相关

**示例：**
```bash
feat(recorder): add window region recording support
fix(streamer): prevent memory leak in client manager
refactor(config): simplify validation logic
docs(readme): update FFmpeg installation instructions
```

#### .gitignore 规则
- **忽略运行时生成文件**：`__pycache__/`, `*.pyc`, `*.log`
- **忽略敏感配置**：`config/*.json`（保留 `*.example.json`）
- **忽略大型二进制**：`ffmpeg/*.exe`, `ffmpeg/*.dll`
- **忽略 IDE 配置**：`.vscode/`, `.idea/`
- **忽略测试产物**：`.pytest_cache/`, `.coverage`, `htmlcov/`

## Domain Context

### 屏幕录制概念
- **gdigrab**：Windows DirectScreen 屏幕捕获技术，提供高性能的屏幕和窗口捕获
- **帧率（framerate）**：每秒捕获的画面数量，常用值：30fps、60fps
- **比特率（bitrate）**：视频数据每秒的比特数，常用值：2M、4M、8M
- **编码预设（preset）**：编码速度与压缩率的平衡，从 ultrafast 到 veryslow

### FLV 流媒体协议
- **FLV（Flash Video）**：一种流媒体容器格式，适合实时传输
- **GOP（Group of Pictures）**：一组连续的视频帧，包含 I 帧（关键帧）和 P/B 帧
- **关键帧（I-frame）**：完整画面帧，可作为解码起点
- **FLV Header**：FLV 文件的头部信息，包含元数据

### WebSocket 通信
- **WebSocket**：全双工通信协议，适合实时数据推送
- **按需启动**：只有客户端连接时才启动 FFmpeg 进程
- **延迟关闭**：所有客户端断开后，等待 30 秒再关闭 FFmpeg（避免频繁重启）

### FFmpeg 崩溃检测
- **滑动窗口算法**：在 60 秒的时间窗口内，如果 FFmpeg 崩溃 3 次，则停止重启
- **崩溃阈值**：防止 FFmpeg 无限重启导致资源浪费

## Important Constraints

### 技术约束
- **Python 版本**：必须 ≥ 3.7（asyncio 支持和类型注解改进）
- **操作系统**：主要支持 Windows（gdigrab），Linux（x11grab）和 macOS 可选
- **FFmpeg 版本**：必须支持 gdigrab/x11grab、libx264、aac 编码器
- **内存限制**：单个 FFmpeg 进程约占用 100-200MB 内存

### 业务约束
- **资源节省**：无客户端连接时不启动 FFmpeg
- **自动关闭**：所有客户端断开 30 秒后自动关闭 FFmpeg
- **崩溃保护**：FFmpeg 连续崩溃 3 次后停止自动重启

### 配置约束
- **配置文件位置**：`config/config.json`（需手动创建，不提交到 Git）
- **FFmpeg 可执行文件**：必须手动放置在 `ffmpeg/` 目录下
- **示例配置**：`config/config.example.json` 作为模板，可以提交到 Git

### 性能约束
- **启动延迟**：FFmpeg 启动时间约 1-3 秒
- **内存占用**：每个客户端连接约占用 1-2MB 内存
- **网络带宽**：2M 比特率下约 250KB/s，建议 ≥ 10Mbps 网络

## External Dependencies

### FFmpeg
**用途**：屏幕捕获、视频编码、音频编码

**版本要求**：
- 支持 `gdigrab`（Windows）或 `x11grab`（Linux）
- 支持 `libx264` 视频编码器
- 支持 `aac` 音频编码器

**安装方式**：
- **Windows**：手动下载 ffmpeg.exe 并放置在 `ffmpeg/` 目录
- **Linux**：`sudo apt-get install ffmpeg`
- **macOS**：`brew install ffmpeg`

**命令构建**：使用 `FFmpegCommandBuilder` 类动态构建命令行

### WebSocket 协议
**用途**：实时推送 FLV 视频流到客户端

**实现方式**：
- **websockets** 库（纯异步实现）
- **Flask-Sock** 库（Flask 集成实现）

**客户端要求**：
- 支持 WebSocket 协议（JavaScript WebSocket API）
- 支持 FLV 播放（flv.js 或类似库）

### 操作系统 API
**Windows API**：
- **win32gui**：窗口查找和枚举（通过 `window_helper.py`）
- **DirectScreen**：屏幕捕获（通过 gdigrab）

**Linux API**：
- **X11**：窗口和屏幕捕获（通过 x11grab）

### 配置文件
**JSON Schema**：
- 使用 `jsonschema` 进行配置验证
- 定义在 `src/config/config_validator.py`

**配置文件结构**：
- `server`：服务器配置（host、port）
- `ffmpeg`：FFmpeg 配置（codec、bitrate、framerate）
- `source`：录制源配置（type、display_index、window_title）
- `process`：进程管理配置（crash_threshold、crash_window）
- `logging`：日志配置（level、file）

## Development Guidelines

### 添加新功能流程
1. 在 OpenSpec 中创建变更提案（`openspec/changes/<change-id>/`）
2. 定义需求和场景（`specs/<capability>/spec.md`）
3. 实现功能并编写测试
4. 确保测试覆盖率 > 80%
5. 通过 pylint、flake8、mypy 检查
6. 更新文档（CLAUDE.md 和相关模块文档）
7. 归档变更提案（`openspec archive <change-id>`）

### 调试技巧
1. **启用调试日志**：设置 `"level": "DEBUG"`
2. **查看日志文件**：`screen-streamer.log`
3. **使用 pytest 断点**：`pytest --pdb`
4. **Mock 组件隔离**：使用 `pytest-mock` Mock 外部依赖

### 文档更新要求
- **新增功能**：更新 CLAUDE.md 和相关模块文档
- **API 变更**：更新文档字符串和使用示例
- **配置变更**：更新 `config/config.example.json`
- **架构变更**：更新架构图和设计模式说明

## Project Metrics

### 代码质量目标
- **测试覆盖率**：> 80%
- **Pylint 评分**：> 8.0
- **类型检查**：mypy 无严重错误
- **文档完整性**：所有公共 API 有 docstring

### 性能基准
- **FFmpeg 启动时间**：< 3 秒
- **客户端连接延迟**：< 1 秒
- **视频延迟**：< 2 秒（端到端）
- **内存占用**：< 300MB（包含 FFmpeg）

### 稳定性指标
- **FFmpeg 崩溃率**：< 1%
- **内存泄漏**：长时间运行无明显增长
- **客户端断开恢复**：100% 成功
