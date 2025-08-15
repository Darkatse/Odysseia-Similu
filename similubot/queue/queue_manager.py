"""
队列管理器 - 管理音乐队列的核心逻辑

负责队列的所有操作，包括添加、移除、跳过歌曲等。
支持线程安全操作和队列状态持久化。
"""

import logging
import asyncio
from typing import List, Optional, Dict, Any, Tuple
import discord

from similubot.core.interfaces import IQueueManager, IPersistenceManager, AudioInfo, SongInfo
from .song import Song
from .duplicate_detector import DuplicateDetector


class DuplicateSongError(Exception):
    """
    重复歌曲异常

    当用户尝试添加已经在队列中的歌曲时抛出。
    """
    def __init__(self, message: str, song_title: str, user_name: str):
        super().__init__(message)
        self.song_title = song_title
        self.user_name = user_name


class QueueFairnessError(Exception):
    """
    队列公平性异常

    当用户违反队列公平性规则时抛出（例如：已有歌曲在队列中时尝试添加新歌曲）。
    包含详细的用户队列状态信息，用于生成更有用的错误消息。
    """
    def __init__(self, message: str, song_title: str, user_name: str, pending_count: int = 0,
                 queued_song_title: Optional[str] = None, queue_position: Optional[int] = None,
                 estimated_play_time_seconds: Optional[int] = None):
        super().__init__(message)
        self.song_title = song_title  # 用户尝试添加的歌曲标题
        self.user_name = user_name
        self.pending_count = pending_count
        # 新增的详细队列状态信息
        self.queued_song_title = queued_song_title  # 用户当前在队列中的歌曲标题
        self.queue_position = queue_position  # 队列位置（从1开始）
        self.estimated_play_time_seconds = estimated_play_time_seconds  # 预计播放时间（秒）


class SongTooLongError(Exception):
    """
    歌曲过长异常

    当用户尝试添加超过最大时长限制的歌曲时抛出。
    """
    def __init__(self, message: str, song_title: str, user_name: str, actual_duration: int, max_duration: int):
        super().__init__(message)
        self.song_title = song_title
        self.user_name = user_name
        self.actual_duration = actual_duration
        self.max_duration = max_duration


