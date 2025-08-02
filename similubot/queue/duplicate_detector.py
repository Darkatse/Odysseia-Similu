"""
重复检测器 - 防止用户添加重复歌曲到队列

提供基于歌曲标题、时长和URL的智能重复检测功能。
支持用户级别的重复跟踪，确保不同用户可以添加相同歌曲。
"""

import logging
import re
from typing import Dict, Set, Optional, Tuple, List, Any
from dataclasses import dataclass
from urllib.parse import urlparse, parse_qs
import discord

from similubot.core.interfaces import AudioInfo


@dataclass
class SongIdentifier:
    """
    歌曲标识符 - 用于唯一标识歌曲
    
    结合标题、时长和URL信息来创建歌曲的唯一标识。
    支持标题的标准化处理以处理轻微的变化。
    """
    normalized_title: str
    duration: int
    url_key: str
    
    def __hash__(self) -> int:
        """计算哈希值用于集合和字典操作"""
        return hash((self.normalized_title, self.duration, self.url_key))
    
    def __eq__(self, other) -> bool:
        """比较两个歌曲标识符是否相等"""
        if not isinstance(other, SongIdentifier):
            return False
        return (
            self.normalized_title == other.normalized_title and
            self.duration == other.duration and
            self.url_key == other.url_key
        )


