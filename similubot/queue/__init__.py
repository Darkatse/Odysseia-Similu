"""
队列管理模块 - 处理音乐队列的管理和持久化

该模块负责音乐队列的所有操作，包括添加、移除、跳过歌曲，以及队列状态的持久化。
遵循单一职责原则，专注于队列相关的业务逻辑。
"""

from .queue_manager import QueueManager
from .persistence_manager import PersistenceManager
from .song import Song

__all__ = [
    "QueueManager",
    "PersistenceManager", 
    "Song"
]
