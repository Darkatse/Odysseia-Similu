"""LRC格式歌词解析器和同步逻辑"""

import logging
import re
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class LyricLine:
    """表示带时间戳的单行歌词"""
    timestamp: float  # 时间（秒）
    text: str  # 歌词文本
    translated_text: Optional[str] = None  # 翻译文本（如果可用）


class LyricsParser:
    """
    LRC格式歌词解析器，具有同步功能
    
    处理LRC时间戳的解析，并提供基于播放位置
    查找当前歌词行的方法。
    """

    def __init__(self):
        """初始化歌词解析器"""
        self.logger = logging.getLogger("similubot.lyrics.lyrics_parser")

        # LRC时间戳模式: [mm:ss.xxx] 或 [mm:ss]
        self.timestamp_pattern = re.compile(r'\[(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\]')

        self.logger.debug("歌词解析器初始化完成")

    def parse_lrc_lyrics(self, lrc_content: str, translated_lrc: str = "") -> List[LyricLine]:
        """
        将LRC格式歌词解析为LyricLine对象列表
        
        Args:
            lrc_content: LRC格式歌词内容
            translated_lrc: 可选的翻译歌词内容
            
        Returns:
            按时间戳排序的LyricLine对象列表
        """
        try:
            if not lrc_content or not lrc_content.strip():
                self.logger.debug("提供了空歌词内容")
                return []

            # 解析主歌词
            main_lyrics = self._parse_single_lrc(lrc_content)

            # 如果可用，解析翻译歌词
            translated_lyrics = {}
            if translated_lrc and translated_lrc.strip():
                translated_lines = self._parse_single_lrc(translated_lrc)
                # 创建时间戳到翻译文本的映射
                for line in translated_lines:
                    translated_lyrics[line.timestamp] = line.text

            # 合并主歌词和翻译歌词
            combined_lyrics = []
            for line in main_lyrics:
                translated_text = translated_lyrics.get(line.timestamp)
                combined_line = LyricLine(
                    timestamp=line.timestamp,
                    text=line.text,
                    translated_text=translated_text
                )
                combined_lyrics.append(combined_line)

            # 按时间戳排序
            combined_lyrics.sort(key=lambda x: x.timestamp)

            self.logger.info(f"解析了 {len(combined_lyrics)} 行歌词")
            return combined_lyrics

        except Exception as e:
            self.logger.error(f"解析LRC歌词时出错: {e}", exc_info=True)
            return []

    def _parse_single_lrc(self, lrc_content: str) -> List[LyricLine]:
        """
        解析单个LRC内容字符串
        
        Args:
            lrc_content: LRC格式内容
            
        Returns:
            LyricLine对象列表
        """
        lines = []

        for line in lrc_content.split('\n'):
            line = line.strip()
            if not line:
                continue

            # 查找行中的所有时间戳
            timestamps = self.timestamp_pattern.findall(line)
            if not timestamps:
                continue

            # 提取最后一个时间戳后的文本
            text = self.timestamp_pattern.sub('', line).strip()

            # 跳过空文本行（但保留器乐标记）
            if not text and not self._is_instrumental_marker(line):
                continue

            # 转换每个时间戳并创建歌词行
            for timestamp_match in timestamps:
                try:
                    timestamp_seconds = self._convert_timestamp_to_seconds(timestamp_match)
                    lyric_line = LyricLine(timestamp=timestamp_seconds, text=text)
                    lines.append(lyric_line)
                except ValueError as e:
                    self.logger.warning(f"行 '{line}' 中的时间戳无效: {e}")
                    continue

        return lines

    def _convert_timestamp_to_seconds(self, timestamp_match: Tuple[str, str, str]) -> float:
        """
        将LRC时间戳转换为秒
        
        Args:
            timestamp_match: (分钟, 秒, 毫秒) 的元组
            
        Returns:
            以浮点数表示的时间（秒）
        """
        minutes, seconds, milliseconds = timestamp_match

        try:
            total_seconds = int(minutes) * 60 + int(seconds)

            # 如果存在，添加毫秒
            if milliseconds:
                # 填充或截断为3位数
                ms_str = milliseconds.ljust(3, '0')[:3]
                total_seconds += int(ms_str) / 1000.0

            return total_seconds

        except ValueError as e:
            raise ValueError(f"时间戳格式无效: {timestamp_match}") from e

    def _is_instrumental_marker(self, line: str) -> bool:
        """
        检查行是否为器乐标记
        
        Args:
            line: 要检查的LRC行
            
        Returns:
            如果行似乎是器乐标记则返回True
        """
        # 常见的器乐标记
        instrumental_patterns = [
            r'\[00:00\.000\]',  # 常见开始标记
            r'作词',  # 作词人信用
            r'作曲',  # 作曲人信用
            r'编曲',  # 编曲人信用
            r'制作',  # 制作人信用
        ]

        for pattern in instrumental_patterns:
            if re.search(pattern, line):
                return True

        return False

    def get_current_lyric(self, lyrics: List[LyricLine], current_position: float) -> Optional[LyricLine]:
        """
        基于播放位置获取当前歌词行
        
        Args:
            lyrics: 解析的歌词行列表
            current_position: 当前播放位置（秒）
            
        Returns:
            当前LyricLine或如果没有找到合适的行则返回None
        """
        if not lyrics:
            return None

        # 找到已经过去的最近歌词行
        current_line = None

        for line in lyrics:
            if line.timestamp <= current_position:
                current_line = line
            else:
                break  # 行按时间戳排序

        return current_line

    def get_upcoming_lyric(self, lyrics: List[LyricLine], current_position: float) -> Optional[LyricLine]:
        """
        获取下一个即将到来的歌词行
        
        Args:
            lyrics: 解析的歌词行列表
            current_position: 当前播放位置（秒）
            
        Returns:
            下一个LyricLine或如果没有即将到来的行则返回None
        """
        if not lyrics:
            return None

        for line in lyrics:
            if line.timestamp > current_position:
                return line

        return None

    def get_lyrics_since_last_update(
        self,
        lyrics: List[LyricLine],
        last_position: float,
        current_position: float,
        max_lines: int = 3
    ) -> List[LyricLine]:
        """
        获取在上次更新和当前位置之间出现的歌词
        
        此方法通过返回自上次更新以来应该显示的所有歌词，
        帮助确保在快节奏部分不会跳过歌词。
        
        Args:
            lyrics: 解析的歌词行列表
            last_position: 上次更新时的播放位置（秒）
            current_position: 当前播放位置（秒）
            max_lines: 返回的最大行数
            
        Returns:
            在时间间隔内出现的LyricLine对象列表
        """
        if not lyrics or current_position <= last_position:
            return []

        # 找到在last_position和current_position之间出现的歌词
        interval_lyrics = []

        for line in lyrics:
            # 包括在last_position之后开始且在current_position之前/时的歌词
            if last_position < line.timestamp <= current_position:
                interval_lyrics.append(line)

        # 限制为max_lines以避免显示过多
        if len(interval_lyrics) > max_lines:
            # 保留最近的行
            interval_lyrics = interval_lyrics[-max_lines:]

        self.logger.debug(f"在 {last_position:.1f}s 和 {current_position:.1f}s 之间找到 {len(interval_lyrics)} 行歌词")
        return interval_lyrics

    def get_lyric_context(
        self,
        lyrics: List[LyricLine],
        current_position: float,
        context_lines: int = 1
    ) -> Dict[str, Any]:
        """
        获取歌词上下文，包括当前、前一行和下一行

        Args:
            lyrics: 解析的歌词行列表
            current_position: 当前播放位置（秒）
            context_lines: 当前行前后的上下文行数

        Returns:
            包含歌词上下文信息的字典
        """
        if not lyrics:
            return {
                'current': None,
                'previous': [],
                'next': [],
                'progress': 0.0
            }

        # 找到当前行索引
        current_index = -1
        for i, line in enumerate(lyrics):
            if line.timestamp <= current_position:
                current_index = i
            else:
                break

        # 获取当前行
        current_line = lyrics[current_index] if current_index >= 0 else None

        # 获取前面的行
        previous_lines = []
        if current_index > 0:
            start_idx = max(0, current_index - context_lines)
            previous_lines = lyrics[start_idx:current_index]

        # 获取后面的行
        next_lines = []
        if current_index >= 0 and current_index < len(lyrics) - 1:
            end_idx = min(len(lyrics), current_index + 1 + context_lines)
            next_lines = lyrics[current_index + 1:end_idx]

        # 计算当前行内的进度
        progress = 0.0
        if current_line and current_index < len(lyrics) - 1:
            next_line = lyrics[current_index + 1]
            line_duration = next_line.timestamp - current_line.timestamp
            if line_duration > 0:
                elapsed = current_position - current_line.timestamp
                progress = min(1.0, max(0.0, elapsed / line_duration))

        return {
            'current': current_line,
            'previous': previous_lines,
            'next': next_lines,
            'progress': progress,
            'total_lines': len(lyrics),
            'current_index': current_index
        }

    def is_instrumental_track(self, lyrics: List[LyricLine]) -> bool:
        """
        确定曲目是否为器乐曲

        Args:
            lyrics: 解析的歌词行列表

        Returns:
            如果曲目似乎是器乐曲则返回True
        """
        if not lyrics:
            return True

        # 检查是否所有行都为空或仅包含元数据
        text_lines = 0
        for line in lyrics:
            if line.text and line.text.strip():
                # 跳过常见的元数据模式
                if not any(pattern in line.text for pattern in ['作词', '作曲', '编曲', '制作']):
                    text_lines += 1

        # 如果少于3行实际歌词则认为是器乐曲
        return text_lines < 3

    def format_lyric_display(self, lyric_line: LyricLine, show_translation: bool = True) -> str:
        """
        格式化歌词行以供显示

        Args:
            lyric_line: 要格式化的LyricLine
            show_translation: 是否包含翻译（如果可用）

        Returns:
            格式化的歌词字符串
        """
        if not lyric_line or not lyric_line.text:
            return ""

        display_parts = [lyric_line.text]

        # 如果可用且请求，添加翻译
        if show_translation and lyric_line.translated_text:
            display_parts.append(f"*{lyric_line.translated_text}*")

        return "\n".join(display_parts)

    @staticmethod
    def format_time(seconds: float) -> str:
        """
        将秒数格式化为MM:SS格式

        Args:
            seconds: 时间（秒）

        Returns:
            格式化的时间字符串
        """
        seconds = int(seconds)
        minutes, secs = divmod(seconds, 60)
        return f"{minutes:02d}:{secs:02d}"
