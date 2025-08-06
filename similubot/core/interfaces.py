"""
核心接口定义 - 定义系统各模块间的抽象接口

提供依赖倒置的基础，减少模块间的耦合度。
遵循单一职责原则，每个接口只定义一个明确的职责。
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Tuple, Union
from dataclasses import dataclass
from datetime import datetime
import discord

from similubot.progress.base import ProgressCallback


@dataclass
class AudioInfo:
    """音频信息数据类"""
    title: str
    duration: int
    url: str
    uploader: str
    file_path: Optional[str] = None
    thumbnail_url: Optional[str] = None
    file_size: Optional[int] = None
    file_format: Optional[str] = None


@dataclass
class NetEaseSearchResult:
    """
    网易云音乐搜索结果数据类

    包含搜索结果的基本信息，用于用户选择和后续处理。
    """
    song_id: str
    title: str
    artist: str
    album: str
    cover_url: Optional[str] = None
    duration: Optional[int] = None  # 歌曲时长（秒）

    def get_display_name(self) -> str:
        """
        获取用于显示的歌曲名称

        Returns:
            格式化的歌曲显示名称
        """
        return f"{self.title} - {self.artist}"

    def get_full_display_info(self) -> str:
        """
        获取完整的显示信息

        Returns:
            包含专辑信息的完整显示名称
        """
        if self.album and self.album != self.title:
            return f"{self.title} - {self.artist} ({self.album})"
        return self.get_display_name()

    def format_duration(self) -> str:
        """
        格式化歌曲时长

        Returns:
            格式化的时长字符串，如 "3:45"
        """
        if self.duration is None:
            return "未知时长"

        minutes = self.duration // 60
        seconds = self.duration % 60
        return f"{minutes}:{seconds:02d}"


@dataclass
class SongInfo:
    """歌曲信息数据类"""
    audio_info: AudioInfo
    requester: discord.Member
    added_at: datetime
    
    @property
    def title(self) -> str:
        return self.audio_info.title
    
    @property
    def duration(self) -> int:
        return self.audio_info.duration
    
    @property
    def url(self) -> str:
        return self.audio_info.url
    
    @property
    def uploader(self) -> str:
        return self.audio_info.uploader


class IAudioProvider(ABC):
    """音频提供者接口 - 定义音频源的基本操作"""
    
    @abstractmethod
    def is_supported_url(self, url: str) -> bool:
        """检查URL是否被支持"""
        pass
    
    @abstractmethod
    async def extract_audio_info(self, url: str) -> Optional[AudioInfo]:
        """提取音频信息"""
        pass
    
    @abstractmethod
    async def download_audio(self, url: str, progress_callback: Optional[ProgressCallback] = None) -> Tuple[bool, Optional[AudioInfo], Optional[str]]:
        """下载音频文件"""
        pass


class IQueueManager(ABC):
    """队列管理器接口 - 定义队列操作的基本功能"""
    
    @abstractmethod
    async def add_song(self, audio_info: AudioInfo, requester: discord.Member) -> int:
        """添加歌曲到队列"""
        pass
    
    @abstractmethod
    def peek_next_song(self, index: int = 0) -> Optional[SongInfo]:
        """查看指定索引的下一首歌曲但不从队列中移除"""
        pass


    @abstractmethod
    async def get_next_song(self) -> Optional[SongInfo]:
        """获取下一首歌曲"""
        pass
    
    @abstractmethod
    async def skip_current_song(self) -> Optional[SongInfo]:
        """跳过当前歌曲"""
        pass

    @abstractmethod
    async def clear_queue(self) -> int:
        """清空队列"""
        pass

    @abstractmethod
    async def replace_user_song(self, user: 'discord.Member', new_audio_info: AudioInfo) -> Tuple[bool, Optional[int], Optional[str]]:
        """替换用户在队列中的第一首歌曲"""
        pass
    
    @abstractmethod
    async def get_queue_info(self) -> Dict[str, Any]:
        """获取队列信息"""
        pass
    
    @abstractmethod
    def get_current_song(self) -> Optional[SongInfo]:
        """获取当前歌曲"""
        pass
    
    @abstractmethod
    def update_position(self, position: float) -> None:
        """更新播放位置"""
        pass

    @abstractmethod
    def check_duplicate_for_user(self, audio_info: AudioInfo, user: discord.Member) -> bool:
        """检查歌曲是否为指定用户的重复请求"""
        pass

    @abstractmethod
    def get_user_song_count(self, user: discord.Member) -> int:
        """获取用户当前在队列中的歌曲数量"""
        pass

    @abstractmethod
    def notify_song_finished(self, song: 'SongInfo') -> None:
        """通知歌曲播放完成，从重复检测器中移除"""
        pass

    @abstractmethod
    def get_user_queue_status(self, user: discord.Member) -> Dict[str, Any]:
        """获取用户的详细队列状态"""
        pass

    @abstractmethod
    def can_user_add_song(self, audio_info: AudioInfo, user: discord.Member) -> Tuple[bool, str]:
        """检查用户是否可以添加歌曲（综合检查）"""
        pass


class IVoiceManager(ABC):
    """语音管理器接口 - 定义语音连接和播放控制"""
    
    @abstractmethod
    async def connect_to_channel(self, channel: discord.VoiceChannel) -> Tuple[bool, Optional[str]]:
        """连接到语音频道"""
        pass
    
    @abstractmethod
    async def disconnect_from_guild(self, guild_id: int) -> bool:
        """从服务器断开连接"""
        pass
    
    @abstractmethod
    async def play_audio(self, guild_id: int, source: discord.AudioSource, after_callback: Optional[Any] = None) -> bool:
        """播放音频"""
        pass
    
    @abstractmethod
    def is_playing(self, guild_id: int) -> bool:
        """检查是否正在播放"""
        pass
    
    @abstractmethod
    def is_paused(self, guild_id: int) -> bool:
        """检查是否暂停"""
        pass
    
    @abstractmethod
    def is_connected(self, guild_id: int) -> bool:
        """检查是否已连接"""
        pass


class IPersistenceManager(ABC):
    """持久化管理器接口 - 定义数据持久化操作"""
    
    @abstractmethod
    async def save_queue_state(self, guild_id: int, current_song: Optional[SongInfo], queue: List[SongInfo], current_position: float = 0.0) -> bool:
        """保存队列状态"""
        pass
    
    @abstractmethod
    async def load_queue_state(self, guild_id: int, guild: discord.Guild) -> Optional[Dict[str, Any]]:
        """加载队列状态"""
        pass
    
    @abstractmethod
    async def delete_queue_state(self, guild_id: int) -> bool:
        """删除队列状态"""
        pass
    
    @abstractmethod
    async def get_all_guild_ids(self) -> List[int]:
        """获取所有服务器ID"""
        pass


class IPlaybackEngine(ABC):
    """播放引擎接口 - 定义核心播放逻辑"""
    
    @abstractmethod
    async def add_song_to_queue(self, url: str, requester: discord.Member, progress_callback: Optional[ProgressCallback] = None) -> Tuple[bool, Optional[int], Optional[str]]:
        """添加歌曲到队列"""
        pass
    
    @abstractmethod
    async def skip_song(self, guild_id: int) -> Tuple[bool, Optional[SongInfo], Optional[str]]:
        """跳过歌曲"""
        pass
    
    @abstractmethod
    async def stop_playback(self, guild_id: int) -> Tuple[bool, Optional[str]]:
        """停止播放"""
        pass
    
    @abstractmethod
    async def connect_to_user_channel(self, user: discord.Member) -> Tuple[bool, Optional[str]]:
        """连接到用户语音频道"""
        pass
    
    @abstractmethod
    def get_queue_info(self, guild_id: int) -> Dict[str, Any]:
        """获取队列信息"""
        pass
    
    @abstractmethod
    def is_playing(self, guild_id: int) -> bool:
        """检查是否正在播放"""
        pass


class ISeekManager(ABC):
    """定位管理器接口 - 定义音频定位功能"""
    
    @abstractmethod
    async def seek_to_position(self, guild_id: int, target_seconds: float) -> Tuple[bool, Optional[str]]:
        """定位到指定位置"""
        pass
    
    @abstractmethod
    def get_current_position(self, guild_id: int) -> Optional[float]:
        """获取当前播放位置"""
        pass


# 事件接口
class IPlaybackEventHandler(ABC):
    """播放事件处理器接口"""
    
    @abstractmethod
    async def on_song_started(self, guild_id: int, song: SongInfo) -> None:
        """歌曲开始播放事件"""
        pass
    
    @abstractmethod
    async def on_song_finished(self, guild_id: int, song: SongInfo) -> None:
        """歌曲播放完成事件"""
        pass
    
    @abstractmethod
    async def on_queue_empty(self, guild_id: int) -> None:
        """队列为空事件"""
        pass
    
    @abstractmethod
    async def on_playback_error(self, guild_id: int, error: Exception) -> None:
        """播放错误事件"""
        pass
