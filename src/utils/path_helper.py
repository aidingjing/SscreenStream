"""
路径处理工具

提供路径相关的辅助函数
"""

from pathlib import Path


def get_builtin_ffmpeg_path() -> Path:
    """获取内置 FFmpeg 可执行文件路径

    Returns:
        Path: FFmpeg 可执行文件的绝对路径

    Raises:
        FileNotFoundError: FFmpeg 可执行文件不存在
    """
    # 获取项目根目录（假设此文件位于 src/utils/）
    project_root = Path(__file__).parent.parent.parent
    ffmpeg_dir = project_root / "ffmpeg"

    # Windows 平台
    ffmpeg_name = "ffmpeg.exe"
    ffmpeg_path = ffmpeg_dir / ffmpeg_name

    if not ffmpeg_path.exists():
        raise FileNotFoundError(
            f"找不到内置 FFmpeg: {ffmpeg_path.absolute()}\n"
            f"请确保 FFmpeg 可执行文件位于 {ffmpeg_dir.absolute()} 目录下"
        )

    return ffmpeg_path


def resolve_relative_path(relative_path: str, base_dir: Path) -> Path:
    """解析相对路径为绝对路径

    Args:
        relative_path: 相对路径
        base_dir: 基准目录

    Returns:
        Path: 绝对路径
    """
    path = Path(relative_path)

    # 如果是绝对路径，直接返回
    if path.is_absolute():
        return path

    # 相对于基准目录
    return base_dir / path


def ensure_directory_exists(dir_path: Path) -> None:
    """确保目录存在，不存在则创建

    Args:
        dir_path: 目录路径
    """
    dir_path.mkdir(parents=True, exist_ok=True)
