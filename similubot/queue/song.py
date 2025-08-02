"""
歌曲数据模型 - 定义歌曲的数据结构和基本操作

提供歌曲信息的统一数据模型，支持不同音频源的歌曲信息。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import discord

from similubot.core.interfaces import AudioInfo, SongInfo


@dataclass
class Song(SongInfo):
    """
    歌曲数据类
    
    包含歌曲的所有相关信息，包括音频信息、请求者和添加时间。
    实现了 SongInfo 接口，提供统一的歌曲信息访问。
    """
    audio_info: AudioInfo
    requester: discord.Member
    added_at: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """初始化后处理"""
        # 确保 added_at 是 datetime 对象
        if isinstance(self.added_at, str):
            self.added_at = datetime.fromisoformat(self.added_at)
    
    @property
    def title(self) -> str:
        """获取歌曲标题"""
        return self.audio_info.title
    
    @property
    def duration(self) -> int:
        """获取歌曲时长（秒）"""
        return self.audio_info.duration
    
    @property
    def url(self) -> str:
        """获取歌曲URL"""
        return self.audio_info.url
    
    @property
    def uploader(self) -> str:
        """获取上传者"""
        return self.audio_info.uploader
    
    @property
    def file_path(self) -> Optional[str]:
        """获取文件路径"""
        return self.audio_info.file_path
    
    @property
    def thumbnail_url(self) -> Optional[str]:
        """获取缩略图URL"""
        return self.audio_info.thumbnail_url
    
    @property
    def file_size(self) -> Optional[int]:
        """获取文件大小"""
        return self.audio_info.file_size
    
    @property
    def file_format(self) -> Optional[str]:
        """获取文件格式"""
        return self.audio_info.file_format
    
    def format_duration(self) -> str:
        """
        格式化时长为可读字符串
        
        Returns:
            格式化的时长字符串 (例: "3:45")
        """
        minutes = self.duration // 60
        seconds = self.duration % 60
        return f"{minutes}:{seconds:02d}"
    
    def get_display_info(self) -> dict:
        """
        获取用于显示的歌曲信息
        
        Returns:
            包含显示信息的字典
        """
        return {
            'title': self.title,
            'duration': self.format_duration(),
            'uploader': self.uploader,
            'requester': self.requester.display_name,
            'added_at': self.added_at.strftime("%Y-%m-%d %H:%M:%S"),
            'url': self.url,
            'thumbnail_url': self.thumbnail_url
        }
    
    def to_dict(self) -> dict:
        """
        转换为字典格式（用于持久化）
        
        Returns:
            歌曲信息字典
        """
        return {
            'title': self.title,
            'duration': self.duration,
            'url': self.url,
            'uploader': self.uploader,
            'file_path': self.file_path,
            'thumbnail_url': self.thumbnail_url,
            'file_size': self.file_size,
            'file_format': self.file_format,
            'requester_id': self.requester.id,
            'requester_name': self.requester.display_name,
            'added_at': self.added_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: dict, guild: discord.Guild) -> Optional['Song']:
        """
        从字典创建歌曲对象（用于持久化恢复）
        
        Args:
            data: 歌曲信息字典
            guild: Discord服务器对象
            
        Returns:
            歌曲对象，失败时返回None
        """
        try:
            # 获取请求者
            requester = guild.get_member(data['requester_id'])
            if not requester:
                # 创建虚拟成员对象
                class MockMember:
                    def __init__(self, user_id: int, name: str, guild_obj: discord.Guild):
                        self.id = user_id
                        self.display_name = name
                        self.guild = guild_obj
                
                requester = MockMember(data['requester_id'], data['requester_name'], guild)
            
            # 创建音频信息
            audio_info = AudioInfo(
                title=data['title'],
                duration=data['duration'],
                url=data['url'],
                uploader=data['uploader'],
                file_path=data.get('file_path'),
                thumbnail_url=data.get('thumbnail_url'),
                file_size=data.get('file_size'),
                file_format=data.get('file_format')
            )
            
            # 创建歌曲对象
            return cls(
                audio_info=audio_info,
                requester=requester,
                added_at=datetime.fromisoformat(data['added_at'])
            )
            
        except Exception:
            return None
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"{self.title} - {self.uploader} ({self.format_duration()})"
    
    def __repr__(self) -> str:
        """调试字符串表示"""
        return f"Song(title='{self.title}', duration={self.duration}, requester='{self.requester.display_name}')"
