"""网易云音乐API客户端 - 歌词获取功能"""

import logging
import asyncio
import aiohttp
import json
from typing import Optional, Dict, Any, Tuple
from urllib.parse import quote

# 延迟导入以避免循环依赖
# from similubot.utils.netease_search import search_song_id, search_and_get_lyrics


class NetEaseCloudMusicClient:
    """
    网易云音乐API客户端
    
    提供歌曲搜索和歌词获取功能，使用第三方API端点。
    """

    def __init__(self):
        """初始化网易云音乐客户端"""
        self.logger = logging.getLogger("similubot.lyrics.lyrics_client")

        # API端点
        self.search_api = "http://music.163.com/api/search/get"
        self.lyrics_api = "https://api.paugram.com/netease/"

        # 网易API请求头
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "http://music.163.com",
            "Host": "music.163.com"
        }

        # 会话超时
        self.timeout = aiohttp.ClientTimeout(total=10)

        self.logger.debug("网易云音乐客户端初始化完成")

    async def search_song_id(self, song_title: str, artist: str = "") -> Optional[str]:
        """
        在网易云音乐搜索歌曲并返回歌曲ID

        使用统一的NetEase搜索实现，消除代码重复。

        Args:
            song_title: 要搜索的歌曲标题
            artist: 艺术家名称（可选，有助于提高搜索准确性）

        Returns:
            歌曲ID字符串，如果未找到则返回None
        """
        try:
            self.logger.debug(f"使用统一搜索功能搜索: {song_title} - {artist}")
            # 延迟导入以避免循环依赖
            from similubot.utils.netease_search import search_song_id as unified_search_song_id
            # 使用统一的搜索功能
            return await unified_search_song_id(song_title, artist)
        except Exception as e:
            self.logger.error(f"搜索歌曲ID时出错: {e}", exc_info=True)
            return None

    async def get_lyrics(self, song_id: str) -> Optional[Dict[str, Any]]:
        """
        使用增强API端点获取歌曲歌词
        
        Args:
            song_id: 网易云音乐歌曲ID
            
        Returns:
            包含歌词数据的字典，如果失败则返回None
        """
        try:
            self.logger.debug(f"获取歌曲ID的歌词: {song_id}")

            url = f"{self.lyrics_api}?id={song_id}"

            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        self.logger.warning(f"歌词API返回状态 {response.status}")
                        return None

                    # 稳健地处理不同内容类型
                    data = None

                    # 首先检查内容类型
                    content_type = response.headers.get('content-type', '').lower()
                    self.logger.debug(f"歌词API内容类型: {content_type}")

                    # 尝试首先获取响应文本
                    try:
                        text_response = await response.text()
                        self.logger.debug(f"歌词响应文本长度: {len(text_response)}")
                    except Exception as e:
                        self.logger.error(f"读取歌词响应文本失败: {e}")
                        return None

                    # 尝试解析为JSON，无论内容类型如何
                    if text_response.strip():
                        try:
                            data = json.loads(text_response)
                            self.logger.debug("成功将歌词响应解析为JSON")
                        except json.JSONDecodeError as e:
                            self.logger.warning(f"歌词响应不是有效的JSON: {e}")
                            self.logger.debug(f"歌词响应内容（前300字符）: {text_response[:300]}...")
                            return None
                    else:
                        self.logger.warning("收到空歌词响应")
                        return None

                    # 提取歌词数据
                    lyrics_data = {
                        'id': data.get('id'),
                        'title': data.get('title'),
                        'artist': data.get('artist'),
                        'album': data.get('album'),
                        'cover': data.get('cover'),
                        'lyric': data.get('lyric', ''),
                        'sub_lyric': data.get('sub_lyric', ''),  # 翻译歌词
                        'link': data.get('link'),
                        'cached': data.get('cached', False)
                    }

                    self.logger.info(f"成功获取歌曲ID的歌词: {song_id}")
                    return lyrics_data

        except asyncio.TimeoutError:
            self.logger.warning(f"获取歌曲ID歌词超时: {song_id}")
            return None
        except Exception as e:
            self.logger.error(f"获取歌曲ID '{song_id}' 歌词时出错: {e}", exc_info=True)
            return None

    def _clean_search_query(self, query: str) -> str:
        """
        清理搜索查询以提高搜索准确性，使用稳健的正则表达式模式
        
        Args:
            query: 原始搜索查询
            
        Returns:
            清理后的搜索查询
        """
        import re

        if not query or not query.strip():
            return ""

        cleaned = query.strip()

        # 定义YouTube标题格式的综合正则表达式模式
        # 不区分大小写的模式，灵活的标点符号
        cleanup_patterns = [
            # 官方视频变体（带括号）
            r'\s*[\(\[\{]\s*official\s+(?:music\s+)?video\s*[\)\]\}]\s*',
            r'\s*[\(\[\{]\s*official\s+audio\s*[\)\]\}]\s*',
            r'\s*[\(\[\{]\s*official\s*[\)\]\}]\s*',

            # 官方变体（不带括号）
            r'\s*-\s*official\s+(?:music\s+)?video\s*',
            r'\s*-\s*official\s+audio\s*',
            r'\s*-\s*official\s*',

            # 歌词视频变体（带括号）
            r'\s*[\(\[\{]\s*lyric\s+video\s*[\)\]\}]\s*',
            r'\s*[\(\[\{]\s*lyrics?\s*[\)\]\}]\s*',
            r'\s*[\(\[\{]\s*with\s+lyrics?\s*[\)\]\}]\s*',

            # 现场表演变体（带括号）
            r'\s*[\(\[\{]\s*live\s+(?:performance|version|at)[^)]*[\)\]\}]\s*',
            r'\s*[\(\[\{]\s*live\s*[\)\]\}]\s*',

            # 混音和版本变体（带括号）
            r'\s*[\(\[\{]\s*(?:remix|extended|radio|clean|explicit)(?:\s+(?:version|edit))?\s*[\)\]\}]\s*',
            r'\s*[\(\[\{]\s*remaster(?:ed)?(?:\s*\d{4})?\s*[\)\]\}]\s*',

            # 特色艺术家模式（带括号）
            r'\s*[\(\[\{]\s*feat\.?\s+[^)]*[\)\]\}]\s*',
            r'\s*[\(\[\{]\s*ft\.?\s+[^)]*[\)\]\}]\s*',
            r'\s*[\(\[\{]\s*featuring\s+[^)]*[\)\]\}]\s*',

            # HD/HQ质量指示器（带括号）
            r'\s*[\(\[\{]\s*(?:hd|hq|4k|1080p|720p)\s*[\)\]\}]\s*',

            # 年份指示器（带括号）
            r'\s*[\(\[\{]\s*(?:19|20)\d{2}\s*[\)\]\}]\s*',

            # 唱片公司后缀（带括号）
            r'\s*[\(\[\{]\s*(?:records?|music|entertainment)\s*[\)\]\}]\s*',

            # Topic频道后缀
            r'\s*-\s*topic\s*$',

            # 特殊Unicode括号及其内容
            r'【[^】]*】',
            r'「[^」]*」',
            r'『[^』]*』',

            # 多个连续破折号或分隔符
            r'\s*[-–—]+\s*$',  # 尾随分隔符
            r'^\s*[-–—]+\s*',  # 前导分隔符
        ]

        # 应用所有清理模式（不区分大小写）
        for pattern in cleanup_patterns:
            cleaned = re.sub(pattern, ' ', cleaned, flags=re.IGNORECASE)

        # 清理额外的空白并规范化
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        # 移除可能剩余的前导/尾随标点符号
        cleaned = re.sub(r'^[^\w\u4e00-\u9fff]+|[^\w\u4e00-\u9fff]+$', '', cleaned)

        return cleaned

    def _construct_search_query(self, cleaned_title: str, artist: str) -> str:
        """
        构建搜索查询，智能处理艺术家以避免重复

        Args:
            cleaned_title: 已清理的歌曲标题
            artist: 艺术家名称

        Returns:
            优化的搜索查询
        """
        import re

        if not artist or not artist.strip():
            return cleaned_title

        artist_clean = artist.strip()
        title_clean = cleaned_title.strip()

        if not title_clean:
            return artist_clean

        # 规范化以进行比较（小写，移除特殊字符）
        def normalize_for_comparison(text: str) -> str:
            # 转换为小写并移除非字母数字字符，除了空格
            normalized = re.sub(r'[^\w\s\u4e00-\u9fff]', ' ', text.lower())
            return re.sub(r'\s+', ' ', normalized).strip()

        artist_normalized = normalize_for_comparison(artist_clean)
        title_normalized = normalize_for_comparison(title_clean)

        # 检查艺术家名称是否已存在于标题中
        artist_words = artist_normalized.split()
        title_words = title_normalized.split()

        # 以不同方式检查艺术家存在
        artist_in_title = False

        # 方法1：精确艺术家名称匹配
        if artist_normalized in title_normalized:
            artist_in_title = True

        # 方法2：对于多词艺术家，检查是否所有重要词都存在
        elif len(artist_words) > 1:
            # 过滤掉常见词如"the"、"and"等
            significant_words = [word for word in artist_words if len(word) > 2 and word not in ['the', 'and', 'or', 'of']]
            if significant_words and all(word in title_normalized for word in significant_words):
                artist_in_title = True

        # 方法3：对于单词艺术家，检查是否在标题中
        else:
            if artist_normalized in title_words:
                artist_in_title = True

        if artist_in_title:
            self.logger.debug(f"艺术家 '{artist_clean}' 已存在于标题中，仅使用标题")
            return title_clean

        # 检查标题中是否已有常见的艺术家-标题分隔符
        separator_patterns = [
            r'^\s*' + re.escape(artist_normalized) + r'\s*[-–—:]\s*',
            r'\s*[-–—:]\s*' + re.escape(artist_normalized) + r'\s*$',
            r'^\s*' + re.escape(artist_normalized) + r'\s+',
        ]

        for pattern in separator_patterns:
            if re.search(pattern, title_normalized):
                self.logger.debug(f"检测到艺术家-标题分隔符，仅使用标题")
                return title_clean

        # 构建带艺术家的搜索查询
        search_query = f"{title_clean} - {artist_clean}".replace("- Topic", "")

        self.logger.debug(f"构建搜索查询: '{search_query}' 来自艺术家: '{artist_clean}' 和标题: '{title_clean}'")
        return search_query

    def _find_best_match(self, songs: list, target_title: str, target_artist: str = "") -> Optional[Dict[str, Any]]:
        """
        从搜索结果中找到最佳匹配歌曲

        Args:
            songs: 网易API的歌曲结果列表
            target_title: 目标歌曲标题
            target_artist: 目标艺术家名称

        Returns:
            最佳匹配的歌曲数据，如果没有好的匹配则返回None
        """
        if not songs:
            return None

        # 如果只有一个结果，返回它
        if len(songs) == 1:
            return songs[0]

        # 基于标题和艺术家相似性为每首歌曲评分
        best_score = 0
        best_match = None

        target_title_lower = target_title.lower()
        target_artist_lower = target_artist.lower()

        for song in songs:
            score = 0
            song_title = song.get('name', '').lower()
            song_artists = [artist.get('name', '').lower() for artist in song.get('artists', [])]

            # 标题相似性（最重要）
            if target_title_lower in song_title or song_title in target_title_lower:
                score += 10
            elif any(word in song_title for word in target_title_lower.split()):
                score += 5

            # 艺术家相似性
            if target_artist_lower:
                for artist in song_artists:
                    if target_artist_lower in artist or artist in target_artist_lower:
                        score += 8
                        break
                    elif any(word in artist for word in target_artist_lower.split()):
                        score += 3
                        break

            # 偏好更高人气的歌曲（如果可用）
            if song.get('popularity', 0) > 50:
                score += 1

            if score > best_score:
                best_score = score
                best_match = song

        # 只有在有合理匹配时才返回
        if best_score >= 5:
            return best_match

        # 如果没有好的匹配，回退到第一个结果
        return songs[0]

    async def search_and_get_lyrics(self, song_title: str, artist: str = "") -> Optional[Dict[str, Any]]:
        """
        在一个操作中搜索歌曲并获取其歌词

        使用统一的NetEase搜索实现，消除代码重复。

        Args:
            song_title: 歌曲标题
            artist: 艺术家名称（可选）

        Returns:
            包含歌词数据的字典，如果失败则返回None
        """
        try:
            self.logger.debug(f"使用统一搜索功能获取歌词: {song_title} - {artist}")
            # 延迟导入以避免循环依赖
            from similubot.utils.netease_search import search_and_get_lyrics as unified_search_and_get_lyrics
            # 使用统一的搜索和获取功能
            return await unified_search_and_get_lyrics(song_title, artist)
        except Exception as e:
            self.logger.error(f"搜索并获取歌词时出错: {e}", exc_info=True)
            return None
