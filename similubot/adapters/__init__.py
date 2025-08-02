"""
适配器模块 - 提供新旧架构间的兼容性

该模块包含各种适配器，确保新架构与现有代码的兼容性。
在重构过程中提供平滑的迁移路径。
"""

from .music_player_adapter import MusicPlayerAdapter

__all__ = [
    "MusicPlayerAdapter"
]
