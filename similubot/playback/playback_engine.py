"""
播放引擎 - 音乐播放的核心控制器

协调音频提供者、队列管理器和语音管理器，提供统一的播放控制接口。
负责播放流程的编排和状态管理。
"""

import logging
import asyncio
import os
import time
from typing import Optional, Dict, Any, Tuple
import discord
from discord.ext import commands

from similubot.core.interfaces import IPlaybackEngine, IQueueManager, IVoiceManager, IAudioProvider, SongInfo
from similubot.progress.base import ProgressCallback
from similubot.provider import AudioProviderFactory
from similubot.queue import QueueManager, PersistenceManager
from .voice_manager import VoiceManager
from .seek_manager import SeekManager


class PlaybackEngine(IPlaybackEngine):
    """
    播放引擎实现
    
    协调各个模块，提供完整的音乐播放功能。
    管理播放状态、队列操作和用户交互。
    """
    
    def __init__(
        self, 
        bot: commands.Bot, 
        temp_dir: str = "./temp", 
        config=None
    ):
        """
        初始化播放引擎
        
        Args:
            bot: Discord机器人实例
            temp_dir: 临时文件目录
            config: 配置管理器
        """
        self.bot = bot
        self.temp_dir = temp_dir
        self.config = config
        self.logger = logging.getLogger("similubot.playback.engine")
        
        # 初始化组件
        self.audio_provider_factory = AudioProviderFactory(temp_dir, config)
        self.voice_manager = VoiceManager(bot)
        self.seek_manager = SeekManager()
        
        # 初始化持久化管理器
        self.persistence_manager = PersistenceManager() if config else None
        
        # 服务器特定的队列管理器
        self._queue_managers: Dict[int, IQueueManager] = {}
        
        # 播放状态跟踪
        self._playback_tasks: Dict[int, asyncio.Task] = {}
        self._current_audio_files: Dict[int, str] = {}
        
        # 播放时间跟踪
        self._playback_start_times: Dict[int, float] = {}
        self._playback_paused_times: Dict[int, float] = {}
        self._total_paused_duration: Dict[int, float] = {}
        
        self.logger.info("🎵 播放引擎初始化完成")
    
    def get_queue_manager(self, guild_id: int) -> IQueueManager:
        """
        获取或创建服务器的队列管理器
        
        Args:
            guild_id: Discord服务器ID
            
        Returns:
            队列管理器实例
        """
        if guild_id not in self._queue_managers:
            queue_manager = QueueManager(guild_id, self.persistence_manager)
            self._queue_managers[guild_id] = queue_manager
            self.logger.debug(f"为服务器 {guild_id} 创建队列管理器")
        
        return self._queue_managers[guild_id]
    
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
        try:
            guild_id = requester.guild.id
            
            # 检查URL是否支持
            if not self.audio_provider_factory.is_supported_url(url):
                return False, None, "不支持的URL格式"
            
            # 提取音频信息
            audio_info = await self.audio_provider_factory.extract_audio_info(url)
            if not audio_info:
                return False, None, "无法获取音频信息"
            
            # 添加到队列
            queue_manager = self.get_queue_manager(guild_id)
            position = await queue_manager.add_song(audio_info, requester)
            
            self.logger.info(f"歌曲添加到队列 - 服务器 {guild_id}: {audio_info.title} (位置 {position})")
            
            # 如果没有正在播放，开始播放
            if not self.is_playing(guild_id):
                await self._start_playback_if_needed(guild_id)
            
            return True, position, None
            
        except Exception as e:
            error_msg = f"添加歌曲到队列失败: {e}"
            self.logger.error(error_msg)
            return False, None, error_msg
    
    async def skip_song(self, guild_id: int) -> Tuple[bool, Optional[SongInfo], Optional[str]]:
        """
        跳过当前歌曲
        
        Args:
            guild_id: 服务器ID
            
        Returns:
            (成功标志, 下一首歌曲, 错误消息)
        """
        try:
            queue_manager = self.get_queue_manager(guild_id)
            
            # 停止当前播放
            self.voice_manager.stop_audio(guild_id)
            
            # 获取下一首歌曲
            next_song = await queue_manager.skip_current_song()
            
            if next_song:
                self.logger.info(f"跳过歌曲 - 服务器 {guild_id}: 下一首 {next_song.title}")
            else:
                self.logger.info(f"跳过歌曲 - 服务器 {guild_id}: 队列为空")
            
            return True, next_song, None
            
        except Exception as e:
            error_msg = f"跳过歌曲失败: {e}"
            self.logger.error(error_msg)
            return False, None, error_msg
    
    async def stop_playback(self, guild_id: int) -> Tuple[bool, Optional[str]]:
        """
        停止播放并清空队列

        Args:
            guild_id: 服务器ID

        Returns:
            (成功标志, 错误消息)
        """
        try:
            # 停止播放
            self.voice_manager.stop_audio(guild_id)

            # 清理播放时间跟踪
            self._cleanup_playback_tracking(guild_id)

            # 清空队列
            queue_manager = self.get_queue_manager(guild_id)
            cleared_count = await queue_manager.clear_queue()

            # 清理播放任务
            if guild_id in self._playback_tasks:
                self._playback_tasks[guild_id].cancel()
                del self._playback_tasks[guild_id]

            # 清理音频文件
            await self._cleanup_current_audio(guild_id)

            self.logger.info(f"停止播放 - 服务器 {guild_id}: 清空了 {cleared_count} 首歌曲")
            return True, None

        except Exception as e:
            error_msg = f"停止播放失败: {e}"
            self.logger.error(error_msg)
            return False, error_msg
    
    async def connect_to_user_channel(self, user: discord.Member) -> Tuple[bool, Optional[str]]:
        """
        连接到用户语音频道
        
        Args:
            user: Discord用户
            
        Returns:
            (成功标志, 错误消息)
        """
        return await self.voice_manager.connect_to_user_channel(user)
    
    def get_queue_info(self, guild_id: int) -> Dict[str, Any]:
        """
        获取队列信息
        
        Args:
            guild_id: 服务器ID
            
        Returns:
            队列信息字典
        """
        try:
            queue_manager = self.get_queue_manager(guild_id)
            # 由于接口限制，这里使用同步方法
            # 在实际使用中可能需要异步版本
            return asyncio.create_task(queue_manager.get_queue_info()).result()
        except:
            return {
                'guild_id': guild_id,
                'current_song': None,
                'queue_length': 0,
                'queue_songs': [],
                'total_duration': 0
            }
    
    def is_playing(self, guild_id: int) -> bool:
        """
        检查是否正在播放
        
        Args:
            guild_id: 服务器ID
            
        Returns:
            如果正在播放则返回True
        """
        return self.voice_manager.is_playing(guild_id)
    
    def is_paused(self, guild_id: int) -> bool:
        """
        检查是否暂停

        Args:
            guild_id: 服务器ID

        Returns:
            如果暂停则返回True
        """
        return self.voice_manager.is_paused(guild_id)

    def get_current_playback_position(self, guild_id: int) -> Optional[float]:
        """
        获取当前播放位置

        Args:
            guild_id: 服务器ID

        Returns:
            当前播放位置（秒），如果没有播放则返回None
        """
        if guild_id not in self._playback_start_times:
            return None

        start_time = self._playback_start_times[guild_id]
        current_time = time.time()

        # 计算已播放时间
        elapsed = current_time - start_time

        # 减去暂停时间
        total_paused = self._total_paused_duration.get(guild_id, 0.0)

        # 如果当前暂停，添加当前暂停时长
        if guild_id in self._playback_paused_times:
            current_pause_duration = current_time - self._playback_paused_times[guild_id]
            total_paused += current_pause_duration

        return max(0.0, elapsed - total_paused)

    def pause_playback(self, guild_id: int) -> bool:
        """
        暂停播放并记录暂停时间

        Args:
            guild_id: 服务器ID

        Returns:
            暂停是否成功
        """
        success = self.voice_manager.pause_audio(guild_id)
        if success and guild_id in self._playback_start_times:
            # 记录暂停开始时间
            self._playback_paused_times[guild_id] = time.time()
            self.logger.debug(f"记录暂停时间 - 服务器 {guild_id}")
        return success

    def resume_playback(self, guild_id: int) -> bool:
        """
        恢复播放并更新暂停时长

        Args:
            guild_id: 服务器ID

        Returns:
            恢复是否成功
        """
        success = self.voice_manager.resume_audio(guild_id)
        if success and guild_id in self._playback_paused_times:
            # 计算暂停时长并累加
            pause_start = self._playback_paused_times[guild_id]
            pause_duration = time.time() - pause_start

            if guild_id not in self._total_paused_duration:
                self._total_paused_duration[guild_id] = 0.0
            self._total_paused_duration[guild_id] += pause_duration

            # 清除暂停开始时间
            del self._playback_paused_times[guild_id]

            self.logger.debug(f"恢复播放，累计暂停时长: {self._total_paused_duration[guild_id]:.1f}秒 - 服务器 {guild_id}")
        return success
    
    async def _start_playback_if_needed(self, guild_id: int) -> None:
        """如果需要，开始播放下一首歌曲"""
        if guild_id in self._playback_tasks:
            return  # 已经有播放任务在运行
        
        # 创建播放任务
        task = asyncio.create_task(self._playback_loop(guild_id))
        self._playback_tasks[guild_id] = task
    
    async def _playback_loop(self, guild_id: int) -> None:
        """播放循环"""
        try:
            queue_manager = self.get_queue_manager(guild_id)
            
            while True:
                # 获取下一首歌曲
                song = await queue_manager.get_next_song()
                if not song:
                    break  # 队列为空
                
                # 下载音频文件
                success, audio_info, error = await self.audio_provider_factory.download_audio(song.url)
                if not success or not audio_info:
                    self.logger.error(f"下载音频失败 - {song.title}: {error}")
                    continue
                
                # 播放音频
                if audio_info.file_path and os.path.exists(audio_info.file_path):
                    await self._play_audio_file(guild_id, audio_info.file_path, song)
                else:
                    # 直接播放URL（如Catbox）
                    await self._play_audio_url(guild_id, song.url, song)
                
        except Exception as e:
            self.logger.error(f"播放循环出错 - 服务器 {guild_id}: {e}")
        finally:
            # 清理播放任务
            if guild_id in self._playback_tasks:
                del self._playback_tasks[guild_id]
    
    async def _play_audio_file(self, guild_id: int, file_path: str, song: SongInfo) -> None:
        """播放音频文件"""
        try:
            # 创建音频源
            audio_source = discord.FFmpegPCMAudio(file_path)

            # 播放完成事件
            playback_finished = asyncio.Event()

            def after_playing(error):
                if error:
                    self.logger.error(f"播放出错: {error}")
                # 清理播放时间跟踪
                self._cleanup_playback_tracking(guild_id)
                playback_finished.set()

            # 开始播放
            success = await self.voice_manager.play_audio(guild_id, audio_source, after_playing)
            if not success:
                return

            # 记录播放开始时间
            self._playback_start_times[guild_id] = time.time()
            self._total_paused_duration[guild_id] = 0.0
            if guild_id in self._playback_paused_times:
                del self._playback_paused_times[guild_id]

            self.logger.info(f"正在播放: {song.title}")

            # 等待播放完成
            await playback_finished.wait()

            # 清理音频文件
            self._current_audio_files[guild_id] = file_path

        except Exception as e:
            self.logger.error(f"播放音频文件失败: {e}")
            self._cleanup_playback_tracking(guild_id)
    
    async def _play_audio_url(self, guild_id: int, url: str, song: SongInfo) -> None:
        """播放音频URL"""
        try:
            # 创建音频源
            audio_source = discord.FFmpegPCMAudio(url)

            # 播放完成事件
            playback_finished = asyncio.Event()

            def after_playing(error):
                if error:
                    self.logger.error(f"播放出错: {error}")
                # 清理播放时间跟踪
                self._cleanup_playback_tracking(guild_id)
                playback_finished.set()

            # 开始播放
            success = await self.voice_manager.play_audio(guild_id, audio_source, after_playing)
            if not success:
                return

            # 记录播放开始时间
            self._playback_start_times[guild_id] = time.time()
            self._total_paused_duration[guild_id] = 0.0
            if guild_id in self._playback_paused_times:
                del self._playback_paused_times[guild_id]

            self.logger.info(f"正在播放: {song.title}")

            # 等待播放完成
            await playback_finished.wait()

        except Exception as e:
            self.logger.error(f"播放音频URL失败: {e}")
            self._cleanup_playback_tracking(guild_id)
    
    def _cleanup_playback_tracking(self, guild_id: int) -> None:
        """清理播放时间跟踪"""
        if guild_id in self._playback_start_times:
            del self._playback_start_times[guild_id]
        if guild_id in self._playback_paused_times:
            del self._playback_paused_times[guild_id]
        if guild_id in self._total_paused_duration:
            del self._total_paused_duration[guild_id]

    async def _cleanup_current_audio(self, guild_id: int) -> None:
        """清理当前音频文件"""
        if guild_id in self._current_audio_files:
            file_path = self._current_audio_files[guild_id]
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    self.logger.debug(f"清理音频文件: {file_path}")
            except Exception as e:
                self.logger.warning(f"清理音频文件失败: {e}")
            finally:
                del self._current_audio_files[guild_id]
    
    async def initialize_persistence(self) -> None:
        """初始化持久化系统并恢复所有队列状态"""
        if not self.persistence_manager:
            self.logger.info("队列持久化未启用")
            return

        try:
            self.logger.info("🔄 开始恢复队列状态...")
            
            # 获取所有有保存状态的服务器
            guild_ids = await self.persistence_manager.get_all_guild_ids()
            if not guild_ids:
                self.logger.info("没有找到需要恢复的队列状态")
                return

            restored_count = 0
            for guild_id in guild_ids:
                try:
                    guild = self.bot.get_guild(guild_id)
                    if not guild:
                        self.logger.warning(f"无法找到服务器 {guild_id}，跳过恢复")
                        continue

                    # 获取队列管理器并恢复状态
                    queue_manager = self.get_queue_manager(guild_id)
                    success = await queue_manager.restore_from_persistence(guild)
                    
                    if success:
                        restored_count += 1
                        self.logger.info(f"✅ 服务器 {guild_id} 队列状态恢复成功")

                except Exception as e:
                    self.logger.error(f"恢复服务器 {guild_id} 队列状态时出错: {e}")

            self.logger.info(f"队列恢复完成: {restored_count}/{len(guild_ids)} 个服务器成功恢复")

        except Exception as e:
            self.logger.error(f"初始化持久化系统时出错: {e}")
