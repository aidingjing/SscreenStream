"""
日志工具

配置统一的日志记录系统
"""

import sys
import logging
from pathlib import Path
from typing import Optional

from src.config.config_parser import ConfigData


def setup_logger(config: ConfigData) -> logging.Logger:
    """配置日志记录器

    Args:
        config: 配置数据对象

    Returns:
        logging.Logger: 配置好的日志记录器
    """
    # 创建日志记录器
    logger = logging.getLogger("ScreenStreamer")
    logger.setLevel(getattr(logging, config.log_level))

    # 清除现有的处理器
    logger.handlers.clear()

    # 创建格式化器
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 添加控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 添加文件处理器（如果配置了日志文件）
    if config.log_file:
        log_file_path = Path(config.log_file)

        # 确保日志文件目录存在
        log_file_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(
            log_file_path,
            mode='a',
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        logger.info(f"日志文件: {log_file_path.absolute()}")

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """获取日志记录器

    Args:
        name: 日志记录器名称（可选）

    Returns:
        logging.Logger: 日志记录器
    """
    if name:
        return logging.getLogger(f"ScreenStreamer.{name}")
    return logging.getLogger("ScreenStreamer")