class DuplicateDetector:
    """
    队列公平性检测器实现

    提供全面的队列公平性控制功能，支持：
    - 基于标题、时长和URL的歌曲识别（重复检测）
    - 用户级别的待播放歌曲跟踪（防止队列垃圾信息）
    - 每用户一次只能有一首待播放歌曲的限制
    - 标题标准化处理
    - 快速查找和验证
    """
    
    def __init__(self, guild_id: int, config_manager=None):
        """
        初始化重复检测器

        Args:
            guild_id: Discord服务器ID
            config_manager: 配置管理器实例
        """
        self.guild_id = guild_id
        self.logger = logging.getLogger(f"similubot.queue.duplicate_detector.{guild_id}")
        self._config_manager = config_manager

        # 用户歌曲映射: user_id -> Set[SongIdentifier] (用于重复检测)
        self._user_songs: Dict[int, Set[SongIdentifier]] = {}

        # 歌曲到用户的反向映射: SongIdentifier -> Set[user_id] (用于重复检测)
        self._song_users: Dict[SongIdentifier, Set[int]] = {}

        # 用户待播放歌曲跟踪: user_id -> List[AudioInfo] (用于队列公平性)
        self._user_pending_songs: Dict[int, List[AudioInfo]] = {}

        # 当前播放歌曲的用户: user_id (用于跟踪谁的歌曲正在播放)
        self._currently_playing_user: Optional[int] = None

        self.logger.debug(f"队列公平性检测器初始化完成 - 服务器 {guild_id}")

    def _get_queue_length_threshold(self) -> int:
        """
        获取队列长度阈值配置

        Returns:
            队列长度阈值，默认为5
        """
        if self._config_manager is None:
            return 5  # 默认值

        try:
            threshold = self._config_manager.get('duplicate_detection.queue_length_threshold', 5)
            # 验证配置值
            if not isinstance(threshold, int) or threshold < 1:
                self.logger.warning(f"无效的队列长度阈值配置: {threshold}，使用默认值5")
                return 5
            return threshold
        except Exception as e:
            self.logger.warning(f"获取队列长度阈值配置失败: {e}，使用默认值5")
            return 5
    
    def _normalize_title(self, title: str) -> str:
        """
        标准化歌曲标题
        
        移除常见的变化因素：
        - 转换为小写
        - 移除多余空格
        - 移除常见的标点符号和特殊字符
        - 移除常见的后缀（如 "Official Video", "Lyrics", etc.）
        
        Args:
            title: 原始标题
            
        Returns:
            标准化后的标题
        """
        if not title:
            return ""
        
        # 转换为小写
        normalized = title.lower().strip()
        
        # 移除常见的后缀和前缀
        suffixes_to_remove = [
            r'\s*\(official\s*(video|audio|music\s*video)?\)',
            r'\s*\[official\s*(video|audio|music\s*video)?\]',
            r'\s*\(lyrics?\)',
            r'\s*\[lyrics?\]',
            r'\s*\(hd\)',
            r'\s*\[hd\]',
            r'\s*\(4k\)',
            r'\s*\[4k\]',
            r'\s*\(remastered\)',
            r'\s*\[remastered\]',
            r'\s*-\s*official\s*(video|audio)',
            r'\s*\|\s*official\s*(video|audio)',
        ]
        
        for suffix_pattern in suffixes_to_remove:
            normalized = re.sub(suffix_pattern, '', normalized, flags=re.IGNORECASE)
        
        # 移除多余的标点符号和特殊字符
        normalized = re.sub(r'[^\w\s\-]', ' ', normalized)
        
        # 标准化空格
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized
    
    def _extract_url_key(self, url: str) -> str:
        """
        从URL提取关键标识符
        
        对于不同类型的URL，提取其核心标识部分：
        - YouTube: 视频ID
        - Catbox: 文件名
        - 其他: 完整URL
        
        Args:
            url: 音频URL
            
        Returns:
            URL关键标识符
        """
        if not url:
            return ""
        
        try:
            parsed = urlparse(url.lower())
            
            # YouTube URL处理
            if 'youtube.com' in parsed.netloc or 'youtu.be' in parsed.netloc:
                if 'youtu.be' in parsed.netloc:
                    # youtu.be/VIDEO_ID 格式
                    return parsed.path.lstrip('/')
                else:
                    # youtube.com/watch?v=VIDEO_ID 格式
                    query_params = parse_qs(parsed.query)
                    video_id = query_params.get('v', [''])[0]
                    return video_id
            
            # Catbox URL处理
            elif 'catbox.moe' in parsed.netloc:
                # 提取文件名
                return parsed.path.split('/')[-1]
            
            # 其他URL，返回完整的标准化URL
            else:
                return url.lower().strip()
                
        except Exception as e:
            self.logger.warning(f"URL解析失败 {url}: {e}")
            return url.lower().strip()
    
    def _create_song_identifier(self, audio_info: AudioInfo) -> SongIdentifier:
        """
        创建歌曲标识符

        Args:
            audio_info: 音频信息

        Returns:
            歌曲标识符
        """
        return SongIdentifier(
            normalized_title=self._normalize_title(audio_info.title),
            duration=audio_info.duration,
            url_key=self._extract_url_key(audio_info.url)
        )

    def is_duplicate_for_user(self, audio_info: AudioInfo, user: discord.Member) -> bool:
        """
        检查歌曲是否为指定用户的重复请求

        Args:
            audio_info: 音频信息
            user: Discord用户

        Returns:
            如果是重复请求则返回True
        """
        song_id = self._create_song_identifier(audio_info)
        user_songs = self._user_songs.get(user.id, set())

        is_duplicate = song_id in user_songs

        if is_duplicate:
            self.logger.debug(
                f"检测到重复歌曲 - 用户 {user.display_name} ({user.id}): "
                f"{audio_info.title} [{song_id.normalized_title}]"
            )

        return is_duplicate

    def can_user_add_song(self, audio_info: AudioInfo, user: discord.Member, current_queue_length: int = 0) -> Tuple[bool, str]:
        """
        检查用户是否可以添加歌曲（综合检查）

        这个方法执行多种检查：
        1. 队列长度阈值：如果队列长度低于阈值，跳过所有限制
        2. 重复检测：用户是否已经请求了相同的歌曲
        3. 队列公平性：用户是否已经有待播放的歌曲

        Args:
            audio_info: 音频信息
            user: Discord用户
            current_queue_length: 当前队列长度（包括正在播放的歌曲）

        Returns:
            (是否可以添加, 错误消息)
        """
        # 检查0: 队列长度阈值检查
        threshold = self._get_queue_length_threshold()
        if current_queue_length < threshold:
            self.logger.debug(
                f"队列长度 {current_queue_length} 低于阈值 {threshold}，跳过所有限制 - "
                f"用户 {user.display_name} ({user.id}): {audio_info.title}"
            )
            return True, ""

        # 检查1: 重复歌曲检测
        if self.is_duplicate_for_user(audio_info, user):
            return False, "您已经请求了这首歌曲，请等待播放完成后再次请求。"

        # 检查2: 队列公平性检测
        if self.has_pending_songs(user):
            pending_count = self.get_user_pending_count(user)
            if pending_count > 0:
                return False, f"您已经有 {pending_count} 首歌曲在队列中等待播放，请等待当前歌曲播放完成后再添加新歌曲。"

        # 检查3: 用户是否有歌曲正在播放
        if self._currently_playing_user == user.id:
            return False, "您的歌曲正在播放中，请等待播放完成后再添加新歌曲。"

        return True, ""

    def has_pending_songs(self, user: discord.Member) -> bool:
        """
        检查用户是否有待播放的歌曲

        Args:
            user: Discord用户

        Returns:
            如果用户有待播放歌曲则返回True
        """
        return user.id in self._user_pending_songs and len(self._user_pending_songs[user.id]) > 0

    def get_user_pending_count(self, user: discord.Member) -> int:
        """
        获取用户待播放歌曲数量

        Args:
            user: Discord用户

        Returns:
            待播放歌曲数量
        """
        return len(self._user_pending_songs.get(user.id, []))

    def add_song_for_user(self, audio_info: AudioInfo, user: discord.Member) -> None:
        """
        为用户添加歌曲到跟踪列表（包括重复检测和队列公平性跟踪）

        Args:
            audio_info: 音频信息
            user: Discord用户
        """
        song_id = self._create_song_identifier(audio_info)

        # 1. 添加到重复检测跟踪
        if user.id not in self._user_songs:
            self._user_songs[user.id] = set()
        self._user_songs[user.id].add(song_id)

        # 添加到歌曲用户反向映射
        if song_id not in self._song_users:
            self._song_users[song_id] = set()
        self._song_users[song_id].add(user.id)

        # 2. 添加到待播放歌曲跟踪
        if user.id not in self._user_pending_songs:
            self._user_pending_songs[user.id] = []
        self._user_pending_songs[user.id].append(audio_info)

        self.logger.debug(
            f"添加歌曲跟踪 - 用户 {user.display_name} ({user.id}): "
            f"{audio_info.title} [{song_id.normalized_title}] "
            f"(待播放: {len(self._user_pending_songs[user.id])})"
        )

    def remove_song_for_user(self, audio_info: AudioInfo, user: discord.Member) -> None:
        """
        从用户的跟踪列表中移除歌曲（包括重复检测和待播放跟踪）

        Args:
            audio_info: 音频信息
            user: Discord用户
        """
        song_id = self._create_song_identifier(audio_info)

        # 1. 从重复检测跟踪中移除
        if user.id in self._user_songs:
            self._user_songs[user.id].discard(song_id)
            if not self._user_songs[user.id]:
                del self._user_songs[user.id]

        # 从歌曲用户反向映射中移除
        if song_id in self._song_users:
            self._song_users[song_id].discard(user.id)
            if not self._song_users[song_id]:
                del self._song_users[song_id]

        # 2. 从待播放歌曲跟踪中移除
        if user.id in self._user_pending_songs:
            user_pending = self._user_pending_songs[user.id]
            # 找到并移除匹配的歌曲（通过标题和URL匹配）
            for i, pending_song in enumerate(user_pending):
                if (pending_song.title == audio_info.title and
                    pending_song.url == audio_info.url):
                    user_pending.pop(i)
                    break

            # 如果用户没有更多待播放歌曲，清理空列表
            if not user_pending:
                del self._user_pending_songs[user.id]

        self.logger.debug(
            f"移除歌曲跟踪 - 用户 {user.display_name} ({user.id}): "
            f"{audio_info.title} [{song_id.normalized_title}] "
            f"(剩余待播放: {self.get_user_pending_count(user)})"
        )

    def clear_user_songs(self, user: discord.Member) -> int:
        """
        清空指定用户的所有歌曲跟踪（包括重复检测和待播放跟踪）

        Args:
            user: Discord用户

        Returns:
            清除的歌曲数量
        """
        total_count = 0

        # 清空重复检测跟踪
        if user.id in self._user_songs:
            user_songs = self._user_songs[user.id].copy()
            total_count += len(user_songs)

            # 从反向映射中移除用户
            for song_id in user_songs:
                if song_id in self._song_users:
                    self._song_users[song_id].discard(user.id)
                    if not self._song_users[song_id]:
                        del self._song_users[song_id]

            # 清空用户歌曲映射
            del self._user_songs[user.id]

        # 清空待播放歌曲跟踪
        if user.id in self._user_pending_songs:
            pending_count = len(self._user_pending_songs[user.id])
            del self._user_pending_songs[user.id]
            self.logger.debug(f"清空用户待播放歌曲 - {user.display_name} ({user.id}): {pending_count} 首")

        # 如果该用户正在播放，清除播放状态
        if self._currently_playing_user == user.id:
            self._currently_playing_user = None

        self.logger.debug(f"清空用户所有跟踪 - {user.display_name} ({user.id}): {total_count} 首歌曲")

        return total_count

    def clear_all(self) -> int:
        """
        清空所有跟踪数据（包括重复检测和待播放跟踪）

        Returns:
            清除的总歌曲跟踪数量
        """
        # 统计总数
        duplicate_count = sum(len(songs) for songs in self._user_songs.values())
        pending_count = sum(len(songs) for songs in self._user_pending_songs.values())
        total_count = duplicate_count + pending_count

        # 清空所有跟踪数据
        self._user_songs.clear()
        self._song_users.clear()
        self._user_pending_songs.clear()
        self._currently_playing_user = None

        self.logger.debug(f"清空所有跟踪数据: {duplicate_count} 重复跟踪, {pending_count} 待播放跟踪")

        return total_count

    def get_user_song_count(self, user: discord.Member) -> int:
        """
        获取用户当前跟踪的歌曲数量

        Args:
            user: Discord用户

        Returns:
            歌曲数量
        """
        return len(self._user_songs.get(user.id, set()))

    def get_total_tracked_songs(self) -> int:
        """
        获取当前跟踪的总歌曲数量（去重）

        Returns:
            总歌曲数量
        """
        return len(self._song_users)

    def get_duplicate_info(self, audio_info: AudioInfo) -> Optional[Tuple[SongIdentifier, Set[int]]]:
        """
        获取歌曲的重复信息

        Args:
            audio_info: 音频信息

        Returns:
            如果歌曲已被跟踪，返回 (歌曲标识符, 请求用户ID集合)，否则返回None
        """
        song_id = self._create_song_identifier(audio_info)

        if song_id in self._song_users:
            return song_id, self._song_users[song_id].copy()

        return None

    def notify_song_started_playing(self, audio_info: AudioInfo, user: discord.Member) -> None:
        """
        通知歌曲开始播放

        当歌曲开始播放时调用此方法，用于：
        1. 设置当前播放用户
        2. 从用户的待播放列表中移除该歌曲

        Args:
            audio_info: 开始播放的音频信息
            user: 请求该歌曲的用户
        """
        # 设置当前播放用户
        self._currently_playing_user = user.id

        # 从待播放列表中移除该歌曲
        if user.id in self._user_pending_songs:
            user_pending = self._user_pending_songs[user.id]
            # 找到并移除匹配的歌曲（通过标题和URL匹配）
            for i, pending_song in enumerate(user_pending):
                if (pending_song.title == audio_info.title and
                    pending_song.url == audio_info.url):
                    user_pending.pop(i)
                    break

            # 如果用户没有更多待播放歌曲，清理空列表
            if not user_pending:
                del self._user_pending_songs[user.id]

        self.logger.debug(
            f"歌曲开始播放 - 用户 {user.display_name} ({user.id}): "
            f"{audio_info.title} (剩余待播放: {self.get_user_pending_count(user)})"
        )

    def notify_song_finished_playing(self, audio_info: AudioInfo, user: discord.Member) -> None:
        """
        通知歌曲播放完成

        当歌曲播放完成时调用此方法，用于：
        1. 清除当前播放用户
        2. 从重复检测跟踪中移除该歌曲

        Args:
            audio_info: 播放完成的音频信息
            user: 请求该歌曲的用户
        """
        # 清除当前播放用户
        if self._currently_playing_user == user.id:
            self._currently_playing_user = None

        # 从重复检测跟踪中移除
        self.remove_song_for_user(audio_info, user)

        self.logger.debug(
            f"歌曲播放完成 - 用户 {user.display_name} ({user.id}): "
            f"{audio_info.title} (剩余待播放: {self.get_user_pending_count(user)})"
        )

    def get_currently_playing_user(self) -> Optional[int]:
        """
        获取当前播放歌曲的用户ID

        Returns:
            当前播放用户的ID，如果没有歌曲在播放则返回None
        """
        return self._currently_playing_user

    def get_user_queue_status(self, user: discord.Member, current_queue_length: int = 0) -> Dict[str, Any]:
        """
        获取用户的队列状态信息

        Args:
            user: Discord用户
            current_queue_length: 当前队列长度（包括正在播放的歌曲）

        Returns:
            包含用户队列状态的字典
        """
        pending_count = self.get_user_pending_count(user)
        is_playing = self._currently_playing_user == user.id
        threshold = self._get_queue_length_threshold()
        restrictions_bypassed = current_queue_length < threshold

        return {
            'user_id': user.id,
            'user_name': user.display_name,
            'pending_songs': pending_count,
            'is_currently_playing': is_playing,
            'can_add_song': restrictions_bypassed or (pending_count == 0 and not is_playing),
            'pending_song_titles': [song.title for song in self._user_pending_songs.get(user.id, [])],
            'queue_length': current_queue_length,
            'queue_length_threshold': threshold,
            'restrictions_bypassed': restrictions_bypassed
        }
