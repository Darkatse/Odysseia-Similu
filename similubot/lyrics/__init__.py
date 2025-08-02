"""
歌词模块 - 歌词获取、解析和同步功能

提供歌词搜索、LRC格式解析、时间同步等功能。
支持网易云音乐API和多种歌词格式。
"""

from .lyrics_client import NetEaseCloudMusicClient
from .lyrics_parser import LyricsParser, LyricLine
from .lyrics_manager import LyricsManager

__all__ = [
    'NetEaseCloudMusicClient',
    'LyricsParser', 
    'LyricLine',
    'LyricsManager'
]
