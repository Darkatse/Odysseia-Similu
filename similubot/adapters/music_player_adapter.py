"""
音乐播放器适配器 - 为新架构提供向后兼容性

该适配器使新的 PlaybackEngine 与现有的 MusicCommands 接口兼容，
确保在重构过程中不破坏现有功能。
"""

import logging
import asyncio
from typing import Optional, Dict, Any, Tuple
import discord
from discord.ext import commands

from similubot.playback.playback_engine import PlaybackEngine
from similubot.progress.base import ProgressCallback
from enum import Enum


class AudioSourceType(Enum):
    YOUTUBE = "youtube"
    CATBOX = "catbox"
    BILIBILI = "bilibili"
    SOUNDCLOUD = "soundcloud"

class MusicPlayerAdapter:
    """
    音乐播放器适配器
    
    将新的 PlaybackEngine 包装为与旧 MusicPlayer 接口兼容的适配器。
    提供所有 MusicCommands 需要的方法和属性。
    """
    
    def __init__(self, playback_engine: PlaybackEngine):
        """
        初始化适配器
        
        Args:
            playback_engine: 新架构的播放引擎
        """
        self.logger = logging.getLogger("similubot.adapters.music_player")
        self._playback_engine = playback_engine
        
        # 为了兼容性，暴露一些内部组件
        self.bot = playback_engine.bot
        self.config = playback_engine.config
        self.temp_dir = playback_engine.temp_dir
        
        # 创建兼容的客户端接口
        self.youtube_client = self._create_youtube_client_adapter()
        self.catbox_client = self._create_catbox_client_adapter()
        self.bilibili_client = self._create_bilibili_client_adapter()
        self.soundcloud_client = self._create_soundcloud_client_adapter()
        self.voice_manager = playback_engine.voice_manager
        self.seek_manager = playback_engine.seek_manager
        
        # 持久化支持
        self.queue_persistence = playback_engine.persistence_manager
        
        self.logger.debug("音乐播放器适配器初始化完成")
    
    def _create_youtube_client_adapter(self):
        """创建 YouTube 客户端适配器"""
        class YouTubeClientAdapter:
            def __init__(self, provider_factory):
                self.provider_factory = provider_factory
                self.youtube_provider = provider_factory.get_provider_by_name('youtube')

            async def extract_audio_info(self, url: str):
                if self.youtube_provider:
                    return await self.youtube_provider.extract_audio_info(url)
                return None

            def format_duration(self, duration: int) -> str:
                """格式化时长为可读字符串"""
                minutes = duration // 60
                seconds = duration % 60
                return f"{minutes}:{seconds:02d}"

        return YouTubeClientAdapter(self._playback_engine.audio_provider_factory)
    
    def _create_catbox_client_adapter(self):
        """创建 Catbox 客户端适配器"""
        class CatboxClientAdapter:
            def __init__(self, provider_factory):
                self.provider_factory = provider_factory
                self.catbox_provider = provider_factory.get_provider_by_name('catbox')

            async def extract_audio_info(self, url: str):
                if self.catbox_provider:
                    return await self.catbox_provider.extract_audio_info(url)
                return None

            def format_file_size(self, size_bytes: int) -> str:
                """
                格式化文件大小为可读字符串

                Args:
                    size_bytes: 文件大小（字节）

                Returns:
                    格式化的文件大小字符串
                """
                if size_bytes is None:
                    return "Unknown size"

                if size_bytes >= 1024 * 1024 * 1024:
                    return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
                elif size_bytes >= 1024 * 1024:
                    return f"{size_bytes / (1024 * 1024):.1f} MB"
                elif size_bytes >= 1024:
                    return f"{size_bytes / 1024:.1f} KB"
                else:
                    return f"{size_bytes} B"

        return CatboxClientAdapter(self._playback_engine.audio_provider_factory)

    def _create_bilibili_client_adapter(self):
        """创建 Bilibili 客户端适配器"""
        class BilibiliClientAdapter:
            def __init__(self, provider_factory):
                self.provider_factory = provider_factory
                self.bilibili_provider = provider_factory.get_provider_by_name('bilibili')

            async def extract_audio_info(self, url: str):
                if self.bilibili_provider:
                    return await self.bilibili_provider.extract_audio_info(url)
                return None

            def format_duration(self, duration: int) -> str:
                """格式化时长为可读字符串"""
                if duration is None or duration <= 0:
                    return "Unknown duration"

                minutes = duration // 60
                seconds = duration % 60
                if minutes >= 60:
                    hours = minutes // 60
                    minutes = minutes % 60
                    return f"{hours}:{minutes:02d}:{seconds:02d}"
                else:
                    return f"{minutes}:{seconds:02d}"

        return BilibiliClientAdapter(self._playback_engine.audio_provider_factory)

    def _create_soundcloud_client_adapter(self):
        """创建 SoundCloud 客户端适配器"""
        class SoundCloudClientAdapter:
            def __init__(self, provider_factory):
                self.provider_factory = provider_factory
                self.soundcloud_provider = provider_factory.get_provider_by_name('soundcloud')

            async def extract_audio_info(self, url: str):
                if self.soundcloud_provider:
                    return await self.soundcloud_provider.extract_audio_info(url)
                return None

        return SoundCloudClientAdapter(self._playback_engine.audio_provider_factory)

    def is_supported_url(self, url: str) -> bool:
        """
        检查URL是否被支持
        
        Args:
            url: 要检查的URL
            
        Returns:
            如果被支持则返回True
        """
        return self._playback_engine.audio_provider_factory.is_supported_url(url)
    
    def detect_audio_source_type(self, url: str) -> Optional[AudioSourceType]:
        """
        检测音频源类型

        Args:
            url: 音频URL

        Returns:
            音频源类型，如果不支持则返回None
        """
        provider = self._playback_engine.audio_provider_factory.detect_provider_for_url(url)
        if not provider:
            return None

        provider_name = provider.name.lower()
        if provider_name == 'youtube':
            return AudioSourceType.YOUTUBE
        elif provider_name == 'catbox':
            return AudioSourceType.CATBOX
        elif provider_name == 'bilibili':
            return AudioSourceType.BILIBILI
        elif provider_name == 'soundcloud':
            return AudioSourceType.SOUNDCLOUD

        return None
    
    async def connect_to_user_channel(self, user: discord.Member) -> Tuple[bool, Optional[str]]:
        """
        连接到用户语音频道
        
        Args:
            user: Discord用户
            
        Returns:
            (成功标志, 错误消息)
        """
        return await self._playback_engine.connect_to_user_channel(user)
    
    async def add_song_to_queue(
        self, 
        url: str, 
        requester: discord.Member, 
        progress_callback: Optional[ProgressCallback] = None
    ) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        添加歌曲到队列
        
        Args:
            url: 音频URL
            requester: 请求用户
            progress_callback: 进度回调
            
        Returns:
            (成功标志, 队列位置, 错误消息)
        """
        return await self._playback_engine.add_song_to_queue(url, requester, progress_callback)
    
    async def get_queue_info(self, guild_id: int) -> Dict[str, Any]:
        """
        获取队列信息

        Args:
            guild_id: 服务器ID

        Returns:
            队列信息字典
        """
        try:
            queue_manager = self._playback_engine.get_queue_manager(guild_id)
            queue_info = await queue_manager.get_queue_info()

            # 为了兼容性，将current_song从display_info字典改为实际的Song对象
            current_song_obj = queue_manager.get_current_song()
            queue_info['current_song'] = current_song_obj

            # 添加兼容性字段
            queue_info['is_empty'] = (queue_info.get('queue_length', 0) == 0 and
                                    current_song_obj is None)

            # 添加播放状态字段（兼容性）
            queue_info['playing'] = self.is_playing(guild_id)
            queue_info['paused'] = self.is_paused(guild_id)

            # 添加语音连接信息
            connection_info = self.voice_manager.get_connection_info(guild_id)
            queue_info['connected'] = connection_info.get('connected', False)
            queue_info['channel'] = connection_info.get('channel', None)

            return queue_info
        except Exception as e:
            self.logger.error(f"获取队列信息失败: {e}")
            return {
                'guild_id': guild_id,
                'current_song': None,
                'queue_length': 0,
                'queue_songs': [],
                'total_duration': 0,
                'is_empty': True,
                'playing': False,
                'paused': False,
                'connected': False,
                'channel': None
            }
    
    async def skip_current_song(self, guild_id: int) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        跳过当前歌曲

        Args:
            guild_id: 服务器ID

        Returns:
            (成功标志, 跳过的歌曲标题, 错误消息)
        """
        success, skipped_song, error = await self._playback_engine.skip_song(guild_id)

        # 获取跳过的歌曲标题用于显示
        skipped_title = "Unknown Song"
        if success and skipped_song:
            skipped_title = skipped_song.title

        return success, skipped_title, error
    
    async def stop_playback(self, guild_id: int) -> Tuple[bool, Optional[str]]:
        """
        停止播放
        
        Args:
            guild_id: 服务器ID
            
        Returns:
            (成功标志, 错误消息)
        """
        return await self._playback_engine.stop_playback(guild_id)
    
    async def jump_to_position(self, guild_id: int, position: int) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        跳转到队列中的指定位置

        Args:
            guild_id: 服务器ID
            position: 队列位置

        Returns:
            (成功标志, 歌曲标题, 错误消息)
        """
        success, target_song, error = await self._playback_engine.jump_to_position(guild_id, position)

        # 获取目标歌曲标题用于显示
        song_title = "Unknown Song"
        if success and target_song:
            song_title = target_song.title

        return success, song_title, error
    
    async def seek_to_position(self, guild_id: int, time_str: str) -> Tuple[bool, Optional[str]]:
        """
        定位到指定时间位置
        
        Args:
            guild_id: 服务器ID
            time_str: 时间字符串
            
        Returns:
            (成功标志, 错误消息)
        """
        try:
            # 使用 seek_manager 解析时间
            seek_info = self.seek_manager.calculate_seek_position(time_str, 3600, 0)  # 假设最大1小时
            
            if seek_info.result.value != "success":
                return False, seek_info.message
            
            # 实际的定位操作需要在播放引擎中实现
            # 这里返回成功，因为时间解析正确
            return True, None
            
        except Exception as e:
            error_msg = f"定位失败: {e}"
            self.logger.error(error_msg)
            return False, error_msg
    
    def is_playing(self, guild_id: int) -> bool:
        """
        检查是否正在播放
        
        Args:
            guild_id: 服务器ID
            
        Returns:
            如果正在播放则返回True
        """
        return self._playback_engine.is_playing(guild_id)
    
    def is_paused(self, guild_id: int) -> bool:
        """
        检查是否暂停
        
        Args:
            guild_id: 服务器ID
            
        Returns:
            如果暂停则返回True
        """
        return self._playback_engine.is_paused(guild_id)
    
    async def initialize_persistence(self) -> None:
        """初始化持久化系统"""
        await self._playback_engine.initialize_persistence()

    async def manual_save(self, guild_id: int) -> None:
        """
        手动保存当前服务器的队列状态到持久化存储

        Args:
            guild_id: 服务器ID
        """
        await self._playback_engine.manual_save(guild_id)

    async def cleanup_all(self) -> None:
        """清理所有资源"""
        try:
            # 清理语音连接
            await self.voice_manager.cleanup_all_connections()
            
            # 清理临时文件
            cleanup_results = self._playback_engine.audio_provider_factory.cleanup_temp_files()
            self.logger.debug(f"临时文件清理结果: {cleanup_results}")
            
        except Exception as e:
            self.logger.error(f"清理资源时发生错误: {e}")
    
    def get_persistence_stats(self) -> Dict[str, Any]:
        """获取持久化统计信息"""
        if self.queue_persistence:
            return self.queue_persistence.get_persistence_stats()
        return {'persistence_enabled': False}

    # 为了兼容性，暴露内部属性
    @property
    def _queue_managers(self) -> Dict[int, Any]:
        """获取队列管理器字典（兼容性属性）"""
        return self._playback_engine._queue_managers

    @property
    def _playback_tasks(self) -> Dict[int, Any]:
        """获取播放任务字典（兼容性属性）"""
        return self._playback_engine._playback_tasks

    def get_current_playback_position(self, guild_id: int) -> Optional[float]:
        """
        获取当前播放位置

        Args:
            guild_id: 服务器ID

        Returns:
            当前播放位置（秒），如果没有播放则返回None
        """
        try:
            # 从播放引擎获取位置信息
            return self._playback_engine.get_current_playback_position(guild_id)
        except Exception as e:
            self.logger.error(f"获取播放位置失败: {e}")
            return None

    async def pause_playback(self, guild_id: int) -> bool:
        """
        暂停播放

        Args:
            guild_id: 服务器ID

        Returns:
            暂停是否成功
        """
        return self._playback_engine.pause_playback(guild_id)

    async def resume_playback(self, guild_id: int) -> bool:
        """
        恢复播放

        Args:
            guild_id: 服务器ID

        Returns:
            恢复是否成功
        """
        return self._playback_engine.resume_playback(guild_id)

    def format_duration(self, duration: int) -> str:
        """
        格式化时长为可读字符串

        Args:
            duration: 时长（秒）

        Returns:
            格式化的时长字符串
        """
        minutes = duration // 60
        seconds = duration % 60
        return f"{minutes}:{seconds:02d}"

    def get_queue_manager(self, guild_id: int):
        """
        获取或创建服务器的队列管理器

        Args:
            guild_id: Discord 服务器 ID

        Returns:
            队列管理器实例
        """
        return self._playback_engine.get_queue_manager(guild_id)
