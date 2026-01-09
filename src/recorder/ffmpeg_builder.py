"""
FFmpeg 命令构建器

根据配置构建 FFmpeg 命令行参数
"""

from typing import List, Optional
import logging

from src.config.config_parser import (
    ConfigData,
    ScreenSourceConfig,
    WindowSourceConfig
)
from src.exceptions import RecorderStartupError


class FFmpegCommandBuilder:
    """FFmpeg 命令构建器

    职责：
    1. 根据配置构建 FFmpeg 命令行参数
    2. 支持屏幕录制（gdigrab）
    3. 支持窗口录制
    4. 支持区域录制
    """

    def __init__(
        self,
        config: ConfigData,
        window_helper: Optional["WindowHelper"] = None
    ):
        """初始化构建器

        Args:
            config: 配置数据对象
            window_helper: 窗口助手（窗口录制时需要）
        """
        self.config = config
        self.window_helper = window_helper
        self.logger = logging.getLogger("ScreenStreamer.FFmpegBuilder")

    def build(self) -> List[str]:
        """构建完整的 FFmpeg 命令

        Returns:
            List[str]: 命令行参数列表
            示例: ["ffmpeg.exe", "-f", "gdigrab", ...]
        """
        cmd = []

        # FFmpeg 可执行文件路径
        cmd.append(self.config.ffmpeg_path)

        # 输入参数（录制源）
        cmd.extend(self._build_input_args())

        # 视频编码参数
        cmd.extend(self._build_video_args())

        # 音频编码参数
        cmd.extend(self._build_audio_args())

        # 输出参数（stdout）
        cmd.extend(self._build_output_args())

        self.logger.debug(f"FFmpeg 命令: {' '.join(cmd)}")

        return cmd

    def __call__(self) -> List[str]:
        """使对象可调用，适配 ProcessManager 的策略接口"""
        return self.build()

    def _build_input_args(self) -> List[str]:
        """构建输入参数（录制源）"""
        args = []
        source = self.config.source.source

        # 基础参数
        args.extend([
            "-f", "gdigrab",
            "-framerate", str(self.config.framerate),
            "-rtbufsize", "100M"  # 缓冲区大小，避免丢帧
        ])

        # 根据源类型构建参数
        if isinstance(source, ScreenSourceConfig):
            args.extend(self._build_screen_input(source))
        elif isinstance(source, WindowSourceConfig):
            args.extend(self._build_window_input(source))

        return args

    def _build_screen_input(self, screen_config: ScreenSourceConfig) -> List[str]:
        """构建屏幕录制输入参数

        示例 1 - 全屏录制:
            "-i", "desktop"

        示例 2 - 区域录制:
            "-i", "desktop",
            "-offset_x", "100",
            "-offset_y", "100",
            "-video_size", "1920x1080"
        """
        args = []

        # 输入源：桌面
        args.append("-i")
        args.append("desktop")

        # 区域录制
        if screen_config.region:
            region = screen_config.region
            args.extend([
                "-offset_x", str(region.x),
                "-offset_y", str(region.y),
                "-video_size", f"{region.width}x{region.height}"
            ])

        return args

    def _build_window_input(self, window_config: WindowSourceConfig) -> List[str]:
        """构建窗口录制输入参数

        示例 1 - 完整窗口:
            "-i", "title=窗口标题"

        示例 2 - 窗口区域:
            "-i", "title=窗口标题",
            "-offset_x", "10",
            "-offset_y", "20",
            "-video_size", "800x600"
        """
        args = []

        # 查找窗口句柄（验证窗口存在）
        hwnd = self._find_window_handle(window_config)

        if not hwnd:
            raise RecorderStartupError(
                f"找不到窗口: {window_config.window_title}"
            )

        # 验证窗口状态
        if self.window_helper:
            if not self.window_helper.validate_window(hwnd):
                self.logger.warning(
                    f"窗口 {hwnd} 状态异常，可能无法正常录制"
                )

        # 构建输入源
        args.append("-i")

        if window_config.window_title:
            # 使用窗口标题
            input_source = f"title={window_config.window_title}"
        else:
            # 使用窗口句柄（FFmpeg 不直接支持，需要获取标题）
            title = self.window_helper.get_window_title(hwnd)
            input_source = f"title={title}"

        args.append(input_source)

        # 窗口区域录制
        if window_config.region:
            region = window_config.region
            args.extend([
                "-offset_x", str(region.x),
                "-offset_y", str(region.y),
                "-video_size", f"{region.width}x{region.height}"
            ])

        return args

    def _build_video_args(self) -> List[str]:
        """构建视频编码参数

        示例: ["-c:v", "libx264", "-preset", "ultrafast",
                "-tune", "zerolatency", "-b:v", "2M"]
        """
        args = []

        # 视频编码器
        args.extend(["-c:v", self.config.video_codec])

        # 编码预设（速度/压缩比平衡）
        args.extend(["-preset", self.config.preset])

        # 编码调优
        args.extend(["-tune", self.config.tune])

        # H.264 profile 和 level（FLV 兼容性）
        args.extend(["-profile:v", "baseline"])
        args.extend(["-level", "3.1"])

        # 像素格式
        args.extend(["-pix_fmt", "yuv420p"])

        # 比特率
        args.extend(["-b:v", self.config.bitrate])

        # 关键帧间隔（GOP）
        args.extend(["-g", "30"])  # 每 30 帧一个关键帧

        return args

    def _build_audio_args(self) -> List[str]:
        """构建音频编码参数

        示例: ["-c:a", "aac", "-b:a", "128k"]
        """
        args = []

        # 音频编码器
        args.extend(["-c:a", self.config.audio_codec])

        # 音频比特率
        args.extend(["-b:a", "128k"])

        # 音频采样率
        args.extend(["-ar", "44100"])

        return args

    def _build_output_args(self) -> List[str]:
        """构建输出参数（stdout）

        输出到 stdout，格式为 FLV（适合 flv.js 播放器）
        """
        args = []

        # 输出格式：FLV（适合 flv.js WebSocket 播放）
        args.extend(["-f", "flv"])

        # 移除 -flvflags no_duration_filesize，保留完整的 FLV 头和元数据
        # 这样可以支持多客户端场景，新客户端能获取完整的初始化信息
        # args.extend(["-flvflags", "no_duration_filesize"])  # 已移除

        # 输出到标准输出
        args.append("pipe:1")

        return args

    def _find_window_handle(self, window_config: WindowSourceConfig) -> Optional[int]:
        """查找窗口句柄

        Args:
            window_config: 窗口录制源配置

        Returns:
            Optional[int]: 窗口句柄，找不到返回 None
        """
        if not self.window_helper:
            self.logger.warning("窗口助手未初始化，跳过窗口查找")
            return None

        # 按优先级尝试不同的查找方式
        if window_config.window_title_pattern:
            return self.window_helper.find_window_by_pattern(
                window_config.window_title_pattern
            )

        if window_config.window_title:
            return self.window_helper.find_window_by_title(
                window_config.window_title,
                exact_match=not window_config.find_by_substring,
                case_sensitive=window_config.case_sensitive
            )

        if window_config.window_class:
            # TODO: 实现按窗口类名查找
            self.logger.warning("按窗口类名查找暂未实现")
            return None

        return None
