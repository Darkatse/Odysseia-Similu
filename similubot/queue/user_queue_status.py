"""
用户队列状态服务 - 提供用户队列状态查询功能

这个模块提供了一个专门的服务类来处理用户队列状态查询，
包括获取用户当前歌曲信息、队列位置和预计播放时间的计算逻辑。
遵循单一职责原则和DRY原则，被队列公平性拒绝消息和!music my命令共同使用。
"""

from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
import discord
import logging

from similubot.core.interfaces import SongInfo, IQueueManager
from similubot.playback.playback_engine import PlaybackEngine


@dataclass
class UserQueueInfo:
    """
    用户队列信息数据类
    
    包含用户在队列中的详细状态信息，用于统一的数据传递。
    """
    user_id: int
    user_name: str
    has_queued_song: bool
    queued_song_title: Optional[str] = None
    queue_position: Optional[int] = None  # 在队列中的位置（从1开始）
    estimated_play_time_seconds: Optional[int] = None  # 预计播放时间（秒）
    is_currently_playing: bool = False
    
    def format_estimated_time(self) -> str:
        """
        格式化预计播放时间为可读字符串
        
        Returns:
            格式化的时间字符串 (例: "3分45秒" 或 "1小时23分")
        """
        if self.estimated_play_time_seconds is None:
            return "未知"
        
        seconds = self.estimated_play_time_seconds
        if seconds < 60:
            return f"{seconds}秒"
        elif seconds < 3600:
            minutes = seconds // 60
            remaining_seconds = seconds % 60
            if remaining_seconds == 0:
                return f"{minutes}分钟"
            else:
                return f"{minutes}分{remaining_seconds}秒"
        else:
            hours = seconds // 3600
            remaining_minutes = (seconds % 3600) // 60
            if remaining_minutes == 0:
                return f"{hours}小时"
            else:
                return f"{hours}小时{remaining_minutes}分钟"


