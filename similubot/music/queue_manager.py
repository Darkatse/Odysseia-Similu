"""音乐队列管理器 - 支持持久化的队列管理"""

import logging
import asyncio
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from dataclasses import dataclass, field
from datetime import datetime
import discord
from .youtube_client import AudioInfo
from .audio_source import UnifiedAudioInfo
from typing import Union

# 避免循环导入
if TYPE_CHECKING:
    from .queue_persistence import QueuePersistence


@dataclass
class Song:
    """Represents a song in the music queue."""
    audio_info: Union[AudioInfo, UnifiedAudioInfo]
    requester: discord.Member
    added_at: datetime = field(default_factory=datetime.now)

    @property
    def title(self) -> str:
        """Get song title."""
        return self.audio_info.title

    @property
    def duration(self) -> int:
        """Get song duration in seconds."""
        return self.audio_info.duration

    @property
    def url(self) -> str:
        """Get song URL."""
        return self.audio_info.url

    @property
    def uploader(self) -> str:
        """Get song uploader."""
        return self.audio_info.uploader


class QueueManager:
    """
    音乐队列管理器 - 管理 Discord 服务器的音乐队列

    提供线程安全的队列操作，包括位置跟踪、歌曲元数据管理和队列持久化。
    """

    def __init__(self, guild_id: int, persistence: Optional['QueuePersistence'] = None):
        """
        初始化队列管理器

        Args:
            guild_id: Discord 服务器 ID
            persistence: 队列持久化管理器（可选）
        """
        self.logger = logging.getLogger("similubot.music.queue_manager")
        self.guild_id = guild_id
        self._queue: List[Song] = []
        self._current_song: Optional[Song] = None
        self._lock = asyncio.Lock()

        # 持久化支持
        self._persistence = persistence
        self._current_position = 0.0  # 当前播放位置（秒）

        self.logger.debug(f"队列管理器初始化完成 - 服务器 {guild_id}")

    def set_persistence(self, persistence: 'QueuePersistence') -> None:
        """设置队列持久化管理器"""
        self._persistence = persistence

    async def _save_state(self) -> None:
        """保存当前队列状态到持久化存储"""
        if self._persistence:
            try:
                await self._persistence.save_queue_state(
                    guild_id=self.guild_id,
                    current_song=self._current_song,
                    queue=self._queue.copy(),
                    current_position=self._current_position
                )
            except Exception as e:
                self.logger.error(f"保存队列状态失败: {e}")

    def update_position(self, position: float) -> None:
        """更新当前播放位置"""
        self._current_position = position

    async def add_song(self, audio_info: Union[AudioInfo, UnifiedAudioInfo], requester: discord.Member) -> int:
        """
        添加歌曲到队列

        Args:
            audio_info: 音频信息
            requester: 请求用户

        Returns:
            队列中的位置（从1开始）
        """
        async with self._lock:
            song = Song(audio_info=audio_info, requester=requester)
            self._queue.append(song)
            position = len(self._queue)

            self.logger.info(f"添加歌曲到队列: {song.title} (位置 {position})")

            # 保存状态
            await self._save_state()

            return position

    async def get_next_song(self) -> Optional[Song]:
        """
        从队列获取下一首歌曲

        Returns:
            下一首歌曲，如果队列为空则返回 None
        """
        async with self._lock:
            if not self._queue:
                return None

            song = self._queue.pop(0)
            self._current_song = song
            self._current_position = 0.0  # 重置播放位置

            self.logger.info(f"获取下一首歌曲: {song.title}")

            # 保存状态
            await self._save_state()

            return song

    async def skip_current_song(self) -> Optional[Song]:
        """
        Skip the current song and get the next one.
        
        Returns:
            Next song or None if queue is empty
        """
        async with self._lock:
            if self._current_song:
                self.logger.info(f"Skipping current song: {self._current_song.title}")
                self._current_song = None
            
            return await self.get_next_song()

    async def jump_to_position(self, position: int) -> Optional[Song]:
        """
        Jump to a specific position in the queue.
        
        Args:
            position: Queue position (1-indexed)
            
        Returns:
            Song at position or None if invalid position
        """
        async with self._lock:
            if position < 1 or position > len(self._queue):
                return None
            
            # Remove songs before the target position
            songs_to_remove = position - 1
            for _ in range(songs_to_remove):
                if self._queue:
                    removed_song = self._queue.pop(0)
                    self.logger.debug(f"Removed song during jump: {removed_song.title}")
            
            # Get the target song
            if self._queue:
                song = self._queue.pop(0)
                self._current_song = song
                self.logger.info(f"Jumped to position {position}: {song.title}")
                return song
            
            return None

    async def clear_queue(self) -> int:
        """
        清空整个队列

        Returns:
            移除的歌曲数量
        """
        async with self._lock:
            count = len(self._queue)
            self._queue.clear()
            self._current_song = None
            self._current_position = 0.0

            self.logger.info(f"清空队列: 移除了 {count} 首歌曲")

            # 保存状态
            await self._save_state()

            return count

    async def restore_from_persistence(self, guild: discord.Guild) -> bool:
        """
        从持久化存储恢复队列状态

        Args:
            guild: Discord 服务器对象

        Returns:
            恢复是否成功
        """
        if not self._persistence:
            return False

        try:
            restored_data = await self._persistence.load_queue_state(self.guild_id, guild)
            if not restored_data:
                return False

            async with self._lock:
                # 恢复队列数据
                self._current_song = restored_data.get('current_song')
                self._queue = restored_data.get('queue', [])
                self._current_position = restored_data.get('current_position', 0.0)

                invalid_songs = restored_data.get('invalid_songs', [])

                self.logger.info(
                    f"队列状态恢复成功 - 服务器 {self.guild_id}: "
                    f"当前歌曲: {'是' if self._current_song else '否'}, "
                    f"队列长度: {len(self._queue)}"
                )

                if invalid_songs:
                    self.logger.warning(f"恢复时发现无效歌曲: {invalid_songs}")

                return True

        except Exception as e:
            self.logger.error(f"从持久化存储恢复队列状态失败: {e}")
            return False

    async def get_queue_info(self) -> Dict[str, Any]:
        """
        Get comprehensive queue information.
        
        Returns:
            Dictionary with queue details
        """
        async with self._lock:
            total_duration = sum(song.duration for song in self._queue)
            
            return {
                "current_song": self._current_song,
                "queue": self._queue.copy(),
                "queue_length": len(self._queue),
                "total_duration": total_duration,
                "is_empty": len(self._queue) == 0
            }

    async def get_current_song(self) -> Optional[Song]:
        """
        Get the currently playing song.
        
        Returns:
            Current song or None if nothing is playing
        """
        async with self._lock:
            return self._current_song

    async def remove_song_at_position(self, position: int) -> Optional[Song]:
        """
        Remove a song at a specific position.
        
        Args:
            position: Queue position (1-indexed)
            
        Returns:
            Removed song or None if invalid position
        """
        async with self._lock:
            if position < 1 or position > len(self._queue):
                return None
            
            removed_song = self._queue.pop(position - 1)
            self.logger.info(f"Removed song at position {position}: {removed_song.title}")
            return removed_song

    async def get_queue_display(self, max_songs: int = 10) -> List[Dict[str, Any]]:
        """
        Get formatted queue information for display.
        
        Args:
            max_songs: Maximum number of songs to include
            
        Returns:
            List of song display information
        """
        async with self._lock:
            display_songs = []
            
            for i, song in enumerate(self._queue[:max_songs], 1):
                display_songs.append({
                    "position": i,
                    "title": song.title,
                    "duration": self._format_duration(song.duration),
                    "uploader": song.uploader,
                    "requester": song.requester.display_name,
                    "url": song.url
                })
            
            return display_songs

    def _format_duration(self, seconds: int) -> str:
        """
        Format duration in seconds to MM:SS or HH:MM:SS format.
        
        Args:
            seconds: Duration in seconds
            
        Returns:
            Formatted duration string
        """
        if seconds < 3600:  # Less than 1 hour
            minutes, secs = divmod(seconds, 60)
            return f"{minutes:02d}:{secs:02d}"
        else:  # 1 hour or more
            hours, remainder = divmod(seconds, 3600)
            minutes, secs = divmod(remainder, 60)
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    async def get_queue_summary(self) -> str:
        """
        Get a brief queue summary.
        
        Returns:
            Summary string
        """
        async with self._lock:
            if not self._queue:
                return "Queue is empty"
            
            total_duration = sum(song.duration for song in self._queue)
            duration_str = self._format_duration(total_duration)
            
            return f"{len(self._queue)} songs in queue ({duration_str} total)"
