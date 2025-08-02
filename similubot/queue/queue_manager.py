"""
队列管理器 - 管理音乐队列的核心逻辑

负责队列的所有操作，包括添加、移除、跳过歌曲等。
支持线程安全操作和队列状态持久化。
"""

import logging
import asyncio
from typing import List, Optional, Dict, Any
import discord

from similubot.core.interfaces import IQueueManager, IPersistenceManager, AudioInfo, SongInfo
from .song import Song


class QueueManager(IQueueManager):
    """
    队列管理器实现
    
    提供线程安全的队列操作，支持持久化和状态跟踪。
    遵循单一职责原则，专注于队列管理逻辑。
    """
    
    def __init__(self, guild_id: int, persistence_manager: Optional[IPersistenceManager] = None):
        """
        初始化队列管理器
        
        Args:
            guild_id: Discord服务器ID
            persistence_manager: 持久化管理器（可选）
        """
        self.guild_id = guild_id
        self.logger = logging.getLogger(f"similubot.queue.manager.{guild_id}")
        
        # 队列状态
        self._queue: List[Song] = []
        self._current_song: Optional[Song] = None
        self._current_position = 0.0  # 当前播放位置（秒）
        
        # 线程安全锁
        self._lock = asyncio.Lock()
        
        # 持久化管理器
        self._persistence_manager = persistence_manager
        
        self.logger.debug(f"队列管理器初始化完成 - 服务器 {guild_id}")
    
    def set_persistence_manager(self, persistence_manager: IPersistenceManager) -> None:
        """
        设置持久化管理器
        
        Args:
            persistence_manager: 持久化管理器
        """
        self._persistence_manager = persistence_manager
        self.logger.debug("持久化管理器已设置")
    
    async def _save_state(self) -> None:
        """保存当前队列状态到持久化存储"""
        if self._persistence_manager:
            try:
                await self._persistence_manager.save_queue_state(
                    guild_id=self.guild_id,
                    current_song=self._current_song,
                    queue=self._queue.copy(),
                    current_position=self._current_position
                )
            except Exception as e:
                self.logger.error(f"保存队列状态失败: {e}")
    
    async def add_song(self, audio_info: AudioInfo, requester: discord.Member) -> int:
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
    
    async def get_next_song(self) -> Optional[SongInfo]:
        """
        从队列获取下一首歌曲
        
        Returns:
            下一首歌曲，如果队列为空则返回None
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
    
    async def skip_current_song(self) -> Optional[SongInfo]:
        """
        跳过当前歌曲并获取下一首
        
        Returns:
            下一首歌曲，如果队列为空则返回None
        """
        async with self._lock:
            if self._current_song:
                self.logger.info(f"跳过当前歌曲: {self._current_song.title}")
                self._current_song = None
                self._current_position = 0.0
            
            # get_next_song 会自动保存状态
            return await self.get_next_song()
    
    async def jump_to_position(self, position: int) -> Optional[SongInfo]:
        """
        跳转到队列中的指定位置
        
        Args:
            position: 队列位置（从1开始）
            
        Returns:
            指定位置的歌曲，如果位置无效则返回None
        """
        async with self._lock:
            if position < 1 or position > len(self._queue):
                return None
            
            # 移除目标位置之前的歌曲
            songs_to_remove = position - 1
            for _ in range(songs_to_remove):
                if self._queue:
                    removed_song = self._queue.pop(0)
                    self.logger.debug(f"跳转时移除歌曲: {removed_song.title}")
            
            # 获取目标歌曲
            if self._queue:
                song = self._queue.pop(0)
                self._current_song = song
                self._current_position = 0.0  # 重置播放位置
                
                self.logger.info(f"跳转到位置 {position}: {song.title}")
                
                # 保存状态
                await self._save_state()
                
                return song
            
            return None
    
    async def remove_song_at_position(self, position: int) -> Optional[SongInfo]:
        """
        移除指定位置的歌曲
        
        Args:
            position: 队列位置（从1开始）
            
        Returns:
            被移除的歌曲，如果位置无效则返回None
        """
        async with self._lock:
            if position < 1 or position > len(self._queue):
                return None
            
            removed_song = self._queue.pop(position - 1)
            self.logger.info(f"移除位置 {position} 的歌曲: {removed_song.title}")
            
            # 保存状态
            await self._save_state()
            
            return removed_song
    
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
    
    def get_current_song(self) -> Optional[SongInfo]:
        """
        获取当前播放的歌曲
        
        Returns:
            当前歌曲，如果没有则返回None
        """
        return self._current_song
    
    def update_position(self, position: float) -> None:
        """
        更新当前播放位置
        
        Args:
            position: 播放位置（秒）
        """
        self._current_position = position
    
    def get_queue_length(self) -> int:
        """
        获取队列长度
        
        Returns:
            队列中的歌曲数量
        """
        return len(self._queue)
    
    def get_queue_songs(self, start: int = 0, limit: int = 10) -> List[SongInfo]:
        """
        获取队列中的歌曲列表

        Args:
            start: 起始位置
            limit: 最大数量

        Returns:
            歌曲列表
        """
        end = min(start + limit, len(self._queue))
        return self._queue[start:end]

    async def get_queue_display(self, max_songs: int = 10) -> List[Dict[str, Any]]:
        """
        获取格式化的队列显示信息

        Args:
            max_songs: 最大显示歌曲数量

        Returns:
            格式化的歌曲显示信息列表
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
        将秒数格式化为 MM:SS 或 HH:MM:SS 格式

        Args:
            seconds: 时长（秒）

        Returns:
            格式化的时长字符串
        """
        if seconds < 3600:  # 少于1小时
            minutes, secs = divmod(seconds, 60)
            return f"{minutes:02d}:{secs:02d}"
        else:  # 1小时或更多
            hours, remainder = divmod(seconds, 3600)
            minutes, secs = divmod(remainder, 60)
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    async def get_queue_info(self) -> Dict[str, Any]:
        """
        获取队列信息
        
        Returns:
            包含队列状态的字典
        """
        async with self._lock:
            queue_info = {
                'guild_id': self.guild_id,
                'current_song': self._current_song.get_display_info() if self._current_song else None,
                'current_position': self._current_position,
                'queue_length': len(self._queue),
                'queue_songs': [song.get_display_info() for song in self._queue[:10]],  # 只返回前10首
                'total_duration': sum(song.duration for song in self._queue),
                'has_more_songs': len(self._queue) > 10
            }
            
            return queue_info
    
    async def restore_from_persistence(self, guild: discord.Guild) -> bool:
        """
        从持久化存储恢复队列状态
        
        Args:
            guild: Discord服务器对象
            
        Returns:
            恢复是否成功
        """
        if not self._persistence_manager:
            return False

        try:
            restored_data = await self._persistence_manager.load_queue_state(self.guild_id, guild)
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