class UserQueueStatusService:
    """
    用户队列状态服务
    
    提供用户队列状态查询功能，包括：
    1. 获取用户当前排队的歌曲信息
    2. 计算歌曲在队列中的位置
    3. 估算歌曲的预计播放时间
    4. 处理各种边界情况
    
    遵循单一职责原则，专注于用户队列状态的查询和计算。
    """
    
    def __init__(self, playback_engine: PlaybackEngine):
        """
        初始化用户队列状态服务
        
        Args:
            playback_engine: 播放引擎实例，用于获取队列和播放状态信息
        """
        self.playback_engine = playback_engine
        self.logger = logging.getLogger("similubot.queue.user_queue_status")
    
    def get_user_queue_info(self, user: discord.Member, guild_id: int) -> UserQueueInfo:
        """
        获取用户的详细队列状态信息
        
        Args:
            user: Discord用户
            guild_id: 服务器ID
            
        Returns:
            用户队列信息对象
        """
        self.logger.debug(f"获取用户队列状态 - 用户: {user.display_name} ({user.id}), 服务器: {guild_id}")
        
        try:
            # 获取队列管理器
            queue_manager = self.playback_engine.get_queue_manager(guild_id)
            
            # 检查用户是否有正在播放的歌曲
            current_song = queue_manager.get_current_song()
            is_currently_playing = current_song and current_song.requester.id == user.id
            
            if is_currently_playing:
                self.logger.debug(f"用户 {user.display_name} 的歌曲正在播放: {current_song.title}")
                return UserQueueInfo(
                    user_id=user.id,
                    user_name=user.display_name,
                    has_queued_song=True,
                    queued_song_title=current_song.title,
                    queue_position=0,  # 正在播放，位置为0
                    estimated_play_time_seconds=0,  # 正在播放，无需等待
                    is_currently_playing=True
                )
            
            # 查找用户在队列中的歌曲
            user_song_info = self._find_user_song_in_queue(user, queue_manager)
            
            if not user_song_info:
                self.logger.debug(f"用户 {user.display_name} 在队列中没有歌曲")
                return UserQueueInfo(
                    user_id=user.id,
                    user_name=user.display_name,
                    has_queued_song=False
                )
            
            song, position = user_song_info
            
            # 计算预计播放时间
            estimated_time = self._calculate_estimated_play_time(position, queue_manager, guild_id)
            
            self.logger.debug(
                f"用户 {user.display_name} 队列状态: 歌曲='{song.title}', "
                f"位置={position}, 预计时间={estimated_time}秒"
            )
            
            return UserQueueInfo(
                user_id=user.id,
                user_name=user.display_name,
                has_queued_song=True,
                queued_song_title=song.title,
                queue_position=position,
                estimated_play_time_seconds=estimated_time,
                is_currently_playing=False
            )
            
        except Exception as e:
            self.logger.error(f"获取用户队列状态时出错: {e}", exc_info=True)
            # 返回默认状态，避免崩溃
            return UserQueueInfo(
                user_id=user.id,
                user_name=user.display_name,
                has_queued_song=False
            )
    
    def _find_user_song_in_queue(self, user: discord.Member, queue_manager: IQueueManager) -> Optional[Tuple[SongInfo, int]]:
        """
        在队列中查找用户的歌曲
        
        Args:
            user: Discord用户
            queue_manager: 队列管理器
            
        Returns:
            (歌曲信息, 队列位置) 的元组，如果未找到则返回None
            队列位置从1开始计数
        """
        try:
            # 获取队列中的所有歌曲
            queue_songs = queue_manager.get_queue_songs(start=0, limit=1000)  # 获取足够多的歌曲
            
            for position, song in enumerate(queue_songs, 1):
                if song.requester.id == user.id:
                    self.logger.debug(f"找到用户 {user.display_name} 的歌曲: {song.title} (位置 {position})")
                    return song, position
            
            return None
            
        except Exception as e:
            self.logger.error(f"查找用户歌曲时出错: {e}", exc_info=True)
            return None
    
    def _calculate_estimated_play_time(self, queue_position: int, queue_manager: IQueueManager, guild_id: int) -> int:
        """
        计算歌曲的预计播放时间
        
        Args:
            queue_position: 歌曲在队列中的位置（从1开始）
            queue_manager: 队列管理器
            guild_id: 服务器ID
            
        Returns:
            预计播放时间（秒）
        """
        try:
            total_wait_time = 0
            
            # 1. 计算当前播放歌曲的剩余时间
            current_song = queue_manager.get_current_song()
            if current_song:
                current_position = self.playback_engine.get_current_playback_position(guild_id)
                if current_position is not None:
                    remaining_time = max(0, current_song.duration - current_position)
                    total_wait_time += remaining_time
                    self.logger.debug(f"当前歌曲剩余时间: {remaining_time}秒")
                else:
                    # 如果无法获取当前位置，假设整首歌都需要播放
                    total_wait_time += current_song.duration
                    self.logger.debug(f"无法获取当前位置，使用完整歌曲时长: {current_song.duration}秒")
            
            # 2. 计算队列中目标歌曲之前所有歌曲的总时长
            if queue_position > 1:
                queue_songs = queue_manager.get_queue_songs(start=0, limit=queue_position - 1)
                for song in queue_songs:
                    total_wait_time += song.duration
                    self.logger.debug(f"队列歌曲时长: {song.title} - {song.duration}秒")
            
            self.logger.debug(f"总预计等待时间: {total_wait_time}秒")
            return int(total_wait_time)
            
        except Exception as e:
            self.logger.error(f"计算预计播放时间时出错: {e}", exc_info=True)
            return 0  # 返回0作为默认值
    
    def format_queue_status_message(self, user_info: UserQueueInfo) -> str:
        """
        格式化用户队列状态消息
        
        Args:
            user_info: 用户队列信息
            
        Returns:
            格式化的状态消息字符串
        """
        if not user_info.has_queued_song:
            return f"{user_info.user_name}，您当前没有歌曲在队列中。"
        
        if user_info.is_currently_playing:
            return f"{user_info.user_name}，您的歌曲 **{user_info.queued_song_title}** 正在播放中！"
        
        position_text = f"第{user_info.queue_position}位" if user_info.queue_position else "未知位置"
        time_text = user_info.format_estimated_time()
        
        return (
            f"{user_info.user_name}，您的歌曲 **{user_info.queued_song_title}** "
            f"目前排在队列{position_text}，预计 {time_text} 后开始播放。"
        )
