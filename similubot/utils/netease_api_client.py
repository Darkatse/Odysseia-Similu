"""
网易云音乐 API 客户端 - 封装所有对网易云API的直接请求

负责处理网易云音乐的所有API调用，包括：
- 歌曲元数据获取
- 播放链接获取
- 代理和会员认证处理
"""

import logging
import asyncio
from typing import Optional, Dict, Any
from urllib.parse import urlparse, parse_qs

from similubot.utils.netease_search import get_song_details, get_playback_url, search_songs
from similubot.utils.netease_proxy import get_proxy_manager
from similubot.utils.netease_member import get_member_auth
from similubot.utils.config_manager import ConfigManager


class NetEaseApiClient:
    """
    网易云音乐 API 客户端
    
    封装所有对网易云音乐API的直接调用，处理代理、会员认证等复杂逻辑。
    提供统一的接口供 NetEaseProvider 使用。
    """
    
    def __init__(self, config: Optional[ConfigManager] = None):
        """
        初始化网易云音乐 API 客户端
        
        Args:
            config: 配置管理器实例，用于反向代理和会员认证配置
        """
        self.config = config
        self.logger = logging.getLogger("similubot.utils.netease_api_client")
        
        # 初始化代理管理器
        self.proxy_manager = get_proxy_manager(config)
        
        # 初始化会员认证管理器
        self.member_auth = get_member_auth(config)
        
        self.logger.debug("网易云音乐 API 客户端初始化完成")
    
    async def get_song_metadata(self, song_id: str) -> Optional[Dict[str, Any]]:
        """
        通过歌曲ID获取完整的歌曲元数据
        
        Args:
            song_id: 歌曲ID
            
        Returns:
            歌曲元数据字典，包含title、artist、duration等信息
        """
        try:
            self.logger.debug(f"开始获取歌曲元数据: {song_id}")
            
            # 使用现有的歌曲详情API
            song_details = await get_song_details(song_id)
            if not song_details:
                self.logger.warning(f"无法获取歌曲详情: {song_id}")
                return None
            
            # 提取基本信息
            title = song_details.get('title', '未知歌曲')
            artist = song_details.get('artist', '未知艺术家')
            
            # 获取时长信息 - 通过搜索API获取更准确的时长
            duration = await self._get_song_duration(song_id, title, artist)
            
            # 构建完整的元数据
            metadata = {
                'song_id': song_id,
                'title': title,
                'artist': artist,
                'duration': duration,
                'cover_url': song_details.get('cover_url') or song_details.get('cover'),
                'album': song_details.get('album'),
                'source': 'NetEase'
            }
            
            self.logger.debug(f"获取歌曲元数据成功: {title} - {artist} (ID: {song_id})")
            return metadata
            
        except Exception as e:
            self.logger.error(f"获取歌曲元数据失败 (ID: {song_id}): {e}", exc_info=True)
            return None
    
    async def fetch_playback_url(self, song_id: str) -> Optional[str]:
        """
        获取歌曲的可播放直链URL
        
        Args:
            song_id: 歌曲ID
            
        Returns:
            可播放的直链URL，获取失败时返回None
        """
        try:
            self.logger.debug(f"开始获取播放链接: {song_id}")
            
            # 1. 尝试使用会员认证获取高质量音频URL（如果启用）
            if self.member_auth.is_enabled():
                try:
                    member_url = await self.member_auth.get_member_audio_url(song_id)
                    if member_url:
                        self.logger.debug(f"使用会员音频URL: {song_id}")
                        return member_url
                    else:
                        self.logger.debug(f"会员音频URL获取失败，回退到免费模式: {song_id}")
                except Exception as e:
                    self.logger.warning(f"获取会员音频URL时出错: {e}")
            
            # 2. 回退到免费模式，尝试API模式
            try:
                api_url = get_playback_url(song_id, use_api=True, config=self.config)
                if api_url:
                    self.logger.debug(f"使用API模式播放URL: {song_id}")
                    return api_url
            except Exception as e:
                self.logger.warning(f"API模式播放URL获取失败: {e}")
            
            # 3. 最后尝试直接模式
            try:
                direct_url = get_playback_url(song_id, use_api=False, config=self.config)
                if direct_url:
                    self.logger.debug(f"使用直接模式播放URL: {song_id}")
                    return direct_url
            except Exception as e:
                self.logger.warning(f"直接模式播放URL获取失败: {e}")
            
            self.logger.error(f"所有播放URL获取方法都失败: {song_id}")
            return None
            
        except Exception as e:
            self.logger.error(f"获取播放链接时出错 (ID: {song_id}): {e}", exc_info=True)
            return None
    
    async def _get_song_duration(self, song_id: str, title: str, artist: str) -> int:
        """
        获取歌曲时长信息
        
        由于歌曲详情API不包含时长信息，需要通过搜索API获取
        
        Args:
            song_id: 歌曲ID
            title: 歌曲标题
            artist: 艺术家名称
            
        Returns:
            歌曲时长（秒），获取失败时返回0
        """
        try:
            # 构建搜索查询，优先使用标题+艺术家
            if artist and artist != '未知艺术家':
                query = f"{title} {artist}"
            else:
                query = title
            
            self.logger.debug(f"搜索歌曲时长: {query}")
            
            # 搜索歌曲
            search_results = await search_songs(query, limit=10)
            
            if not search_results:
                self.logger.warning(f"搜索无结果，无法获取时长: {query}")
                return 0
            
            # 查找匹配的歌曲ID
            for result in search_results:
                if result.song_id == song_id:
                    self.logger.debug(f"找到匹配歌曲，时长: {result.duration}秒")
                    return result.duration
            
            # 如果没有找到完全匹配的ID，使用第一个结果的时长作为估计
            # 这种情况可能发生在搜索结果中有相同歌曲的不同版本时
            first_result = search_results[0]
            if (first_result.title.lower() == title.lower() or
                title.lower() in first_result.title.lower() or
                first_result.title.lower() in title.lower()):
                self.logger.debug(f"使用相似歌曲的时长估计: {first_result.duration}秒")
                return first_result.duration
            
            self.logger.warning(f"未找到匹配的歌曲ID {song_id}，无法获取准确时长")
            return 0
            
        except Exception as e:
            self.logger.error(f"获取歌曲时长时出错: {e}", exc_info=True)
            return 0
    
    async def is_song_available_for_member(self, song_id: str) -> bool:
        """
        检查歌曲是否对会员可用
        
        Args:
            song_id: 歌曲ID
            
        Returns:
            如果对会员可用则返回True
        """
        if not self.member_auth.is_enabled():
            return False
        
        try:
            return await self.member_auth.is_song_available_for_member(song_id)
        except Exception as e:
            self.logger.warning(f"检查会员权限时出错: {e}")
            return False
    
    def extract_song_id_from_url(self, url: str) -> Optional[str]:
        """
        从各种网易云音乐URL中提取歌曲ID
        
        Args:
            url: 网易云音乐URL
            
        Returns:
            歌曲ID，提取失败时返回None
        """
        try:
            # 支持的URL模式（包含歌曲ID的模式）
            import re
            id_patterns = [
                r'music\.163\.com/song\?id=(\d+)',
                r'music\.163\.com/#/song\?id=(\d+)',
                r'music\.163\.com/m/song\?id=(\d+)',
                r'y\.music\.163\.com/m/song\?id=(\d+)',
                r'music\.163\.com/song/media/outer/url\?id=(\d+)',
                r'api\.paugram\.com/netease/\?id=(\d+)',
            ]
            
            # 尝试所有模式
            for pattern in id_patterns:
                match = re.search(pattern, url)
                if match:
                    song_id = match.group(1)
                    self.logger.debug(f"从URL提取歌曲ID: {song_id}")
                    return song_id
            
            # 如果正则匹配失败，尝试解析查询参数
            parsed = urlparse(url)
            if parsed.query:
                query_params = parse_qs(parsed.query)
                if 'id' in query_params:
                    song_id = query_params['id'][0]
                    self.logger.debug(f"从查询参数提取歌曲ID: {song_id}")
                    return song_id
            
            self.logger.warning(f"无法从URL提取歌曲ID: {url}")
            return None
            
        except Exception as e:
            self.logger.error(f"提取歌曲ID时出错: {e}")
            return None
