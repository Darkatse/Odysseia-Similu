"""
网易云音乐搜索工具 - 提供歌曲搜索和详细信息获取功能

从歌词模块中提取的可重用搜索功能，支持：
- 歌曲搜索（返回多个结果）
- 歌曲详细信息获取
- 搜索结果排序和过滤
"""

import logging
import asyncio
import aiohttp
import json
import re
from typing import Optional, List, Dict, Any
from urllib.parse import quote

from similubot.core.interfaces import NetEaseSearchResult
from similubot.utils.netease_proxy import get_proxy_manager
from similubot.utils.netease_member import get_member_auth
from similubot.utils.config_manager import ConfigManager


class NetEaseSearchClient:
    """
    网易云音乐搜索客户端
    
    提供歌曲搜索和详细信息获取功能，使用第三方API端点。
    从原有歌词客户端中提取并优化，专注于搜索功能。
    """

    def __init__(self, config: Optional[ConfigManager] = None):
        """
        初始化网易云音乐搜索客户端

        Args:
            config: 配置管理器实例，用于反向代理配置
        """
        self.logger = logging.getLogger("similubot.utils.netease_search")
        self.config = config

        # API端点
        self.search_api = "http://music.163.com/api/search/get"
        self.song_detail_api = "https://api.paugram.com/netease/"

        # 网易API请求头
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "http://music.163.com",
            "Host": "music.163.com"
        }

        # 会话超时
        self.timeout = aiohttp.ClientTimeout(total=10)

        # 初始化代理管理器
        self.proxy_manager = get_proxy_manager(config)

        # 初始化会员认证管理器
        self.member_auth = get_member_auth(config)

        self.logger.debug("网易云音乐搜索客户端初始化完成")

    async def search_songs(self, query: str, limit: int = 5) -> List[NetEaseSearchResult]:
        """
        搜索歌曲并返回结果列表
        
        Args:
            query: 搜索查询字符串
            limit: 返回结果数量限制（默认5个）
            
        Returns:
            搜索结果列表，按相关性排序
        """
        try:
            # 清理搜索查询
            cleaned_query = self._clean_search_query(query)
            self.logger.debug(f"搜索网易云音乐: {cleaned_query}")

            # 搜索参数
            params = {
                's': cleaned_query,
                'type': 1,  # 1 = 歌曲
                'limit': max(limit, 10),  # 获取更多结果以便筛选
            }

            # 处理代理URL和请求头
            search_url, proxy_headers = self.proxy_manager.process_url_and_headers(
                self.search_api, self.headers
            )

            self.logger.debug(f"搜索API URL: {search_url}")

            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(
                    search_url,
                    params=params,
                    headers=proxy_headers
                ) as response:
                    if response.status != 200:
                        self.logger.warning(f"搜索请求失败，状态码: {response.status}")
                        return []

                    # 稳健地处理不同内容类型（从lyrics_client.py学习）
                    data = None

                    # 首先检查内容类型
                    content_type = response.headers.get('content-type', '').lower()
                    self.logger.debug(f"响应内容类型: {content_type}")

                    # 尝试首先获取响应文本
                    try:
                        text_response = await response.text()
                        self.logger.debug(f"响应文本长度: {len(text_response)}")
                    except Exception as e:
                        self.logger.error(f"读取响应文本失败: {e}")
                        return []

                    # 尝试解析为JSON，无论内容类型如何
                    if text_response.strip():
                        try:
                            data = json.loads(text_response)
                            self.logger.debug("成功将响应解析为JSON")
                        except json.JSONDecodeError as e:
                            self.logger.warning(f"响应不是有效的JSON: {e}")
                            self.logger.debug(f"响应内容（前300字符）: {text_response[:300]}...")
                            return []
                    else:
                        self.logger.warning("收到空响应")
                        return []

                    # 检查响应结构
                    if 'result' not in data or 'songs' not in data['result']:
                        self.logger.warning("搜索响应格式异常")
                        return []

                    songs = data['result']['songs']
                    if not songs:
                        self.logger.info(f"未找到匹配的歌曲: {cleaned_query}")
                        return []

                    # 转换为搜索结果对象
                    results = []
                    for song in songs[:limit]:
                        try:
                            result = self._convert_to_search_result(song)
                            if result:
                                results.append(result)
                        except Exception as e:
                            self.logger.warning(f"转换搜索结果时出错: {e}")
                            continue

                    self.logger.info(f"找到 {len(results)} 个搜索结果")
                    return results

        except asyncio.TimeoutError:
            self.logger.error("搜索请求超时")
            return []
        except Exception as e:
            self.logger.error(f"搜索歌曲时出错: {e}", exc_info=True)
            return []

    async def get_song_details(self, song_id: str) -> Optional[Dict[str, Any]]:
        """
        获取歌曲详细信息
        
        Args:
            song_id: 歌曲ID
            
        Returns:
            包含歌曲详细信息的字典，失败时返回None
        """
        try:
            self.logger.debug(f"获取歌曲详细信息: {song_id}")
            
            # 构建API URL
            api_url = f"{self.song_detail_api}?id={song_id}"

            # 处理代理URL和请求头
            detail_url, proxy_headers = self.proxy_manager.process_url_and_headers(
                api_url, self.headers
            )

            self.logger.debug(f"歌曲详情API URL: {detail_url}")

            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(detail_url, headers=proxy_headers) as response:
                    if response.status != 200:
                        self.logger.warning(f"获取歌曲详情失败，状态码: {response.status}")
                        return None

                    # 稳健地处理不同内容类型
                    data = None

                    # 首先检查内容类型
                    content_type = response.headers.get('content-type', '').lower()
                    self.logger.debug(f"歌曲详情API内容类型: {content_type}")

                    # 尝试首先获取响应文本
                    try:
                        text_response = await response.text()
                        self.logger.debug(f"歌曲详情响应文本长度: {len(text_response)}")
                    except Exception as e:
                        self.logger.error(f"读取歌曲详情响应文本失败: {e}")
                        return None

                    # 尝试解析为JSON，无论内容类型如何
                    if text_response.strip():
                        try:
                            data = json.loads(text_response)
                            self.logger.debug("成功将歌曲详情响应解析为JSON")
                        except json.JSONDecodeError as e:
                            self.logger.warning(f"歌曲详情响应不是有效的JSON: {e}")
                            self.logger.debug(f"响应内容（前300字符）: {text_response[:300]}...")
                            return None
                    else:
                        self.logger.warning("收到空的歌曲详情响应")
                        return None

                    # 验证响应数据
                    if not data or 'id' not in data:
                        self.logger.warning(f"歌曲详情响应格式异常: {song_id}")
                        return None

                    self.logger.debug(f"成功获取歌曲详情: {data.get('title', 'Unknown')}")
                    return data

        except asyncio.TimeoutError:
            self.logger.error(f"获取歌曲详情超时: {song_id}")
            return None
        except Exception as e:
            self.logger.error(f"获取歌曲详情时出错 {song_id}: {e}", exc_info=True)
            return None

    def _convert_to_search_result(self, song_data: Dict[str, Any]) -> Optional[NetEaseSearchResult]:
        """
        将API响应转换为搜索结果对象
        
        Args:
            song_data: API返回的歌曲数据
            
        Returns:
            搜索结果对象，转换失败时返回None
        """
        try:
            # 提取基本信息
            song_id = str(song_data.get('id', ''))
            title = song_data.get('name', '未知歌曲')
            duration = song_data.get('duration', 0) // 1000  # 转换为秒
            
            # 提取艺术家信息
            artists = song_data.get('artists', [])
            if artists:
                artist = ', '.join([artist.get('name', '未知艺术家') for artist in artists])
            else:
                artist = '未知艺术家'
            
            # 提取专辑信息
            album_data = song_data.get('album', {})
            album = album_data.get('name', '未知专辑')
            
            # 提取封面URL
            cover_url = None
            if album_data and 'picUrl' in album_data:
                cover_url = album_data['picUrl']
            
            return NetEaseSearchResult(
                song_id=song_id,
                title=title,
                artist=artist,
                album=album,
                cover_url=cover_url,
                duration=duration
            )
            
        except Exception as e:
            self.logger.warning(f"转换搜索结果时出错: {e}")
            return None

    def _clean_search_query(self, query: str) -> str:
        """
        清理搜索查询字符串
        
        Args:
            query: 原始查询字符串
            
        Returns:
            清理后的查询字符串
        """
        if not query:
            return ""
        
        # 移除特殊字符和多余空格
        cleaned = re.sub(r'[^\w\s\u4e00-\u9fff-]', ' ', query)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        return cleaned

    def get_playback_url(self, song_id: str, use_api: bool = True) -> str:
        """
        获取歌曲播放URL

        Args:
            song_id: 歌曲ID
            use_api: 是否使用API端点（默认True），False则使用直接链接

        Returns:
            播放URL（已处理代理域名替换）
        """
        if use_api:
            original_url = f"https://api.paugram.com/netease/?id={song_id}"
        else:
            original_url = f"https://music.163.com/song/media/outer/url?id={song_id}.mp3"

        # 应用代理域名替换
        proxy_url = self.proxy_manager.replace_domain_in_url(original_url)

        self.logger.debug(f"播放URL生成: {original_url} -> {proxy_url}")
        return proxy_url

    async def get_member_playback_url(self, song_id: str, quality_level: Optional[str] = None) -> Optional[str]:
        """
        获取会员播放URL（如果启用会员功能）

        Args:
            song_id: 歌曲ID
            quality_level: 音频质量等级，如果为None则使用默认配置

        Returns:
            会员播放URL，如果获取失败或未启用会员功能则返回None
        """
        if not self.member_auth.is_enabled():
            return None

        try:
            member_url = await self.member_auth.get_member_audio_url(song_id, quality_level)
            if member_url:
                self.logger.debug(f"获取会员播放URL成功: {song_id}")
                return member_url
            else:
                self.logger.debug(f"会员播放URL获取失败: {song_id}")
        except Exception as e:
            self.logger.warning(f"获取会员播放URL时出错: {e}")

        return None


