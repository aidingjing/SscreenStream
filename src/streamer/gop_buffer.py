"""
GOP (Group of Pictures) 缓冲模块

维护最近 1-2 个 GOP 的 FLV 数据，确保新客户端能正确播放
"""

import logging
from typing import Optional, List
from collections import deque
from dataclasses import dataclass


@dataclass
class FLVTag:
    """FLV 标签信息"""
    data: bytes
    tag_type: int  # 8=audio, 9=video, 18=script
    timestamp: int
    is_keyframe: bool = False  # 是否为关键帧（仅视频）


class GOPBuffer:
    """GOP 缓冲器

    职责：
    1. 缓存 FLV Header + onMetadata
    2. 缓存最近 1-2 个 GOP 的数据
    3. 为新客户端提供完整的初始化数据

    FLV Tag 类型：
    - 8: Audio
    - 9: Video
    - 18: Script Data (onMetadata)
    """

    # FLV 头固定大小
    FLV_HEADER_SIZE = 13  # 9 bytes header + 4 bytes PreviousTagSize0

    # FLV Tag 头大小
    TAG_HEADER_SIZE = 11  # TagType(1) + DataSize(3) + Timestamp(3) + StreamID(3)

    def __init__(self, logger: logging.Logger, max_gop_count: int = 2):
        """初始化 GOP 缓冲器

        Args:
            logger: 日志记录器
            max_gop_count: 最多缓存几个 GOP（默认 2）
        """
        self.logger = logger
        self.max_gop_count = max_gop_count

        # FLV 头部数据
        self._flv_header: Optional[bytes] = None
        self._metadata_tag: Optional[bytes] = None

        # GOP 数据缓存（使用 deque 实现滑动窗口）
        self._gop_buffer: deque[bytes] = deque(maxlen=max_gop_count)

        # 当前 GOP 累积数据
        self._current_gop: List[bytes] = []

        # 统计信息
        self._total_bytes = 0

    def is_ready(self) -> bool:
        """检查是否就绪（FLV Header + Metadata + 至少一个关键帧）

        Returns:
            bool: True 表示可以为新客户端提供数据
        """
        return (
            self._flv_header is not None and
            self._metadata_tag is not None and
            (len(self._gop_buffer) > 0 or len(self._current_gop) > 0)
        )

    def get_initial_data(self) -> bytes:
        """获取新客户端需要的初始化数据

        Returns:
            bytes: FLV Header + Metadata + 完整 GOP 数据
        """
        if not self.is_ready():
            return b''

        # 组合数据：Header + Metadata + GOPs
        result = bytearray()

        # 1. FLV Header
        result.extend(self._flv_header)

        # 2. Metadata Tag（如果有）
        if self._metadata_tag:
            result.extend(self._metadata_tag)

        # 3. 最近的一个完整 GOP（优先使用已保存的 GOP，否则使用当前正在累积的 GOP）
        gop_source = "无"
        if self._gop_buffer:
            # 取最新的 GOP（最后一个）
            latest_gop = self._gop_buffer[-1]
            result.extend(latest_gop)
            gop_source = "已保存"
        elif self._current_gop:
            # 如果没有已保存的 GOP，使用当前正在累积的 GOP
            current_gop_data = b''.join(self._current_gop)
            result.extend(current_gop_data)
            gop_source = "当前累积"

        self.logger.info(
            f"为客户端发送初始化数据: "
            f"Header={len(self._flv_header or b'')}, "
            f"Metadata={len(self._metadata_tag or b'')}, "
            f"GOP={gop_source}, "
            f"总大小={len(result)} bytes"
        )

        return bytes(result)

    def process_data(self, data: bytes) -> tuple[bytes, bytes]:
        """处理 FLV 数据块，提取并缓存 GOP

        Args:
            data: 从 FFmpeg 读取的数据块

        Returns:
            tuple[bytes, bytes]: (initial_data, stream_data)
                - initial_data: 初始化数据（首次调用时返回）
                - stream_data: 原始流数据（用于广播）
        """
        # 如果已经捕获过头，直接返回原始数据
        if self._flv_header is not None:
            return b'', data

        # 第一次捕获：保存原始数据用于返回
        original_data = data

        # 添加到处理缓冲区
        if not hasattr(self, '_process_buffer'):
            self._process_buffer = bytearray()

        self._process_buffer.extend(data)

        # 尝试提取 FLV Header
        if len(self._process_buffer) >= self.FLV_HEADER_SIZE:
            # 验证 FLV 签名
            if self._process_buffer[0:3] != b'FLV':
                self.logger.warning("无效的 FLV 签名")
                self._flv_header = bytes(self._process_buffer[:self.FLV_HEADER_SIZE])
                self._process_buffer.clear()
                return b'', original_data  # 返回原始数据

            # 提取 FLV Header
            self._flv_header = bytes(self._process_buffer[:self.FLV_HEADER_SIZE])
            remaining = bytes(self._process_buffer[self.FLV_HEADER_SIZE:])
            self._process_buffer.clear()

            self.logger.info(f"✅ FLV Header 已捕获: {len(self._flv_header)} bytes")

            # 继续处理剩余数据，查找 Metadata，返回原始数据用于广播
            return self._process_tags(remaining, original_data)

        # Header 还未完整，返回原始数据
        return b'', original_data

    def _process_tags(self, data: bytes, original_data: bytes = None) -> tuple[bytes, bytes]:
        """处理 FLV Tag 数据

        Args:
            data: FLV Tag 数据
            original_data: 原始数据（用于首次捕获时返回）

        Returns:
            tuple[bytes, bytes]: (initial_data, stream_data)
        """
        if not hasattr(self, '_tag_buffer'):
            self._tag_buffer = bytearray()

        self._tag_buffer.extend(data)

        # 持续解析完整的 Tag
        while len(self._tag_buffer) >= self.TAG_HEADER_SIZE:
            # 读取 Tag 头
            tag_type = self._tag_buffer[0]
            data_size = int.from_bytes(self._tag_buffer[1:4], byteorder='big')
            timestamp = int.from_bytes(self._tag_buffer[4:7], byteorder='big')

            # 计算 Tag 总大小（Tag头 + 数据 + PreviousTagSize）
            tag_total_size = self.TAG_HEADER_SIZE + data_size + 4

            # 检查是否有完整的 Tag
            if len(self._tag_buffer) < tag_total_size:
                break

            # 提取完整 Tag
            tag_data = bytes(self._tag_buffer[:tag_total_size])
            self._tag_buffer = self._tag_buffer[tag_total_size:]

            # 处理 Tag
            self._handle_tag(tag_type, tag_data, timestamp)

        # 返回剩余数据和原始数据（首次捕获时）
        remaining = bytes(self._tag_buffer)
        self._tag_buffer.clear()

        # 首次捕获时，返回原始数据用于广播
        if original_data is not None:
            return b'', original_data

        return b'', remaining

    def _handle_tag(self, tag_type: int, tag_data: bytes, timestamp: int) -> None:
        """处理单个 FLV Tag

        Args:
            tag_type: Tag 类型 (8=audio, 9=video, 18=script)
            tag_data: 完整的 Tag 数据（包含 PreviousTagSize）
            timestamp: 时间戳
        """
        # 18 = Script Data (onMetadata)
        if tag_type == 18 and self._metadata_tag is None:
            self._metadata_tag = tag_data
            self.logger.info(f"✅ Metadata Tag 已捕获: {len(tag_data)} bytes")
            return

        # 9 = Video Tag
        if tag_type == 9:
            # 检查是否为关键帧
            # 视频帧类型在第一个字节的高 4 位
            frame_type = (tag_data[self.TAG_HEADER_SIZE] & 0xF0) >> 4
            is_keyframe = (frame_type == 1)  # 1 = keyframe (I-frame)

            if is_keyframe:
                # 遇到新的关键帧，保存当前 GOP
                if self._current_gop:
                    gop_data = b''.join(self._current_gop)
                    self._gop_buffer.append(gop_data)
                    self.logger.debug(
                        f"保存 GOP #{len(self._gop_buffer)}: "
                        f"{len(gop_data)} bytes, {len(self._current_gop)} tags"
                    )

                # 开始新的 GOP
                self._current_gop = [tag_data]
            else:
                # 非关键帧，添加到当前 GOP
                if self._current_gop:
                    self._current_gop.append(tag_data)

        # 8 = Audio Tag
        elif tag_type == 8:
            # 音频帧添加到当前 GOP
            if self._current_gop:
                self._current_gop.append(tag_data)

    def reset(self) -> None:
        """重置缓冲器（FFmpeg 重启时调用）"""
        self._flv_header = None
        self._metadata_tag = None
        self._gop_buffer.clear()
        self._current_gop.clear()
        self._total_bytes = 0

        if hasattr(self, '_process_buffer'):
            del self._process_buffer

        if hasattr(self, '_tag_buffer'):
            del self._tag_buffer

        self.logger.debug("GOP 缓冲器已重置")

    def get_statistics(self) -> dict:
        """获取统计信息

        Returns:
            dict: 统计信息
        """
        return {
            "header_ready": self._flv_header is not None,
            "header_size": len(self._flv_header) if self._flv_header else 0,
            "metadata_ready": self._metadata_tag is not None,
            "metadata_size": len(self._metadata_tag) if self._metadata_tag else 0,
            "gop_count": len(self._gop_buffer),
            "current_gop_tags": len(self._current_gop),
            "ready": self.is_ready()
        }
