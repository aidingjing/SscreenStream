"""
自定义异常模块

定义了项目中使用的所有自定义异常类
"""


class ScreenStreamerError(Exception):
    """基础异常类

    所有项目特定异常的基类
    """
    pass


class ConfigValidationError(ScreenStreamerError):
    """配置验证错误

    当配置文件验证失败时抛出
    """
    pass


class RecorderStartupError(ScreenStreamerError):
    """录制器启动错误

    当录制器（如 FFmpeg）启动失败时抛出
    """
    pass


class ProcessManagerError(ScreenStreamerError):
    """进程管理错误

    当进程管理操作失败时抛出
    """
    pass


class WindowNotFoundError(ScreenStreamerError):
    """窗口未找到错误

    当无法找到指定的窗口时抛出
    """
    pass


class StreamError(ScreenStreamerError):
    """推流错误

    当推流操作失败时抛出
    """
    pass