# 全局搜索客户端实例
_search_client: Optional[NetEaseSearchClient] = None


def get_search_client(config: Optional[ConfigManager] = None) -> NetEaseSearchClient:
    """
    获取全局搜索客户端实例

    Args:
        config: 配置管理器实例，用于反向代理配置

    Returns:
        搜索客户端实例
    """
    global _search_client
    if _search_client is None:
        _search_client = NetEaseSearchClient(config)
    return _search_client


# 便捷函数
async def search_songs(query: str, limit: int = 5) -> List[NetEaseSearchResult]:
    """
    搜索歌曲的便捷函数
    
    Args:
        query: 搜索查询
        limit: 结果数量限制
        
    Returns:
        搜索结果列表
    """
    client = get_search_client()
    return await client.search_songs(query, limit)


async def get_song_details(song_id: str) -> Optional[Dict[str, Any]]:
    """
    获取歌曲详情的便捷函数

    Args:
        song_id: 歌曲ID

    Returns:
        歌曲详情字典
    """
    client = get_search_client()
    return await client.get_song_details(song_id)


async def search_song_id(song_title: str, artist: str = "") -> Optional[str]:
    """
    搜索歌曲并返回最佳匹配的歌曲ID

    Args:
        song_title: 歌曲标题
        artist: 艺术家名称（可选，有助于提高搜索准确性）

    Returns:
        歌曲ID字符串，如果未找到则返回None
    """
    try:
        # 构建搜索查询
        if artist:
            query = f"{song_title} {artist}"
        else:
            query = song_title

        # 搜索歌曲
        results = await search_songs(query, limit=5)

        if not results:
            return None

        # 返回第一个结果的ID（最相关的匹配）
        return results[0].song_id

    except Exception as e:
        logger = logging.getLogger("similubot.utils.netease_search")
        logger.error(f"搜索歌曲ID时出错: {e}", exc_info=True)
        return None


async def search_and_get_lyrics(song_title: str, artist: str = "") -> Optional[Dict[str, Any]]:
    """
    搜索歌曲并获取其歌词（为lyrics模块提供兼容接口）

    Args:
        song_title: 歌曲标题
        artist: 艺术家名称（可选）

    Returns:
        包含歌词数据的字典，如果失败则返回None
    """
    try:
        # 首先搜索歌曲ID
        song_id = await search_song_id(song_title, artist)
        if not song_id:
            return None

        # 获取歌曲详情（包含歌词信息）
        song_details = await get_song_details(song_id)
        return song_details

    except Exception as e:
        logger = logging.getLogger("similubot.utils.netease_search")
        logger.error(f"搜索并获取歌词时出错: {e}", exc_info=True)
        return None


def get_playback_url(song_id: str, use_api: bool = True, config: Optional[ConfigManager] = None) -> str:
    """
    获取播放URL的便捷函数

    Args:
        song_id: 歌曲ID
        use_api: 是否使用API端点
        config: 配置管理器实例，用于反向代理配置

    Returns:
        播放URL（已处理代理域名替换）
    """
    client = get_search_client(config)
    return client.get_playback_url(song_id, use_api)
