"""
配置验证器

负责验证配置参数的合法性
"""

import re
from typing import Dict, Any
from src.exceptions import ConfigValidationError


class ConfigValidator:
    """配置验证器

    验证配置参数的类型、范围和合法性
    """

    # 默认配置常量
    DEFAULT_SERVER_PORT = 8765
    DEFAULT_HOST = "0.0.0.0"
    DEFAULT_VIDEO_CODEC = "libx264"
    DEFAULT_AUDIO_CODEC = "aac"
    DEFAULT_BITRATE = "2M"
    DEFAULT_FRAMERATE = 30
    DEFAULT_PRESET = "ultrafast"
    DEFAULT_TUNE = "zerolatency"
    DEFAULT_CRASH_THRESHOLD = 3
    DEFAULT_CRASH_WINDOW = 60
    DEFAULT_SHUTDOWN_TIMEOUT = 30

    # 有效的视频编码器
    VALID_VIDEO_CODECS = ["libx264", "libx265", "mpeg4", "vp8", "vp9"]

    # 有效的音频编码器
    VALID_AUDIO_CODECS = ["aac", "mp3", "libopus", "pcm_s16le"]

    # 有效的编码预设
    VALID_PRESETS = [
        "ultrafast", "superfast", "veryfast", "faster", "fast",
        "medium", "slow", "slower", "veryslow"
    ]

    # 有效的编码调优
    VALID_TUNES = [
        "film", "animation", "grain", "stillimage", "fastdecode",
        "zerolatency"
    ]

    # 有效的日志级别
    VALID_LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    def validate(self, config: Dict[str, Any]) -> None:
        """验证配置字典

        Args:
            config: 配置字典

        Raises:
            ConfigValidationError: 验证失败时抛出
        """
        try:
            # 只验证存在的配置部分
            if "server" in config:
                self._validate_server_config(config)
            if "ffmpeg" in config:
                self._validate_ffmpeg_config(config)
            if "source" in config:
                self._validate_source_config(config)
            if "process" in config:
                self._validate_process_config(config)
            if "logging" in config:
                self._validate_logging_config(config)
        except (KeyError, ValueError, TypeError) as e:
            raise ConfigValidationError(f"配置验证失败: {e}")

    def _validate_server_config(self, config: Dict[str, Any]) -> None:
        """验证服务器配置

        Args:
            config: 配置字典

        Raises:
            ConfigValidationError: 服务器配置无效
        """
        if "server" not in config:
            return  # 可选配置，使用默认值

        server = config["server"]

        # 验证端口
        if "port" in server:
            port = server["port"]
            if not isinstance(port, int):
                raise ConfigValidationError("服务器端口必须是整数")
            if not (1024 <= port <= 65535):
                raise ConfigValidationError(
                    f"服务器端口必须在 1024-65535 之间，当前值: {port}"
                )

        # 验证主机地址
        if "host" in server:
            host = server["host"]
            if not isinstance(host, str):
                raise ConfigValidationError("主机地址必须是字符串")

    def _validate_ffmpeg_config(self, config: Dict[str, Any]) -> None:
        """验证 FFmpeg 配置

        Args:
            config: 配置字典

        Raises:
            ConfigValidationError: FFmpeg 配置无效
        """
        if "ffmpeg" not in config:
            return  # 可选配置，使用默认值

        ffmpeg = config["ffmpeg"]

        # 验证视频编码器
        if "video_codec" in ffmpeg:
            codec = ffmpeg["video_codec"]
            if codec not in self.VALID_VIDEO_CODECS:
                raise ConfigValidationError(
                    f"不支持的视频编码器: {codec}，"
                    f"支持的编码器: {', '.join(self.VALID_VIDEO_CODECS)}"
                )

        # 验证音频编码器
        if "audio_codec" in ffmpeg:
            codec = ffmpeg["audio_codec"]
            if codec not in self.VALID_AUDIO_CODECS:
                raise ConfigValidationError(
                    f"不支持的音频编码器: {codec}，"
                    f"支持的编码器: {', '.join(self.VALID_AUDIO_CODECS)}"
                )

        # 验证比特率
        if "bitrate" in ffmpeg:
            bitrate = ffmpeg["bitrate"]
            if not isinstance(bitrate, str):
                raise ConfigValidationError("比特率必须是字符串")

            # 验证比特率格式（如 "2M", "500K"）
            bitrate_pattern = r'^\d+[KMkm]$'
            if not re.match(bitrate_pattern, bitrate):
                raise ConfigValidationError(
                    f"无效的比特率格式: {bitrate}，"
                    f"正确格式示例: 2M, 500K"
                )

        # 验证帧率
        if "framerate" in ffmpeg:
            framerate = ffmpeg["framerate"]
            if not isinstance(framerate, int):
                raise ConfigValidationError("帧率必须是整数")
            if not (1 <= framerate <= 120):
                raise ConfigValidationError(
                    f"帧率必须在 1-120 之间，当前值: {framerate}"
                )

        # 验证编码预设
        if "preset" in ffmpeg:
            preset = ffmpeg["preset"]
            if preset not in self.VALID_PRESETS:
                raise ConfigValidationError(
                    f"无效的编码预设: {preset}，"
                    f"支持的预设: {', '.join(self.VALID_PRESETS)}"
                )

        # 验证编码调优
        if "tune" in ffmpeg:
            tune = ffmpeg["tune"]
            if tune not in self.VALID_TUNES:
                raise ConfigValidationError(
                    f"无效的编码调优: {tune}，"
                    f"支持的调优: {', '.join(self.VALID_TUNES)}"
                )

    def _validate_source_config(self, config: Dict[str, Any]) -> None:
        """验证录制源配置

        Args:
            config: 配置字典

        Raises:
            ConfigValidationError: 录制源配置无效
        """
        if "source" not in config:
            raise ConfigValidationError("缺少必需的 source 配置")

        source = config["source"]

        # 验证源类型
        if "type" not in source:
            raise ConfigValidationError("source 配置缺少 type 字段")

        source_type = source["type"]
        valid_types = ["screen", "window", "window_bg", "window_region", "network_stream"]

        if source_type not in valid_types:
            raise ConfigValidationError(
                f"无效的录制源类型: {source_type}，"
                f"支持的类型: {', '.join(valid_types)}"
            )

        # 根据源类型验证特定参数
        if source_type == "screen":
            self._validate_screen_source(source)
        elif source_type in ["window", "window_bg", "window_region"]:
            self._validate_window_source(source)
        elif source_type == "network_stream":
            self._validate_network_stream_source(source)

    def _validate_screen_source(self, source: Dict[str, Any]) -> None:
        """验证屏幕录制源配置

        Args:
            source: 录制源配置

        Raises:
            ConfigValidationError: 屏幕录制源配置无效
        """
        # 验证显示器索引
        if "display_index" in source:
            index = source["display_index"]
            if not isinstance(index, int) or index < 1:
                raise ConfigValidationError(
                    f"显示器索引必须是正整数，当前值: {index}"
                )

        # 验证区域配置
        if "region" in source and source["region"] is not None:
            region = source["region"]

            required_fields = ["x", "y", "width", "height"]
            for field in required_fields:
                if field not in region:
                    raise ConfigValidationError(
                        f"区域配置缺少必需字段: {field}"
                    )

            if not all(isinstance(region[f], int) for f in required_fields):
                raise ConfigValidationError("区域配置的所有字段必须是整数")

            if region["width"] <= 0 or region["height"] <= 0:
                raise ConfigValidationError(
                    "区域的宽度和高度必须大于 0"
                )

            if region["x"] < 0 or region["y"] < 0:
                raise ConfigValidationError("区域的 x 和 y 坐标不能为负数")

    def _validate_window_source(self, source: Dict[str, Any]) -> None:
        """验证窗口录制源配置

        Args:
            source: 录制源配置

        Raises:
            ConfigValidationError: 窗口录制源配置无效
        """
        # 至少需要一种窗口标识方式
        has_identifier = any([
            "window_title" in source,
            "window_title_pattern" in source,
            "window_class" in source
        ])

        if not has_identifier:
            raise ConfigValidationError(
                "窗口录制源必须指定至少一种窗口标识方式: "
                "window_title, window_title_pattern, 或 window_class"
            )

        # 验证窗口区域配置（仅 window_region 类型）
        if source["type"] == "window_region":
            if "region" not in source or source["region"] is None:
                raise ConfigValidationError(
                    "window_region 类型必须指定 region 配置"
                )

            region = source["region"]
            required_fields = ["x", "y", "width", "height"]
            for field in required_fields:
                if field not in region:
                    raise ConfigValidationError(
                        f"区域配置缺少必需字段: {field}"
                    )

            if not all(isinstance(region[f], int) for f in required_fields):
                raise ConfigValidationError("区域配置的所有字段必须是整数")

            if region["width"] <= 0 or region["height"] <= 0:
                raise ConfigValidationError(
                    "区域的宽度和高度必须大于 0"
                )

    def _validate_network_stream_source(self, source: Dict[str, Any]) -> None:
        """验证网络流录制源配置

        Args:
            source: 录制源配置

        Raises:
            ConfigValidationError: 网络流录制源配置无效
        """
        # URL 是必需的
        if "url" not in source or not source["url"]:
            raise ConfigValidationError("网络流源必须提供 url 字段")

        url = source["url"]

        # 验证 URL 格式（必须以支持的协议开头）
        supported_protocols = ["rtsp://", "rtmp://", "http://", "https://"]
        if not any(url.startswith(protocol) for protocol in supported_protocols):
            raise ConfigValidationError(
                f"不支持的 URL 协议，支持的协议: {', '.join(supported_protocols)}"
            )

        # 验证传输协议（如果提供）
        if "transport" in source and source["transport"] is not None:
            transport = source["transport"]
            valid_transports = ["tcp", "udp", "auto"]
            if transport not in valid_transports:
                raise ConfigValidationError(
                    f"无效的传输协议: {transport}，"
                    f"支持的协议: {', '.join(valid_transports)}"
                )

        # 验证超时时间（如果提供）
        if "timeout" in source and source["timeout"] is not None:
            timeout = source["timeout"]
            if not isinstance(timeout, int) or timeout <= 0:
                raise ConfigValidationError(
                    f"超时时间必须是正整数（微秒），当前值: {timeout}"
                )

        # 验证重连延迟（如果提供）
        if "reconnect_delay" in source and source["reconnect_delay"] is not None:
            delay = source["reconnect_delay"]
            if not isinstance(delay, int) or delay <= 0:
                raise ConfigValidationError(
                    f"重连延迟必须是正整数（秒），当前值: {delay}"
                )

        # 验证最大重连次数（如果提供）
        if "max_reconnect_attempts" in source and source["max_reconnect_attempts"] is not None:
            attempts = source["max_reconnect_attempts"]
            if not isinstance(attempts, int) or attempts < 0:
                raise ConfigValidationError(
                    f"最大重连次数必须是非负整数，当前值: {attempts}"
                )

    def _validate_process_config(self, config: Dict[str, Any]) -> None:
        """验证进程管理配置

        Args:
            config: 配置字典

        Raises:
            ConfigValidationError: 进程管理配置无效
        """
        if "process" not in config:
            return  # 可选配置，使用默认值

        process = config["process"]

        # 验证崩溃阈值
        if "crash_threshold" in process:
            threshold = process["crash_threshold"]
            if not isinstance(threshold, int) or threshold < 1:
                raise ConfigValidationError(
                    f"崩溃阈值必须是正整数，当前值: {threshold}"
                )

        # 验证崩溃时间窗口
        if "crash_window" in process:
            window = process["crash_window"]
            if not isinstance(window, int) or window < 1:
                raise ConfigValidationError(
                    f"崩溃时间窗口必须是正整数，当前值: {window}"
                )

        # 验证关闭超时
        if "shutdown_timeout" in process:
            timeout = process["shutdown_timeout"]
            if not isinstance(timeout, int) or timeout < 0:
                raise ConfigValidationError(
                    f"关闭超时必须是非负整数，当前值: {timeout}"
                )

    def _validate_logging_config(self, config: Dict[str, Any]) -> None:
        """验证日志配置

        Args:
            config: 配置字典

        Raises:
            ConfigValidationError: 日志配置无效
        """
        if "logging" not in config:
            return  # 可选配置，使用默认值

        logging_config = config["logging"]

        # 验证日志级别
        if "level" in logging_config:
            level = logging_config["level"]
            if level not in self.VALID_LOG_LEVELS:
                raise ConfigValidationError(
                    f"无效的日志级别: {level}，"
                    f"支持的级别: {', '.join(self.VALID_LOG_LEVELS)}"
                )

        # 验证日志文件路径
        if "file" in logging_config and logging_config["file"] is not None:
            log_file = logging_config["file"]
            if not isinstance(log_file, str):
                raise ConfigValidationError("日志文件路径必须是字符串")
