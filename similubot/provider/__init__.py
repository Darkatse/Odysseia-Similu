"""
音频提供者模块 - 处理各种音频源的提取和下载

该模块负责从不同的音频源（YouTube、Catbox等）提取音频信息和下载音频文件。
遵循单一职责原则，每个提供者只处理一种音频源。
"""

from .base import BaseAudioProvider
from .youtube_provider import YouTubeProvider
from .catbox_provider import CatboxProvider
from .provider_factory import AudioProviderFactory

__all__ = [
    "BaseAudioProvider",
    "YouTubeProvider", 
    "CatboxProvider",
    "AudioProviderFactory"
]
