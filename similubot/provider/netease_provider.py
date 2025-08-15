"""
网易云音乐提供者 - 处理网易云音乐的音频提取和下载

集成到现有的音频提供者系统中，支持：
- 网易云音乐URL识别
- 音频信息提取
- 音频文件下载（通过API）
"""

import logging
import asyncio
import aiohttp
import os
import re
from typing import Optional, Tuple, Dict, Any
from urllib.parse import urlparse, parse_qs

from similubot.core.interfaces import AudioInfo
from similubot.progress.base import ProgressCallback, ProgressInfo, ProgressStatus
from similubot.utils.netease_search import get_song_details, get_playback_url
from similubot.utils.netease_proxy import get_proxy_manager
from similubot.utils.netease_member import get_member_auth
from similubot.utils.config_manager import ConfigManager
from .base import BaseAudioProvider


class NetEaseProvider(BaseAudioProvider):
    """
    网易云音乐音频提供者
    
    处理网易云音乐链接的音频提取和下载。
    支持多种网易云音乐URL格式。
    """
    
    def __init__(self, temp_dir: str = "./temp", config: Optional[ConfigManager] = None):
        """
        初始化网易云音乐提供者

        Args:
            temp_dir: 临时文件目录
            config: 配置管理器实例，用于反向代理配置
        """
        super().__init__("NetEase", temp_dir)
        self.config = config

        # 支持的URL模式
        self.url_patterns = [
            # 官方网易云音乐URL
            r'music\.163\.com/song\?id=(\d+)',
            r'music\.163\.com/#/song\?id=(\d+)',
            r'music\.163\.com/m/song\?id=(\d+)',
            r'y\.music\.163\.com/m/song\?id=(\d+)',
            # 网易云音乐媒体URL
            r'music\.163\.com/song/media/outer/url\?id=(\d+)',
            # API代理端点URL（用于播放）
            r'api\.paugram\.com/netease/\?id=(\d+)',
            # 会员音频直链URL（支持所有music.126.net子域名）
            r'[a-z0-9]+\.music\.126\.net/.+\.(mp3|flac|m4a|aac)',
            # 网易云音乐CDN直链（备用）
            r'music\.126\.net/.+\.(mp3|flac|m4a|aac)',
        ]

        # 编译正则表达式
        self.compiled_patterns = [re.compile(pattern) for pattern in self.url_patterns]

        # 会话超时
        self.timeout = aiohttp.ClientTimeout(total=30)

        # 初始化代理管理器
        self.proxy_manager = get_proxy_manager(config)

        # 初始化会员认证管理器
        self.member_auth = get_member_auth(config)

        # URL到歌曲ID的映射缓存（用于直接音频URL的元数据提取）
        self._url_song_id_cache = {}

        self.logger.debug("网易云音乐提供者初始化完成")
    
    def is_supported_url(self, url: str) -> bool:
        """
        检查URL是否为支持的网易云音乐链接
        
        Args:
            url: 要检查的URL
            
        Returns:
            如果支持则返回True
        """
        if not url:
            return False
        
        # 检查是否匹配任何支持的模式
        for pattern in self.compiled_patterns:
            if pattern.search(url):
                return True
        
        return False
    
    def _extract_song_id(self, url: str) -> Optional[str]:
        """
        从URL中提取歌曲ID

        Args:
            url: 网易云音乐URL

        Returns:
            歌曲ID，提取失败时返回None
        """
        try:
            # 尝试所有模式（前6个模式包含歌曲ID）
            for i, pattern in enumerate(self.compiled_patterns):
                match = pattern.search(url)
                if match:
                    # 前6个模式包含歌曲ID
                    if i < 6:
                        song_id = match.group(1)
                        self.logger.debug(f"从URL提取歌曲ID: {song_id}")
                        return song_id
                    else:
                        # 直接音频URL，没有歌曲ID
                        self.logger.debug(f"检测到直接音频URL，无歌曲ID: {url}")
                        return None

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

    def _is_direct_audio_url(self, url: str) -> bool:
        """
        检查是否为直接音频URL（会员音频链接）

        Args:
            url: 要检查的URL

        Returns:
            如果是直接音频URL则返回True
        """
        # 检查最后两个模式（直接音频URL）
        for pattern in self.compiled_patterns[-2:]:
            if pattern.search(url):
                return True
        return False

    def _extract_metadata_from_direct_url(self, url: str, song_id: Optional[str] = None) -> tuple:
        """
        从直接音频URL中提取基本元数据

        Args:
            url: 直接音频URL
            song_id: 关联的歌曲ID（如果有）

        Returns:
            (title, artist, duration, song_id) 元组
        """
        try:
            parsed = urlparse(url)

            # 从文件路径提取信息
            path_parts = parsed.path.split('/')
            filename = path_parts[-1] if path_parts else "unknown"

            # 移除文件扩展名和查询参数
            title = os.path.splitext(filename)[0]

            # 如果提供了歌曲ID，优先使用它
            if song_id:
                self.logger.debug(f"使用提供的歌曲ID: {song_id}")
                return title, "网易云音乐", 0, song_id

            # 尝试从URL路径中提取可能的歌曲ID
            # 网易云音乐的直接URL有时在路径中包含歌曲ID
            for part in path_parts:
                if part.isdigit() and len(part) >= 6:  # 歌曲ID通常是6位以上的数字
                    potential_song_id = part
                    self.logger.debug(f"从URL路径提取到潜在歌曲ID: {potential_song_id}")
                    return title, "网易云音乐", 0, potential_song_id

            # 如果标题是哈希值或无意义字符串，使用默认值
            if len(title) > 32 or not any(c.isalpha() for c in title):
                title = "网易云音乐会员音频"

            return title, "网易云音乐", 0, None

        except Exception as e:
            self.logger.warning(f"从直接URL提取元数据失败: {e}")
            return "网易云音乐会员音频", "网易云音乐", 0, None

    async def _get_song_metadata_by_id(self, song_id: str) -> Optional[Dict[str, Any]]:
        """
        通过歌曲ID获取完整的歌曲元数据

        Args:
            song_id: 歌曲ID

        Returns:
            歌曲元数据字典，包含title、artist、duration等信息
        """
        try:
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
                'cover_url': song_details.get('cover_url'),
                'album': song_details.get('album'),
                'source': 'NetEase'
            }

            self.logger.debug(f"获取歌曲元数据成功: {title} - {artist} (ID: {song_id})")
            return metadata

        except Exception as e:
            self.logger.error(f"获取歌曲元数据失败 (ID: {song_id}): {e}")
            return None

    async def _extract_audio_info_from_direct_url(self, url: str, context_song_id: Optional[str] = None) -> Optional[AudioInfo]:
        """
        从直接音频URL提取音频信息（会员音频链接）

        Args:
            url: 直接音频URL
            context_song_id: 上下文中的歌曲ID（来自会员认证系统）

        Returns:
            音频信息，失败时返回None
        """
        try:
            # 首先尝试从URL和上下文提取基本元数据
            title, artist, duration, extracted_song_id = self._extract_metadata_from_direct_url(url, context_song_id)

            # 确定要使用的歌曲ID（优先使用上下文ID）
            song_id = context_song_id or extracted_song_id

            # 如果有歌曲ID，尝试获取完整的元数据
            if song_id:
                self.logger.debug(f"尝试通过歌曲ID获取完整元数据: {song_id}")
                metadata = await self._get_song_metadata_by_id(song_id)

                if metadata:
                    # 使用API获取的完整元数据
                    title = metadata['title']
                    artist = metadata['artist']
                    duration = metadata['duration']
                    thumbnail_url = metadata.get('cover_url')
                    self.logger.debug(f"使用API元数据: {title} - {artist}")
                else:
                    # API失败，使用基本元数据
                    thumbnail_url = None
                    self.logger.debug(f"API获取元数据失败，使用基本元数据: {title} - {artist}")
            else:
                # 没有歌曲ID，只能使用基本元数据
                thumbnail_url = None
                self.logger.debug(f"无歌曲ID，使用基本元数据: {title} - {artist}")

            # 处理代理URL（重要：在创建AudioInfo之前处理）
            processed_url = self._process_direct_url_for_proxy(url)

            # 创建音频信息对象
            audio_info = AudioInfo(
                title=title,
                uploader=artist,  # AudioInfo使用uploader字段而不是artist
                duration=duration,
                url=processed_url,  # 使用处理后的URL
                thumbnail_url=thumbnail_url
            )

            self.logger.debug(f"从直接URL提取音频信息成功: {title} - {artist}")
            return audio_info

        except Exception as e:
            self.logger.error(f"从直接URL提取音频信息失败: {e}")
            return None

    def _process_direct_url_for_proxy(self, url: str) -> str:
        """
        为直接音频URL处理代理配置

        Args:
            url: 原始直接音频URL

        Returns:
            处理后的URL
        """
        try:
            # 检查是否启用了代理
            if not self.proxy_manager.is_enabled():
                self.logger.debug("代理未启用，保持原始URL")
                return url

            # 获取域名映射配置
            domain_mapping = self.proxy_manager.get_domain_mapping()
            parsed = urlparse(url)
            original_domain = parsed.netloc.lower().split(':')[0]  # 移除端口号

            # 检查是否有针对music.126.net的特定配置
            mapped_domain = None
            for source_domain, target_domain in domain_mapping.items():
                if original_domain == source_domain.lower():
                    mapped_domain = target_domain
                    break

            # 如果映射的域名与原域名相同，说明配置为直连
            if mapped_domain and mapped_domain.lower() == original_domain:
                self.logger.debug(f"域名 {original_domain} 配置为直连，保持原始URL")
                return url

            # 应用代理域名替换
            processed_url = self.proxy_manager.replace_domain_in_url(url)

            if processed_url != url:
                self.logger.debug(f"应用代理配置: {url[:60]}... -> {processed_url[:60]}...")
            else:
                self.logger.debug("代理配置未改变URL")

            return processed_url

        except Exception as e:
            self.logger.error(f"处理直接URL代理配置时出错: {e}")
            return url

    def _cache_url_song_id_mapping(self, url: str, song_id: str):
        """
        缓存URL到歌曲ID的映射

        Args:
            url: 音频URL
            song_id: 对应的歌曲ID
        """
        try:
            # 使用URL的主要部分作为键（去除查询参数中的时效性参数）
            parsed = urlparse(url)
            cache_key = f"{parsed.netloc}{parsed.path}"

            self._url_song_id_cache[cache_key] = song_id
            self.logger.debug(f"缓存URL到歌曲ID映射: {cache_key[:50]}... -> {song_id}")

            # 限制缓存大小，避免内存泄漏
            if len(self._url_song_id_cache) > 1000:
                # 移除最旧的一半条目
                items = list(self._url_song_id_cache.items())
                self._url_song_id_cache = dict(items[500:])
                self.logger.debug("清理URL歌曲ID缓存")

        except Exception as e:
            self.logger.warning(f"缓存URL歌曲ID映射时出错: {e}")

    def _get_cached_song_id(self, url: str) -> Optional[str]:
        """
        从缓存中获取URL对应的歌曲ID

        Args:
            url: 音频URL

        Returns:
            歌曲ID，如果未找到则返回None
        """
        try:
            parsed = urlparse(url)
            cache_key = f"{parsed.netloc}{parsed.path}"

            song_id = self._url_song_id_cache.get(cache_key)
            if song_id:
                self.logger.debug(f"从缓存获取歌曲ID: {cache_key[:50]}... -> {song_id}")

            return song_id

        except Exception as e:
            self.logger.warning(f"从缓存获取歌曲ID时出错: {e}")
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
            from similubot.utils.netease_search import search_songs

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

    async def _extract_audio_info_impl(self, url: str) -> Optional[AudioInfo]:
        """
        从网易云音乐URL提取音频信息

        Args:
            url: 网易云音乐URL

        Returns:
            音频信息，失败时返回None
        """
        try:
            # 检查是否为直接音频URL
            if self._is_direct_audio_url(url):
                # 尝试从缓存获取关联的歌曲ID
                cached_song_id = self._get_cached_song_id(url)
                return await self._extract_audio_info_from_direct_url(url, cached_song_id)

            # 提取歌曲ID
            song_id = self._extract_song_id(url)
            if not song_id:
                return None
            
            # 获取歌曲详细信息
            song_details = await get_song_details(song_id)
            if not song_details:
                self.logger.warning(f"无法获取歌曲详情: {song_id}")
                return None
            
            # 构建音频信息
            title = song_details.get('title', '未知歌曲')
            artist = song_details.get('artist', '未知艺术家')

            # 获取时长信息 - 歌曲详情API不包含时长，需要通过搜索获取
            duration = await self._get_song_duration(song_id, title, artist)

            # 尝试获取会员音频URL（如果启用会员功能）
            playback_url = None
            if self.member_auth.is_enabled():
                try:
                    member_url = await self.member_auth.get_member_audio_url(song_id)
                    if member_url:
                        playback_url = member_url
                        # 缓存URL到歌曲ID的映射，用于后续的元数据提取
                        self._cache_url_song_id_mapping(member_url, song_id)
                        self.logger.debug(f"使用会员音频URL: {song_id}")
                    else:
                        self.logger.debug(f"会员音频URL获取失败，回退到免费模式: {song_id}")
                except Exception as e:
                    self.logger.warning(f"获取会员音频URL时出错: {e}")

            # 如果没有获取到会员URL，使用免费模式
            if not playback_url:
                # 尝试从link字段获取实际播放URL
                playback_url = song_details.get('link')
                if not playback_url:
                    # 回退到API URL，传递配置以支持代理
                    playback_url = get_playback_url(song_id, use_api=True, config=self.config)

            # 获取封面URL
            cover_url = song_details.get('cover')

            self.logger.debug(f"NetEase音频信息: {title} - {artist}, 时长: {duration}秒, URL: {playback_url}")

            return AudioInfo(
                title=title,
                duration=duration,
                url=playback_url,
                uploader=artist,
                thumbnail_url=cover_url,
                file_format='mp3'
            )
            
        except Exception as e:
            self.logger.error(f"提取网易云音频信息时出错: {e}", exc_info=True)
            return None
    
    async def _download_audio_impl(
        self, 
        url: str, 
        progress_callback: Optional[ProgressCallback] = None
    ) -> Tuple[bool, Optional[AudioInfo], Optional[str]]:
        """
        下载网易云音乐音频文件
        
        Args:
            url: 网易云音乐URL
            progress_callback: 进度回调
            
        Returns:
            (成功标志, 音频信息, 错误消息)
        """
        progress_tracker = progress_callback
        
        try:
            if progress_tracker:
                await progress_tracker(ProgressInfo(
                    operation="netease_download",
                    status=ProgressStatus.IN_PROGRESS,
                    percentage=0.0,
                    message="正在获取歌曲信息..."
                ))
            
            # 提取音频信息
            audio_info = await self._extract_audio_info_impl(url)
            if not audio_info:
                return False, None, "无法获取歌曲信息"
            
            if progress_tracker:
                await progress_tracker(ProgressInfo(
                    operation="netease_download",
                    status=ProgressStatus.IN_PROGRESS,
                    percentage=20.0,
                    message="正在下载音频文件..."
                ))
            
            # 生成文件名
            song_id = self._extract_song_id(url)
            safe_title = re.sub(r'[^\w\s-]', '', audio_info.title)[:50]
            filename = f"netease_{song_id}_{safe_title}.mp3"
            file_path = os.path.join(self.temp_dir, filename)
            
            # 检查文件是否已存在
            if os.path.exists(file_path):
                self.logger.debug(f"使用已存在的文件: {filename}")
                audio_info.file_path = file_path
                audio_info.file_size = os.path.getsize(file_path)
                
                if progress_tracker:
                    await progress_tracker(ProgressInfo(
                        operation="netease_download",
                        status=ProgressStatus.COMPLETED,
                        percentage=100.0,
                        message="下载完成"
                    ))
                
                return True, audio_info, None
            
            # 下载音频文件
            success = await self._download_file(
                audio_info.url, 
                file_path, 
                progress_tracker
            )
            
            if not success:
                return False, None, "音频文件下载失败"
            
            # 更新音频信息
            audio_info.file_path = file_path
            if os.path.exists(file_path):
                audio_info.file_size = os.path.getsize(file_path)
            
            if progress_tracker:
                await progress_tracker(ProgressInfo(
                    operation="netease_download",
                    status=ProgressStatus.COMPLETED,
                    percentage=100.0,
                    message="下载完成"
                ))
            
            return True, audio_info, None
            
        except Exception as e:
            error_msg = f"下载网易云音频时出错: {e}"
            self.logger.error(error_msg, exc_info=True)
            return False, None, error_msg
    
    async def _download_file(
        self,
        url: str,
        file_path: str,
        progress_tracker: Optional[any] = None
    ) -> bool:
        """
        下载文件到指定路径

        Args:
            url: 下载URL（可能是API代理URL）
            file_path: 保存路径
            progress_tracker: 进度跟踪器

        Returns:
            下载是否成功
        """
        return await self._download_file_with_retry(url, file_path, progress_tracker, retry_count=0)

    async def _download_file_with_retry(
        self,
        url: str,
        file_path: str,
        progress_tracker: Optional[any] = None,
        retry_count: int = 0
    ) -> bool:
        """
        下载文件到指定路径，支持URL过期重试

        Args:
            url: 下载URL（可能是API代理URL）
            file_path: 保存路径
            progress_tracker: 进度跟踪器
            retry_count: 当前重试次数

        Returns:
            下载是否成功
        """
        max_retries = 1  # 最多重试1次（总共尝试2次）

        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            # 设置请求头，模拟浏览器请求
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'audio/mpeg, audio/*, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Referer': 'https://music.163.com/',
            }

            # 处理代理URL和请求头
            download_url, proxy_headers = self.proxy_manager.process_url_and_headers(url, headers)

            self.logger.debug(f"开始下载NetEase音频: {download_url}")

            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                # 处理可能的重定向
                async with session.get(download_url, headers=proxy_headers, allow_redirects=True) as response:
                    if response.status == 403:
                        # 检查是否是URL过期错误
                        auth_msg = response.headers.get('X-AUTH-MSG', '').lower()
                        if 'expired url' in auth_msg or 'auth failed' in auth_msg:
                            self.logger.warning(f"检测到URL过期错误: {auth_msg}")

                            # 如果还有重试机会，尝试刷新URL
                            if retry_count < max_retries:
                                fresh_url = await self._refresh_expired_url(url)
                                if fresh_url and fresh_url != url:
                                    self.logger.info(f"URL刷新成功，重试下载 (第{retry_count + 1}次)")
                                    return await self._download_file_with_retry(
                                        fresh_url, file_path, progress_tracker, retry_count + 1
                                    )
                                else:
                                    self.logger.warning("URL刷新失败，无法获取新的下载链接")
                            else:
                                self.logger.error(f"已达到最大重试次数({max_retries})，放弃下载")

                        self.logger.error(f"NetEase音频下载请求失败，状态码: {response.status}")
                        self.logger.debug(f"响应头: {dict(response.headers)}")
                        return False

                    if response.status != 200:
                        self.logger.error(f"NetEase音频下载请求失败，状态码: {response.status}")
                        self.logger.debug(f"响应头: {dict(response.headers)}")
                        return False

                    # 检查内容类型
                    content_type = response.headers.get('content-type', '').lower()
                    self.logger.debug(f"响应内容类型: {content_type}")

                    # 验证是否为音频内容
                    if not any(audio_type in content_type for audio_type in ['audio/', 'application/octet-stream', 'binary/octet-stream']):
                        # 如果不是音频内容，可能是HTML错误页面或其他内容
                        response_text = await response.text()
                        self.logger.warning(f"响应不是音频内容，内容类型: {content_type}")
                        self.logger.debug(f"响应内容（前500字符）: {response_text[:500]}")

                        # 如果是API代理URL返回的错误，尝试使用直接URL
                        if 'api.paugram.com' in url or 'netease' in url:
                            self.logger.info("API代理URL失败，尝试使用直接URL")
                            # 提取歌曲ID并尝试直接URL
                            song_id = self._extract_song_id_from_api_url(url)
                            if song_id:
                                from similubot.utils.netease_search import get_playback_url
                                direct_url = get_playback_url(song_id, use_api=False, config=self.config)
                                self.logger.debug(f"尝试直接URL: {direct_url}")
                                return await self._download_file_with_retry(direct_url, file_path, progress_tracker, retry_count)

                        return False

                    total_size = int(response.headers.get('content-length', 0))
                    downloaded = 0

                    self.logger.debug(f"开始下载音频文件，大小: {total_size} 字节")

                    with open(file_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)
                            downloaded += len(chunk)

                            # 更新进度
                            if progress_tracker and total_size > 0:
                                progress = 20.0 + (downloaded / total_size) * 70.0
                                await progress_tracker(ProgressInfo(
                                    operation="netease_download",
                                    status=ProgressStatus.IN_PROGRESS,
                                    percentage=min(progress, 90.0),
                                    current_size=downloaded,
                                    total_size=total_size,
                                    message=f"下载中... {downloaded}/{total_size} 字节"
                                ))

            # 验证下载的文件
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                if file_size > 0:
                    self.logger.debug(f"NetEase音频文件下载完成: {file_path}, 大小: {file_size} 字节")
                    return True
                else:
                    self.logger.error(f"下载的文件为空: {file_path}")
                    os.remove(file_path)  # 删除空文件
                    return False
            else:
                self.logger.error(f"下载完成但文件不存在: {file_path}")
                return False

        except Exception as e:
            self.logger.error(f"下载NetEase音频文件时出错: {e}", exc_info=True)
            # 清理可能的部分下载文件
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass
            return False

    async def _refresh_expired_url(self, expired_url: str) -> Optional[str]:
        """
        刷新过期的下载URL

        当检测到URL过期时，使用歌曲ID重新生成新的下载链接

        Args:
            expired_url: 过期的下载URL

        Returns:
            新的下载URL，如果刷新失败则返回None
        """
        try:
            self.logger.debug(f"开始刷新过期URL: {expired_url[:100]}...")

            # 1. 尝试从缓存中获取歌曲ID
            song_id = self._get_cached_song_id(expired_url)

            # 2. 如果缓存中没有，尝试从URL中提取
            if not song_id:
                song_id = self._extract_song_id_from_api_url(expired_url)

            if not song_id:
                self.logger.warning(f"无法从过期URL中提取歌曲ID: {expired_url}")
                return None

            self.logger.debug(f"从过期URL提取到歌曲ID: {song_id}")

            # 4. 尝试使用会员认证获取新的URL（如果启用）
            if self.member_auth.is_enabled():
                try:
                    fresh_member_url = await self.member_auth.get_member_audio_url(song_id)
                    if fresh_member_url:
                        self.logger.debug(f"使用会员认证刷新URL成功: {song_id}")
                        # 更新缓存映射
                        self._cache_url_song_id_mapping(fresh_member_url, song_id)
                        return fresh_member_url
                    else:
                        self.logger.debug(f"会员URL刷新失败，回退到免费模式: {song_id}")
                except Exception as e:
                    self.logger.warning(f"会员URL刷新时出错: {e}")

            # 5. 回退到免费模式URL生成
            from similubot.utils.netease_search import get_playback_url

            # 尝试API模式
            try:
                fresh_api_url = get_playback_url(song_id, use_api=True, config=self.config)
                if fresh_api_url and fresh_api_url != expired_url:
                    self.logger.debug(f"使用API模式刷新URL成功: {song_id}")
                    return fresh_api_url
            except Exception as e:
                self.logger.warning(f"API模式URL刷新时出错: {e}")

            # 尝试直接模式
            try:
                fresh_direct_url = get_playback_url(song_id, use_api=False, config=self.config)
                if fresh_direct_url and fresh_direct_url != expired_url:
                    self.logger.debug(f"使用直接模式刷新URL成功: {song_id}")
                    return fresh_direct_url
            except Exception as e:
                self.logger.warning(f"直接模式URL刷新时出错: {e}")

            self.logger.warning(f"所有URL刷新方法都失败: {song_id}")
            return None

        except Exception as e:
            self.logger.error(f"刷新过期URL时出错: {e}", exc_info=True)
            return None

    def _extract_song_id_from_api_url(self, api_url: str) -> Optional[str]:
        """
        从API代理URL中提取歌曲ID

        Args:
            api_url: API代理URL，如 https://api.paugram.com/netease/?id=123456

        Returns:
            歌曲ID，提取失败时返回None
        """
        try:
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(api_url)
            if parsed.query:
                query_params = parse_qs(parsed.query)
                if 'id' in query_params:
                    return query_params['id'][0]
            return None
        except Exception as e:
            self.logger.error(f"从API URL提取歌曲ID时出错: {e}")
            return None

    async def is_member_required(self, url: str) -> bool:
        """
        检查歌曲是否需要会员权限

        Args:
            url: 歌曲URL

        Returns:
            如果需要会员权限则返回True
        """
        if not self.member_auth.is_enabled():
            return False

        try:
            song_id = self._extract_song_id(url)
            if not song_id:
                return False

            # 检查歌曲是否对会员可用
            return await self.member_auth.is_song_available_for_member(song_id)
        except Exception as e:
            self.logger.warning(f"检查会员权限时出错: {e}")
            return False
