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
from typing import Optional, Tuple
from urllib.parse import urlparse, parse_qs

from similubot.core.interfaces import AudioInfo
from similubot.progress.base import ProgressCallback, ProgressInfo, ProgressStatus
from similubot.utils.netease_search import get_song_details, get_playback_url
from similubot.utils.netease_proxy import get_proxy_manager
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
        ]

        # 编译正则表达式
        self.compiled_patterns = [re.compile(pattern) for pattern in self.url_patterns]

        # 会话超时
        self.timeout = aiohttp.ClientTimeout(total=30)

        # 初始化代理管理器
        self.proxy_manager = get_proxy_manager(config)

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
            # 尝试所有模式
            for pattern in self.compiled_patterns:
                match = pattern.search(url)
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
                                return await self._download_file(direct_url, file_path, progress_tracker)

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
