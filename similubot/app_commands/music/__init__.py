"""
音乐领域命令模块

包含所有音乐相关的Slash命令实现：
- 音乐搜索和添加
- 队列管理
- 播放控制
"""

from .search_commands import MusicSearchCommands
from .queue_commands import QueueManagementCommands
from .playback_commands import PlaybackControlCommands

__all__ = [
    'MusicSearchCommands',
    'QueueManagementCommands',
    'PlaybackControlCommands'
]