class QueueManager(IQueueManager):
    """
    队列管理器实现
    
    提供线程安全的队列操作，支持持久化和状态跟踪。
    遵循单一职责原则，专注于队列管理逻辑。
    """
    
    def __init__(self, guild_id: int, persistence_manager: Optional[IPersistenceManager] = None, config_manager=None):
        """
        初始化队列管理器

        Args:
            guild_id: Discord服务器ID
            persistence_manager: 持久化管理器（可选）
            config_manager: 配置管理器（可选）
        """
        self.guild_id = guild_id
        self.logger = logging.getLogger(f"similubot.queue.manager.{guild_id}")
        self._config_manager = config_manager

        # 队列状态
        self._queue: List[Song] = []
        self._current_song: Optional[Song] = None
        self._current_position = 0.0  # 当前播放位置（秒）

        # 线程安全锁
        self._lock = asyncio.Lock()

        # 持久化管理器
        self._persistence_manager = persistence_manager

        # 重复检测器
        self._duplicate_detector = DuplicateDetector(guild_id, config_manager)

        self.logger.debug(f"队列管理器初始化完成 - 服务器 {guild_id}")

    def _get_max_song_duration(self) -> int:
        """
        获取最大歌曲时长配置（秒）

        Returns:
            最大歌曲时长（秒），默认为600秒（10分钟）
        """
        if self._config_manager is None:
            return 600  # 默认10分钟

        try:
            # 配置以秒为单位
            max_duration = self._config_manager.get('music.max_song_duration', 600)

            # 验证配置值
            if not isinstance(max_duration, (int, float)) or max_duration <= 0:
                self.logger.warning(f"无效的最大歌曲时长配置: {max_duration}，使用默认值600秒")
                return 600

            return int(max_duration)
        except Exception as e:
            self.logger.warning(f"获取最大歌曲时长配置失败: {e}，使用默认值600秒")
            return 600

    def _format_duration_string(self, seconds: int) -> str:
        """
        格式化时长为可读字符串

        Args:
            seconds: 时长（秒）

        Returns:
            格式化的时长字符串 (例: "3:45" 或 "1:23:45")
        """
        if seconds < 3600:  # 小于1小时
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes}:{secs:02d}"
        else:  # 1小时或以上
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            secs = seconds % 60
            return f"{hours}:{minutes:02d}:{secs:02d}"

    def _remove_song_from_tracking(self, song: 'Song') -> None:
        """
        从重复检测器中移除歌曲跟踪

        这是一个集中的辅助方法，确保所有队列移除操作都同步更新重复检测状态。

        Args:
            song: 要移除跟踪的歌曲对象
        """
        self._duplicate_detector.remove_song_for_user(song.audio_info, song.requester)
        self.logger.debug(
            f"移除重复跟踪 - 用户 {song.requester.display_name}: {song.title}"
        )

    def _remove_song_from_duplicate_tracking(self, song: 'Song') -> None:
        """
        从重复检测器中移除歌曲

        这是一个内部辅助方法，确保每当歌曲从队列中移除时，
        都会同步更新重复检测器的状态。

        Args:
            song: 要移除的歌曲对象
        """
        self._duplicate_detector.remove_song_for_user(song.audio_info, song.requester)
        self.logger.debug(f"从重复跟踪中移除歌曲: {song.title} (用户: {song.requester.display_name})")

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

    async def _record_song_to_history(self, audio_info: AudioInfo, requester: discord.Member) -> None:
        """
        记录歌曲到历史数据库（用于抽卡功能）

        Args:
            audio_info: 音频信息
            requester: 请求用户
        """
        try:
            # 检查是否启用抽卡功能
            if self._config_manager:
                card_draw_config = self._config_manager.get('card_draw', {})
                if not card_draw_config.get('enabled', True):
                    return

                # 检查是否启用自动记录
                if not card_draw_config.get('database', {}).get('auto_record', True):
                    return

            # 动态导入以避免循环依赖
            try:
                from similubot.app_commands.card_draw.database import SongHistoryDatabase

                # 创建数据库实例（应该从容器中获取，但这里简化处理）
                database = SongHistoryDatabase()

                # 检测音频源类型
                source_platform = self._detect_source_platform(audio_info.url)

                # 记录到数据库
                success = await database.add_song_record(
                    audio_info=audio_info,
                    requester=requester,
                    guild_id=self.guild_id,
                    source_platform=source_platform
                )

                if success:
                    self.logger.debug(f"歌曲已记录到历史数据库: {audio_info.title}")
                else:
                    self.logger.warning(f"记录歌曲到历史数据库失败: {audio_info.title}")

            except ImportError:
                # 如果抽卡模块不可用，静默跳过
                self.logger.debug("抽卡模块不可用，跳过歌曲历史记录")

        except Exception as e:
            # 记录失败不应该影响正常的队列操作
            self.logger.error(f"记录歌曲历史时发生异常: {e}", exc_info=True)

    def _detect_source_platform(self, url: str) -> str:
        """
        检测音频来源平台

        Args:
            url: 音频URL

        Returns:
            平台名称
        """
        url_lower = url.lower()

        if 'youtube.com' in url_lower or 'youtu.be' in url_lower:
            return 'YouTube'
        elif 'music.163.com' in url_lower or 'music.126.net' in url_lower:
            return 'NetEase'
        elif 'bilibili.com' in url_lower:
            return 'Bilibili'
        elif 'catbox.moe' in url_lower:
            return 'Catbox'
        else:
            return 'Unknown'
    
    async def add_song(self, audio_info: AudioInfo, requester: discord.Member) -> int:
        """
        添加歌曲到队列

        Args:
            audio_info: 音频信息
            requester: 请求用户

        Returns:
            队列中的位置（从1开始）

        Raises:
            DuplicateSongError: 当用户尝试添加重复歌曲时
        """
        async with self._lock:
            # 检查1: 歌曲时长限制（优先检查，即使其他限制被绕过也要检查）
            max_duration = self._get_max_song_duration()
            if audio_info.duration > max_duration:
                error_msg = (
                    f"歌曲时长 {self._format_duration_string(audio_info.duration)} "
                    f"超过了最大限制 {self._format_duration_string(max_duration)}。"
                )
                self.logger.info(
                    f"阻止过长歌曲添加 - 用户 {requester.display_name} ({requester.id}): "
                    f"{audio_info.title} - 时长: {audio_info.duration}s, 限制: {max_duration}s"
                )
                raise SongTooLongError(
                    error_msg, audio_info.title, requester.display_name,
                    audio_info.duration, max_duration
                )

            # 计算当前队列长度（包括正在播放的歌曲）
            current_queue_length = len(self._queue) + (1 if self._current_song else 0)

            # 检查2: 综合检查：重复检测 + 队列公平性
            can_add, error_msg = self._duplicate_detector.can_user_add_song(audio_info, requester, current_queue_length)
            if not can_add:
                self.logger.info(
                    f"阻止歌曲添加 - 用户 {requester.display_name} ({requester.id}): "
                    f"{audio_info.title} - 原因: {error_msg} (队列长度: {current_queue_length})"
                )

                # 根据错误类型抛出相应的异常
                if "已经请求了这首歌曲" in error_msg:
                    raise DuplicateSongError(error_msg, audio_info.title, requester.display_name)
                else:
                    # 队列公平性错误
                    pending_count = self._duplicate_detector.get_user_pending_count(requester)
                    raise QueueFairnessError(error_msg, audio_info.title, requester.display_name, pending_count)

            # 创建歌曲并添加到队列
            song = Song(audio_info=audio_info, requester=requester)
            self._queue.append(song)
            position = len(self._queue)

            # 添加到重复检测器
            self._duplicate_detector.add_song_for_user(audio_info, requester)

            self.logger.info(f"添加歌曲到队列: {song.title} (位置 {position})")

            # 记录到歌曲历史数据库（用于抽卡功能）
            await self._record_song_to_history(audio_info, requester)

            # 保存状态
            await self._save_state()

            return position
    
    def peek_next_song(self, index=0) -> Optional[SongInfo]:
        """
        查看下一首歌曲但不从队列中移除

        Args:
            index: 可选的索引位置（从0开始），如果为None则返回第一首歌曲

        这个方法用于预览下一首歌曲，不会修改队列状态。
        主要用于检查下一首歌曲的点歌人状态等场景。

        Returns:
            下一首歌曲，如果队列为空则返回None
        """
        if not self._queue:
            return None
        
        if index != 0:
            if index < 0 or index >= len(self._queue):
                return None
            return self._queue[index]
        
        return self._queue[0]
    

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

            # 通知重复检测器歌曲开始播放（用于队列公平性跟踪）
            self._duplicate_detector.notify_song_started_playing(song.audio_info, song.requester)

            # 注意：不在这里移除重复跟踪，而是在歌曲播放完成时移除
            # 这样可以防止用户在歌曲播放期间重复添加相同歌曲

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
                    # 从重复检测器中移除跳过的歌曲（使用集中的辅助方法）
                    self._remove_song_from_tracking(removed_song)
                    self.logger.debug(f"跳转时移除歌曲: {removed_song.title}")

            # 获取目标歌曲
            if self._queue:
                song = self._queue.pop(0)
                self._current_song = song
                self._current_position = 0.0  # 重置播放位置

                # 从重复检测器中移除目标歌曲（使用集中的辅助方法）
                self._remove_song_from_tracking(song)

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

            # 从重复检测器中移除歌曲
            self._duplicate_detector.remove_song_for_user(
                removed_song.audio_info, removed_song.requester
            )

            self.logger.info(f"移除位置 {position} 的歌曲: {removed_song.title}")

            # 保存状态
            await self._save_state()

            return removed_song

    async def replace_user_song(self, user: discord.Member, new_audio_info: AudioInfo) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        替换用户在队列中的第一首歌曲

        这个方法允许用户替换其在队列中的第一首歌曲，保持相同的队列位置。
        主要用于队列公平性系统，当用户已有歌曲在队列中时提供替换选项。

        Args:
            user: Discord用户
            new_audio_info: 新歌曲的音频信息

        Returns:
            (成功标志, 队列位置, 错误消息)
        """
        async with self._lock:
            self.logger.debug(f"尝试替换用户歌曲 - 用户: {user.display_name} ({user.id}), 新歌曲: {new_audio_info.title}")

            try:
                # 安全检查1: 检查歌曲时长限制
                max_duration = self._get_max_song_duration()
                if new_audio_info.duration > max_duration:
                    error_msg = (
                        f"新歌曲时长 {self._format_duration_string(new_audio_info.duration)} "
                        f"超过了最大限制 {self._format_duration_string(max_duration)}。"
                    )
                    self.logger.info(f"替换歌曲失败 - 时长超限: {error_msg}")
                    return False, None, error_msg

                # 安全检查2: 防止替换正在播放的歌曲
                if self._current_song and self._current_song.requester.id == user.id:
                    error_msg = "无法替换正在播放的歌曲，请等待当前歌曲播放完成。"
                    self.logger.info(f"替换歌曲失败 - 歌曲正在播放: 用户 {user.display_name}")
                    return False, None, error_msg

                # 安全检查3: 防止替换即将播放的歌曲（队列第一位）
                if self._queue and self._queue[0].requester.id == user.id:
                    error_msg = "无法替换即将播放的歌曲，请等待当前歌曲播放完成。"
                    self.logger.info(f"替换歌曲失败 - 歌曲即将播放: 用户 {user.display_name}")
                    return False, None, error_msg

                # 查找用户在队列中的第一首歌曲
                user_song_index = None

                for i, song in enumerate(self._queue):
                    if song.requester.id == user.id:
                        user_song_index = i
                        break

                if user_song_index is None:
                    error_msg = "您在队列中没有歌曲可以替换。"
                    self.logger.info(f"替换歌曲失败 - 用户无歌曲: 用户 {user.display_name}")
                    return False, None, error_msg

                # 创建新歌曲对象
                new_song = Song(audio_info=new_audio_info, requester=user)

                # 执行替换操作
                old_song = self._queue[user_song_index]
                self._queue[user_song_index] = new_song

                # 更新重复检测器：移除旧歌曲，添加新歌曲
                self._duplicate_detector.remove_song_for_user(old_song.audio_info, user)
                self._duplicate_detector.add_song_for_user(new_audio_info, user)

                # 计算队列位置（从1开始）
                queue_position = user_song_index + 1

                self.logger.info(
                    f"成功替换用户歌曲 - 用户: {user.display_name}, "
                    f"位置: {queue_position}, 旧歌曲: {old_song.title}, 新歌曲: {new_song.title}"
                )

                # 保存状态
                await self._save_state()

                return True, queue_position, None

            except Exception as e:
                error_msg = f"替换歌曲时发生错误: {str(e)}"
                self.logger.error(f"替换用户歌曲时出错: {e}", exc_info=True)
                return False, None, error_msg
    
    async def clear_queue(self) -> int:
        """
        清空整个队列

        Returns:
            移除的歌曲数量
        """
        async with self._lock:
            count = len(self._queue)

            # 从重复检测器中移除所有歌曲（这些歌曲不会正常播放完成）
            for song in self._queue:
                self._remove_song_from_tracking(song)

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
        return [song for song in self._queue[start:end]]  # Convert Song to SongInfo

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

                # 重建重复检测器状态
                self._duplicate_detector.clear_all()
                for song in self._queue:
                    self._duplicate_detector.add_song_for_user(song.audio_info, song.requester)

                invalid_songs = restored_data.get('invalid_songs', [])

                self.logger.info(
                    f"队列状态恢复成功 - 服务器 {self.guild_id}: "
                    f"当前歌曲: {'是' if self._current_song else '否'}, "
                    f"队列长度: {len(self._queue)}, "
                    f"重复检测器跟踪歌曲: {self._duplicate_detector.get_total_tracked_songs()}"
                )

                if invalid_songs:
                    self.logger.warning(f"恢复时发现无效歌曲: {invalid_songs}")

                return True

        except Exception as e:
            self.logger.error(f"从持久化存储恢复队列状态失败: {e}")
            return False

    def check_duplicate_for_user(self, audio_info: AudioInfo, user: discord.Member) -> bool:
        """
        检查歌曲是否为指定用户的重复请求

        Args:
            audio_info: 音频信息
            user: Discord用户

        Returns:
            如果是重复请求则返回True
        """
        return self._duplicate_detector.is_duplicate_for_user(audio_info, user)

    def get_user_song_count(self, user: discord.Member) -> int:
        """
        获取用户当前在队列中的歌曲数量

        Args:
            user: Discord用户

        Returns:
            歌曲数量
        """
        return self._duplicate_detector.get_user_song_count(user)

    def get_duplicate_detection_stats(self) -> Dict[str, int]:
        """
        获取重复检测统计信息

        Returns:
            包含统计信息的字典
        """
        currently_playing_user = self._duplicate_detector.get_currently_playing_user()
        return {
            'total_tracked_songs': self._duplicate_detector.get_total_tracked_songs(),
            'total_users_with_songs': len(self._duplicate_detector._user_songs),
            'total_users_with_pending': len(self._duplicate_detector._user_pending_songs),
            'currently_playing_user': currently_playing_user if currently_playing_user is not None else 0
        }

    def get_user_queue_status(self, user: discord.Member) -> Dict[str, Any]:
        """
        获取用户的详细队列状态

        Args:
            user: Discord用户

        Returns:
            包含用户队列状态的详细信息
        """
        # 计算当前队列长度（包括正在播放的歌曲）
        current_queue_length = len(self._queue) + (1 if self._current_song else 0)
        return self._duplicate_detector.get_user_queue_status(user, current_queue_length)

    def can_user_add_song(self, audio_info: AudioInfo, user: discord.Member) -> Tuple[bool, str]:
        """
        检查用户是否可以添加歌曲

        Args:
            audio_info: 音频信息
            user: Discord用户

        Returns:
            (是否可以添加, 错误消息)
        """
        # 计算当前队列长度（包括正在播放的歌曲）
        current_queue_length = len(self._queue) + (1 if self._current_song else 0)
        return self._duplicate_detector.can_user_add_song(audio_info, user, current_queue_length)

    def notify_song_finished(self, song: SongInfo) -> None:
        """
        通知歌曲播放完成，更新所有相关跟踪状态

        这个方法应该在歌曲实际播放完成时调用，用于：
        1. 清除当前播放用户状态
        2. 从重复检测跟踪中移除歌曲

        Args:
            song: 播放完成的歌曲
        """
        self._duplicate_detector.notify_song_finished_playing(song.audio_info, song.requester)
        self.logger.debug(f"歌曲播放完成，更新跟踪状态: {song.title} - {song.requester.display_name}")

    def _remove_song_from_tracking(self, song: SongInfo) -> None:
        """
        从重复检测器中移除歌曲的辅助方法

        Args:
            song: 要移除的歌曲
        """
        self._duplicate_detector.remove_song_for_user(song.audio_info, song.requester)
