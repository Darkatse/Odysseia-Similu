"""歌词管理器 - 协调歌词获取、解析和缓存"""

import logging
import asyncio
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from .lyrics_client import NetEaseCloudMusicClient
from .lyrics_parser import LyricsParser, LyricLine


@dataclass
class LyricsData:
    """歌词数据容器"""
    song_id: Optional[str]
    title: str
    artist: str
    lyrics: List[LyricLine]
    raw_lyric: str
    raw_translated: str
    cached: bool = False


class LyricsManager:
    """
    歌词管理器
    
    协调歌词客户端和解析器，提供统一的歌词获取和处理接口。
    包含缓存机制以提高性能。
    """

    def __init__(self):
        """初始化歌词管理器"""
        self.logger = logging.getLogger("similubot.lyrics.lyrics_manager")
        
        # 初始化组件
        self.client = NetEaseCloudMusicClient()
        self.parser = LyricsParser()
        
        # 歌词缓存 - 使用歌曲标题和艺术家作为键
        self._lyrics_cache: Dict[str, Optional[LyricsData]] = {}
        
        # 缓存设置
        self.cache_enabled = True
        self.max_cache_size = 100
        
        self.logger.info("歌词管理器初始化完成")

    async def get_lyrics(self, song_title: str, artist: str = "") -> Optional[LyricsData]:
        """
        获取歌曲的歌词数据
        
        Args:
            song_title: 歌曲标题
            artist: 艺术家名称（可选）
            
        Returns:
            LyricsData对象或None（如果未找到歌词）
        """
        try:
            # 创建缓存键
            cache_key = self._create_cache_key(song_title, artist)
            
            # 检查缓存
            if self.cache_enabled and cache_key in self._lyrics_cache:
                cached_data = self._lyrics_cache[cache_key]
                if cached_data is not None:
                    self.logger.debug(f"从缓存返回歌词: {song_title}")
                    return cached_data
                else:
                    self.logger.debug(f"缓存显示歌词不可用: {song_title}")
                    return None
            
            self.logger.info(f"获取歌词: {song_title} - {artist}")
            
            # 从API获取歌词
            lyrics_response = await self.client.search_and_get_lyrics(song_title, artist)
            
            if not lyrics_response:
                self.logger.debug(f"未找到歌词: {song_title}")
                # 缓存失败以避免重复尝试
                if self.cache_enabled:
                    self._cache_lyrics(cache_key, None)
                return None
            
            # 解析歌词
            raw_lyric = lyrics_response.get('lyric', '')
            raw_translated = lyrics_response.get('sub_lyric', '')
            
            if not raw_lyric or not raw_lyric.strip():
                self.logger.debug(f"歌词内容为空: {song_title}")
                # 缓存失败
                if self.cache_enabled:
                    self._cache_lyrics(cache_key, None)
                return None
            
            # 解析LRC格式歌词
            parsed_lyrics = self.parser.parse_lrc_lyrics(raw_lyric, raw_translated)
            
            if not parsed_lyrics:
                self.logger.debug(f"歌词解析失败: {song_title}")
                # 缓存失败
                if self.cache_enabled:
                    self._cache_lyrics(cache_key, None)
                return None
            
            # 创建歌词数据对象
            lyrics_data = LyricsData(
                song_id=lyrics_response.get('id'),
                title=lyrics_response.get('title', song_title),
                artist=lyrics_response.get('artist', artist),
                lyrics=parsed_lyrics,
                raw_lyric=raw_lyric,
                raw_translated=raw_translated,
                cached=lyrics_response.get('cached', False)
            )
            
            # 缓存结果
            if self.cache_enabled:
                self._cache_lyrics(cache_key, lyrics_data)
            
            self.logger.info(f"成功获取并解析歌词: {song_title} ({len(parsed_lyrics)} 行)")
            return lyrics_data
            
        except Exception as e:
            self.logger.error(f"获取歌词时出错 '{song_title}' by '{artist}': {e}", exc_info=True)
            return None

    def get_current_lyric(self, lyrics_data: LyricsData, current_position: float) -> Optional[LyricLine]:
        """
        获取当前播放位置的歌词行
        
        Args:
            lyrics_data: 歌词数据
            current_position: 当前播放位置（秒）
            
        Returns:
            当前歌词行或None
        """
        if not lyrics_data or not lyrics_data.lyrics:
            return None
        
        return self.parser.get_current_lyric(lyrics_data.lyrics, current_position)

    def get_upcoming_lyric(self, lyrics_data: LyricsData, current_position: float) -> Optional[LyricLine]:
        """
        获取即将到来的歌词行
        
        Args:
            lyrics_data: 歌词数据
            current_position: 当前播放位置（秒）
            
        Returns:
            即将到来的歌词行或None
        """
        if not lyrics_data or not lyrics_data.lyrics:
            return None
        
        return self.parser.get_upcoming_lyric(lyrics_data.lyrics, current_position)

    def get_lyric_context(
        self, 
        lyrics_data: LyricsData, 
        current_position: float, 
        context_lines: int = 1
    ) -> Dict[str, Any]:
        """
        获取歌词上下文信息
        
        Args:
            lyrics_data: 歌词数据
            current_position: 当前播放位置（秒）
            context_lines: 上下文行数
            
        Returns:
            歌词上下文字典
        """
        if not lyrics_data or not lyrics_data.lyrics:
            return {
                'current': None,
                'previous': [],
                'next': [],
                'progress': 0.0
            }
        
        return self.parser.get_lyric_context(lyrics_data.lyrics, current_position, context_lines)

    def is_instrumental_track(self, lyrics_data: LyricsData) -> bool:
        """
        检查是否为器乐曲
        
        Args:
            lyrics_data: 歌词数据
            
        Returns:
            如果是器乐曲则返回True
        """
        if not lyrics_data or not lyrics_data.lyrics:
            return True
        
        return self.parser.is_instrumental_track(lyrics_data.lyrics)

    def format_lyric_display(self, lyric_line: LyricLine, show_translation: bool = True) -> str:
        """
        格式化歌词行以供显示
        
        Args:
            lyric_line: 歌词行
            show_translation: 是否显示翻译
            
        Returns:
            格式化的歌词字符串
        """
        return self.parser.format_lyric_display(lyric_line, show_translation)

    def _create_cache_key(self, song_title: str, artist: str) -> str:
        """
        创建缓存键
        
        Args:
            song_title: 歌曲标题
            artist: 艺术家名称
            
        Returns:
            缓存键字符串
        """
        # 规范化标题和艺术家以提高缓存命中率
        normalized_title = song_title.strip().lower()
        normalized_artist = artist.strip().lower() if artist else ""
        
        if normalized_artist:
            return f"{normalized_title}|{normalized_artist}"
        else:
            return normalized_title

    def _cache_lyrics(self, cache_key: str, lyrics_data: Optional[LyricsData]) -> None:
        """
        缓存歌词数据
        
        Args:
            cache_key: 缓存键
            lyrics_data: 要缓存的歌词数据（可以是None表示未找到）
        """
        try:
            # 检查缓存大小限制
            if len(self._lyrics_cache) >= self.max_cache_size:
                # 移除最旧的条目（简单的FIFO策略）
                oldest_key = next(iter(self._lyrics_cache))
                del self._lyrics_cache[oldest_key]
                self.logger.debug(f"从缓存中移除最旧条目: {oldest_key}")
            
            # 添加到缓存
            self._lyrics_cache[cache_key] = lyrics_data
            self.logger.debug(f"缓存歌词数据: {cache_key}")
            
        except Exception as e:
            self.logger.warning(f"缓存歌词数据失败: {e}")

    def clear_cache(self) -> None:
        """清除歌词缓存"""
        self._lyrics_cache.clear()
        self.logger.info("歌词缓存已清除")

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            缓存统计字典
        """
        return {
            'cache_size': len(self._lyrics_cache),
            'max_cache_size': self.max_cache_size,
            'cache_enabled': self.cache_enabled,
            'cache_keys': list(self._lyrics_cache.keys())
        }

    def set_cache_enabled(self, enabled: bool) -> None:
        """
        启用或禁用缓存
        
        Args:
            enabled: 是否启用缓存
        """
        self.cache_enabled = enabled
        self.logger.info(f"歌词缓存 {'启用' if enabled else '禁用'}")

    def set_max_cache_size(self, max_size: int) -> None:
        """
        设置最大缓存大小
        
        Args:
            max_size: 最大缓存条目数
        """
        if max_size < 1:
            raise ValueError("最大缓存大小必须至少为1")
        
        self.max_cache_size = max_size
        
        # 如果当前缓存超过新限制，修剪它
        while len(self._lyrics_cache) > max_size:
            oldest_key = next(iter(self._lyrics_cache))
            del self._lyrics_cache[oldest_key]
        
        self.logger.info(f"最大缓存大小设置为: {max_size}")

    async def preload_lyrics(self, songs: List[Dict[str, str]]) -> None:
        """
        预加载歌曲列表的歌词
        
        Args:
            songs: 歌曲列表，每个包含 'title' 和可选的 'artist'
        """
        self.logger.info(f"开始预加载 {len(songs)} 首歌曲的歌词")
        
        tasks = []
        for song in songs:
            title = song.get('title', '')
            artist = song.get('artist', '')
            if title:
                task = self.get_lyrics(title, artist)
                tasks.append(task)
        
        if tasks:
            # 并发获取歌词，但限制并发数以避免API限制
            semaphore = asyncio.Semaphore(3)  # 最多3个并发请求
            
            async def limited_get_lyrics(task):
                async with semaphore:
                    return await task
            
            limited_tasks = [limited_get_lyrics(task) for task in tasks]
            results = await asyncio.gather(*limited_tasks, return_exceptions=True)
            
            success_count = sum(1 for result in results if isinstance(result, LyricsData))
            self.logger.info(f"预加载完成: {success_count}/{len(songs)} 首歌曲成功获取歌词")
