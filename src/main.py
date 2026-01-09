"""
主程序入口

WebSocket Screen Streamer - 屏幕录制推流工具
"""

import sys
import argparse
import asyncio
import signal
import platform
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.config_parser import ConfigParser
from src.recorder.ffmpeg_recorder import FFmpegRecorder
from src.recorder.window_helper import WindowHelper
from src.streamer.ws_server import WebSocketStreamer
from src.utils.logger import setup_logger


async def main():
    """主函数"""

    # 0. 设置控制台编码（Windows 兼容）
    if platform.system() == "Windows":
        import io
        # 尝试设置 UTF-8 编码输出
        try:
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding='utf-8', errors='replace'
            )
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer, encoding='utf-8', errors='replace'
            )
        except Exception:
            # 如果设置失败，继续使用默认编码
            pass

    # 1. 解析命令行参数
    args = parse_args()
    config_path = args.config

    # 2. 加载并验证配置
    print(f"📋 加载配置文件: {config_path}")
    try:
        parser = ConfigParser(config_path)
        config = parser.parse()
        print(f"✅ 配置加载成功")
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        sys.exit(1)

    # 3. 初始化日志
    logger = setup_logger(config)
    logger.info("=" * 60)
    logger.info("WebSocket Screen Streamer 启动")
    logger.info("=" * 60)

    # 4. 创建窗口助手（窗口录制时需要）
    window_helper = None
    source_type = config.source.source.type
    if source_type in ["window", "window_bg", "window_region"]:
        logger.info("初始化窗口助手...")
        window_helper = WindowHelper(logger)

    # 5. 创建录制器对象（⚠️ 不启动 FFmpeg）
    logger.info("初始化录制器...")
    recorder = FFmpegRecorder(config, logger)

    if window_helper:
        # 设置窗口助手到 FFmpeg 命令构建器
        recorder.command_builder.window_helper = window_helper

    # 6. 创建 WebSocket 服务器
    logger.info("初始化 WebSocket 推流服务器...")
    server = WebSocketStreamer(config, recorder, logger)

    # 7. 设置信号处理（仅在 Unix 系统上）
    if platform.system() != "Windows":
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(
                sig,
                lambda: asyncio.create_task(shutdown(server, logger))
            )
    else:
        # Windows 上使用传统的信号处理
        # KeyboardInterrupt 会被 __main__ 中的 try-except 捕获
        logger.debug("Windows 系统检测到，跳过信号处理器设置")

    # 8. 启动 WebSocket 服务器（⚠️ 只启动监听，不启动 FFmpeg）
    try:
        await server.start()
        logger.info("✅ 服务器启动完成，等待客户端连接...")
        logger.info("")
        logger.info("=" * 60)
        logger.info("📡 服务已就绪")
        logger.info(f"🌐 监听地址: ws://{config.host}:{config.server_port}")
        logger.info(f"🎬 录制源类型: {source_type}")
        logger.info("=" * 60)
        logger.info("")
        logger.info("💡 提示: 第一个客户端连接时将自动启动 FFmpeg")
        logger.info("💡 提示: 所有客户端断开后将自动关闭 FFmpeg")
        logger.info("")

        # 9. 保持运行，等待信号
        await wait_for_shutdown()

    except Exception as e:
        logger.error(f"❌ 服务器运行异常: {e}", exc_info=True)
        sys.exit(1)

    finally:
        # 10. 优雅退出
        logger.info("正在关闭服务器...")
        await server.stop()
        logger.info("✅ 服务器已关闭")
        logger.info("=" * 60)


def parse_args() -> argparse.Namespace:
    """解析命令行参数

    Returns:
        argparse.Namespace: 解析后的参数
    """
    parser = argparse.ArgumentParser(
        description="WebSocket Screen Streamer - 屏幕录制推流工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用默认配置文件
  python main.py

  # 指定配置文件
  python main.py --config config/config.json

  # 列出所有窗口
  python main.py --list-windows
        """
    )

    parser.add_argument(
        "--config",
        type=str,
        default="config/config.example.json",
        help="配置文件路径（默认: config/config.example.json）"
    )

    parser.add_argument(
        "--list-windows",
        action="store_true",
        help="列出所有可见窗口（辅助功能）"
    )

    return parser.parse_args()


async def wait_for_shutdown():
    """等待关闭信号"""
    # 创建一个永远不会完成的 Future
    future = asyncio.Future()
    await future


async def shutdown(server: WebSocketStreamer, logger):
    """关闭处理

    Args:
        server: WebSocket 服务器
        logger: 日志记录器
    """
    logger.info("\n收到关闭信号，正在优雅退出...")

    # 停止服务器
    await server.stop()

    # 退出程序
    sys.exit(0)


def list_windows_command():
    """列出所有窗口（辅助工具）"""
    import sys

    print("\n=== 列出所有可见窗口 ===\n")

    try:
        from recorder.window_helper import WindowHelper
        from utils.logger import setup_logger
        from config.config_parser import ConfigData, SourceConfig, ScreenSourceConfig

        # 创建临时配置用于日志
        temp_config = ConfigData(
            server_port=8765,
            host="0.0.0.0",
            ffmpeg_path="ffmpeg.exe",
            video_codec="libx264",
            audio_codec="aac",
            bitrate="2M",
            framerate=30,
            preset="ultrafast",
            tune="zerolatency",
            source=SourceConfig(source=ScreenSourceConfig(type="screen")),
            crash_threshold=3,
            crash_window=60,
            shutdown_timeout=30,
            log_level="INFO",
            log_file=None
        )

        logger = setup_logger(temp_config)
        helper = WindowHelper(logger)

        windows = helper.list_all_windows()

        print(f"{'HWND':<12} | {'窗口标题'}")
        print("-" * 80)

        for hwnd, title in windows:
            print(f"{hwnd:<12} | {title}")

        print(f"\n共 {len(windows)} 个窗口\n")

    except Exception as e:
        print(f"❌ 列出窗口失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # 解析参数
    args = parse_args()

    # 列出窗口的辅助命令
    if args.list_windows:
        list_windows_command()
        sys.exit(0)

    # 主程序
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n用户中断，程序退出")
        sys.exit(0)
