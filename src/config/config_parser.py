"""
配置文件解析器

负责加载、解析和验证 JSON 配置文件
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Union, Optional
from dataclasses import dataclass

from .config_validator import ConfigValidator
from src.exceptions import ConfigValidationError


@dataclass
class RegionConfig:
    """区域配置"""
    x: int
    y: int
    width: int
    height: int


@dataclass
class ScreenSourceConfig:
    """屏幕录制源配置"""
    type: str
    display_index: int = 1
    region: Optional[RegionConfig] = None


@dataclass
class WindowSourceConfig:
    """窗口录制源配置"""
    type: str
    window_title: Optional[str] = None
    window_title_pattern: Optional[str] = None
    window_class: Optional[str] = None
    find_by_substring: bool = False
    case_sensitive: bool = False
    region: Optional[RegionConfig] = None
    force_render: bool = False
    restore_position: bool = True


@dataclass
class NetworkStreamSourceConfig:
    """网络流录制源配置

    支持 RTSP、RTMP、HTTP-FLV 等网络流协议
    """
    type: str  # 必须为 "network_stream"
    url: str  # 网络流 URL (rtsp://, rtmp://, http://, https://)
    transport: Optional[str] = None  # 传输协议: tcp, udp, auto
    timeout: Optional[int] = None  # 超时时间（微秒）
    reconnect_delay: Optional[int] = None  # 重连延迟（秒）
    max_reconnect_attempts: Optional[int] = None  # 最大重连次数


@dataclass
class SourceConfig:
    """统一录制源配置"""
    source: Union[ScreenSourceConfig, WindowSourceConfig, NetworkStreamSourceConfig]


@dataclass
class ConfigData:
    """完整配置数据对象"""

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


class ConfigParser:
    """配置文件解析器

    负责加载 JSON 配置文件，解析并验证配置参数
    """

    def __init__(self, config_path: str, validator: Optional[ConfigValidator] = None):
        """初始化解析器

        Args:
            config_path: 配置文件路径
            validator: 配置验证器（可选，默认创建新实例）
        """
        self.config_path = Path(config_path)
        self.validator = validator or ConfigValidator()

        # 获取项目根目录（用于解析相对路径）
        self.project_root = Path(__file__).parent.parent.parent

    def parse(self) -> ConfigData:
        """解析配置文件

        Returns:
            ConfigData: 配置数据对象

        Raises:
            FileNotFoundError: 配置文件不存在
            json.JSONDecodeError: JSON 格式错误
            ConfigValidationError: 配置验证失败
        """
        # 1. 加载 JSON 文件
        config_dict = self._load_json()

        # 2. 应用默认值
        config_dict = self._apply_defaults(config_dict)

        # 3. 解析相对路径为绝对路径
        config_dict = self._resolve_paths(config_dict)

        # 4. 验证配置
        self.validator.validate(config_dict)

        # 5. 转换为 ConfigData 对象
        return self._convert_to_config_data(config_dict)

    def _load_json(self) -> Dict[str, Any]:
        """加载 JSON 文件

        Returns:
            Dict[str, Any]: 配置字典

        Raises:
            FileNotFoundError: 配置文件不存在
            json.JSONDecodeError: JSON 格式错误
        """
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"配置文件不存在: {self.config_path.absolute()}"
            )

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(
                f"配置文件 JSON 格式错误: {e.msg}",
                e.doc,
                e.pos
            )

    def _apply_defaults(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """应用默认值

        Args:
            config: 原始配置字典

        Returns:
            Dict[str, Any]: 应用默认值后的配置字典
        """
        # 服务器配置默认值
        config.setdefault("server", {})
        config["server"].setdefault("port", ConfigValidator.DEFAULT_SERVER_PORT)
        config["server"].setdefault("host", ConfigValidator.DEFAULT_HOST)

        # FFmpeg 配置默认值
        config.setdefault("ffmpeg", {})
        config["ffmpeg"].setdefault("video_codec", ConfigValidator.DEFAULT_VIDEO_CODEC)
        config["ffmpeg"].setdefault("audio_codec", ConfigValidator.DEFAULT_AUDIO_CODEC)
        config["ffmpeg"].setdefault("bitrate", ConfigValidator.DEFAULT_BITRATE)
        config["ffmpeg"].setdefault("framerate", ConfigValidator.DEFAULT_FRAMERATE)
        config["ffmpeg"].setdefault("preset", ConfigValidator.DEFAULT_PRESET)
        config["ffmpeg"].setdefault("tune", ConfigValidator.DEFAULT_TUNE)

        # 录制源配置默认值（必需）
        config.setdefault("source", {"type": "screen"})

        # 进程管理配置默认值
        config.setdefault("process", {})
        config["process"].setdefault("crash_threshold", ConfigValidator.DEFAULT_CRASH_THRESHOLD)
        config["process"].setdefault("crash_window", ConfigValidator.DEFAULT_CRASH_WINDOW)
        config["process"].setdefault("shutdown_timeout", ConfigValidator.DEFAULT_SHUTDOWN_TIMEOUT)

        # 日志配置默认值
        config.setdefault("logging", {})
        config["logging"].setdefault("level", "INFO")
        config["logging"].setdefault("file", None)

        return config

    def _resolve_paths(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """解析相对路径为绝对路径

        Args:
            config: 配置字典

        Returns:
            Dict[str, Any]: 路径已解析的配置字典
        """
        # 解析 FFmpeg 路径
        if "ffmpeg" in config and "ffmpeg_path" in config["ffmpeg"]:
            ffmpeg_path = config["ffmpeg"]["ffmpeg_path"]
            config["ffmpeg"]["ffmpeg_path"] = str(self._resolve_relative_path(ffmpeg_path))
        else:
            # 使用内置 FFmpeg（如果不存在则使用默认路径）
            try:
                config["ffmpeg"]["ffmpeg_path"] = str(self._get_builtin_ffmpeg_path())
            except FileNotFoundError:
                # 测试环境或 FFmpeg 未安装时使用默认路径
                config["ffmpeg"]["ffmpeg_path"] = "ffmpeg.exe"

        # 解析日志文件路径
        if "logging" in config and config["logging"].get("file"):
            log_file = config["logging"]["file"]
            config["logging"]["file"] = str(self._resolve_relative_path(log_file))

        return config

    def _resolve_relative_path(self, relative_path: str) -> Path:
        """解析相对路径为绝对路径

        Args:
            relative_path: 相对路径

        Returns:
            Path: 绝对路径
        """
        path = Path(relative_path)

        # 如果是绝对路径，直接返回
        if path.is_absolute():
            return path

        # 相对于项目根目录
        return self.project_root / path

    def _get_builtin_ffmpeg_path(self) -> Path:
        """获取内置 FFmpeg 可执行文件路径

        Returns:
            Path: FFmpeg 可执行文件的绝对路径
        """
        # Windows 平台
        ffmpeg_name = "ffmpeg.exe"
        ffmpeg_dir = self.project_root / "ffmpeg"
        ffmpeg_path = ffmpeg_dir / ffmpeg_name

        if not ffmpeg_path.exists():
            raise FileNotFoundError(
                f"找不到内置 FFmpeg: {ffmpeg_path.absolute()}\n"
                f"请确保 FFmpeg 可执行文件位于 {ffmpeg_dir.absolute()} 目录下"
            )

        return ffmpeg_path

    def _convert_to_config_data(self, config: Dict[str, Any]) -> ConfigData:
        """将配置字典转换为 ConfigData 对象

        Args:
            config: 配置字典

        Returns:
            ConfigData: 配置数据对象
        """
        # 解析服务器配置
        server_config = config["server"]
        server_port = server_config["port"]
        host = server_config["host"]

        # 解析 FFmpeg 配置
        ffmpeg_config = config["ffmpeg"]
        ffmpeg_path = ffmpeg_config["ffmpeg_path"]
        video_codec = ffmpeg_config["video_codec"]
        audio_codec = ffmpeg_config["audio_codec"]
        bitrate = ffmpeg_config["bitrate"]
        framerate = ffmpeg_config["framerate"]
        preset = ffmpeg_config["preset"]
        tune = ffmpeg_config["tune"]

        # 解析录制源配置
        source_config = self._parse_source_config(config["source"])

        # 解析进程管理配置
        process_config = config["process"]
        crash_threshold = process_config["crash_threshold"]
        crash_window = process_config["crash_window"]
        shutdown_timeout = process_config["shutdown_timeout"]

        # 解析日志配置
        logging_config = config["logging"]
        log_level = logging_config["level"]
        log_file = logging_config["file"]

        return ConfigData(
            server_port=server_port,
            host=host,
            ffmpeg_path=ffmpeg_path,
            video_codec=video_codec,
            audio_codec=audio_codec,
            bitrate=bitrate,
            framerate=framerate,
            preset=preset,
            tune=tune,
            source=source_config,
            crash_threshold=crash_threshold,
            crash_window=crash_window,
            shutdown_timeout=shutdown_timeout,
            log_level=log_level,
            log_file=log_file
        )

    def _parse_source_config(self, source_dict: Dict[str, Any]) -> SourceConfig:
        """解析录制源配置

        Args:
            source_dict: 录制源配置字典

        Returns:
            SourceConfig: 录制源配置对象
        """
        source_type = source_dict["type"]

        if source_type == "screen":
            source = self._parse_screen_source(source_dict)
        elif source_type in ["window", "window_bg", "window_region"]:
            source = self._parse_window_source(source_dict)
        elif source_type == "network_stream":
            source = self._parse_network_stream_source(source_dict)
        else:
            raise ConfigValidationError(f"不支持的录制源类型: {source_type}")

        return SourceConfig(source=source)

    def _parse_screen_source(self, source_dict: Dict[str, Any]) -> ScreenSourceConfig:
        """解析屏幕录制源配置

        Args:
            source_dict: 录制源配置字典

        Returns:
            ScreenSourceConfig: 屏幕录制源配置对象
        """
        region = None
        if "region" in source_dict and source_dict["region"] is not None:
            region_dict = source_dict["region"]
            region = RegionConfig(
                x=region_dict["x"],
                y=region_dict["y"],
                width=region_dict["width"],
                height=region_dict["height"]
            )

        return ScreenSourceConfig(
            type=source_dict["type"],
            display_index=source_dict.get("display_index", 1),
            region=region
        )

    def _parse_window_source(self, source_dict: Dict[str, Any]) -> WindowSourceConfig:
        """解析窗口录制源配置

        Args:
            source_dict: 录制源配置字典

        Returns:
            WindowSourceConfig: 窗口录制源配置对象
        """
        region = None
        if "region" in source_dict and source_dict["region"] is not None:
            region_dict = source_dict["region"]
            region = RegionConfig(
                x=region_dict["x"],
                y=region_dict["y"],
                width=region_dict["width"],
                height=region_dict["height"]
            )

        return WindowSourceConfig(
            type=source_dict["type"],
            window_title=source_dict.get("window_title"),
            window_title_pattern=source_dict.get("window_title_pattern"),
            window_class=source_dict.get("window_class"),
            find_by_substring=source_dict.get("find_by_substring", False),
            case_sensitive=source_dict.get("case_sensitive", False),
            region=region,
            force_render=source_dict.get("force_render", False),
            restore_position=source_dict.get("restore_position", True)
        )

    def _parse_network_stream_source(self, source_dict: Dict[str, Any]) -> NetworkStreamSourceConfig:
        """解析网络流录制源配置

        Args:
            source_dict: 录制源配置字典

        Returns:
            NetworkStreamSourceConfig: 网络流录制源配置对象
        """
        # URL 是必需的
        if "url" not in source_dict or not source_dict["url"]:
            raise ConfigValidationError("网络流源必须提供 url 字段")

        # 应用默认值
        # transport: 默认 tcp（更可靠）
        # timeout: 默认 5000000 微秒（5 秒）
        # reconnect_delay: 默认 5 秒
        # max_reconnect_attempts: 默认 3 次
        return NetworkStreamSourceConfig(
            type=source_dict["type"],
            url=source_dict["url"],
            transport=source_dict.get("transport", "tcp"),
            timeout=source_dict.get("timeout", 5000000),
            reconnect_delay=source_dict.get("reconnect_delay", 5),
            max_reconnect_attempts=source_dict.get("max_reconnect_attempts", 3)
        )
