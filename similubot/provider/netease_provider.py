"""
网易云音乐提供者 - 重构版本

核心改进：
1. AudioInfo.url 存储规范化URL（包含歌曲ID），而不是临时播放链接
2. 新增 resolve_playable_url 方法，在播放前将规范化URL转换为可播放直链
3. 职责分离：信息提取与播放链接获取完全分开
4. 使用 NetEaseApiClient 封装所有API调用
5. 简化代码架构，移除复杂的缓存和重试逻辑
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
from similubot.utils.netease_api_client import NetEaseApiClient
from similubot.utils.config_manager import ConfigManager
from .base import BaseAudioProvider


class NetEaseProvider(BaseAudioProvider):
    """
    网易云音乐音频提供者 - 重构版本
    
    主要职责：
    1. 识别网易云音乐URL
    2. 提取音频元数据并生成规范化URL
    3. 在播放前解析规范化URL为可播放直链
    4. 下载音频文件
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
        
        # 初始化API客户端
        self.api_client = NetEaseApiClient(config)
        
        # 支持的URL模式
        self.url_patterns = [
            # 官方网易云音乐URL（包含歌曲ID）
            r'music\.163\.com/song\?id=(\d+)',
            r'music\.163\.com/#/song\?id=(\d+)',
            r'music\.163\.com/m/song\?id=(\d+)',
            r'y\.music\.163\.com/m/song\?id=(\d+)',
            r'music\.163\.com/song/media/outer/url\?id=(\d+)',
            r'api\.paugram\.com/netease/\?id=(\d+)',
            # 直接音频URL（会员音频链接，不包含歌曲ID）
            r'[a-z0-9]+\.music\.126\.net/.+\.(mp3|flac|m4a|aac)',
            r'music\.126\.net/.+\.(mp3|flac|m4a|aac)',
        ]
        
        # 编译正则表达式
        self.compiled_patterns = [re.compile(pattern) for pattern in self.url_patterns]
        
        # 会话超时
        self.timeout = aiohttp.ClientTimeout(total=30)
        
        self.logger.debug("网易云音乐提供者初始化完成（重构版本）")
    
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
        return self.api_client.extract_song_id_from_url(url)
    
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
    
    async def _extract_audio_info_impl(self, url: str) -> Optional[AudioInfo]:
        """
        从网易云音乐URL提取音频信息，并返回包含规范化URL的AudioInfo
        
        这是核心重构：AudioInfo.url 存储规范化URL，而不是临时播放链接
        
        Args:
            url: 网易云音乐URL
            
        Returns:
            音频信息，失败时返回None
        """
        try:
            self.logger.debug(f"开始提取网易云音频信息: {url}")
            
            # 1. 提取歌曲ID
            song_id = self._extract_song_id(url)
            if not song_id:
                # 对于无法提取ID的直链，这是一个降级处理，信息会不完整且无法重播
                if self._is_direct_audio_url(url):
                    return await self._extract_audio_info_from_direct_url(url)
                self.logger.warning(f"无法从URL中提取到 song_id: {url}")
                return None
            
            # 2. 获取歌曲元数据
            metadata = await self.api_client.get_song_metadata(song_id)
            if not metadata:
                self.logger.warning(f"无法获取歌曲元数据: {song_id}")
                return None
            
            # 3. 构建规范化URL（关键改动：存储包含ID的永久URL）
            canonical_url = f"https://music.163.com/song?id={song_id}"
            
            # 4. 创建并返回AudioInfo对象
            # 注意：这里的 url 字段存储的是 canonical_url，而不是临时的播放链接！
            audio_info = AudioInfo(
                title=metadata['title'],
                uploader=metadata['artist'],
                duration=metadata['duration'],
                url=canonical_url,  # <--- 关键改动：存储规范化URL
                thumbnail_url=metadata.get('cover_url'),
                file_format='mp3'  # 或根据实际情况设定
            )
            
            self.logger.debug(f"提取信息成功，规范化URL: {canonical_url}")
            self.logger.info(f"网易云音频信息提取成功: {metadata['title']} - {metadata['artist']} ({metadata['duration']}s)")
            return audio_info
            
        except Exception as e:
            self.logger.error(f"提取网易云音频信息时出错: {e}", exc_info=True)
            return None
    
    async def resolve_playable_url(self, canonical_url: str) -> Optional[str]:
        """
        将规范化的URL解析为当前可播放的音频直链
        这是播放前的最后一步
        
        Args:
            canonical_url: 规范化URL（如 https://music.163.com/song?id=123456）
            
        Returns:
            可播放的音频直链，解析失败时返回None
        """
        try:
            song_id = self._extract_song_id(canonical_url)
            if not song_id:
                self.logger.error(f"无法从规范化URL中解析song_id: {canonical_url}")
                return None
            
            self.logger.debug(f"开始为 song_id={song_id} 解析可播放链接...")
            
            # 使用API客户端获取播放链接
            playback_url = await self.api_client.fetch_playback_url(song_id)
            
            if playback_url:
                self.logger.debug(f"成功解析可播放链接: {song_id}")
                return playback_url
            else:
                self.logger.error(f"无法解析可播放链接: {song_id}")
                return None
                
        except Exception as e:
            self.logger.error(f"解析可播放URL时出错: {e}", exc_info=True)
            return None
    
    async def _extract_audio_info_from_direct_url(self, url: str) -> Optional[AudioInfo]:
        """
        从直接音频URL提取音频信息（降级处理）
        
        这种情况下无法获取歌曲ID，信息会不完整且无法重播
        
        Args:
            url: 直接音频URL
            
        Returns:
            音频信息，失败时返回None
        """
        try:
            self.logger.warning(f"处理直接音频URL（降级模式）: {url}")
            
            # 从文件路径提取基本信息
            parsed = urlparse(url)
            path_parts = parsed.path.split('/')
            filename = path_parts[-1] if path_parts else "unknown"
            title = os.path.splitext(filename)[0]
            
            # 如果标题是哈希值或无意义字符串，使用默认值
            if len(title) > 32 or not any(c.isalpha() for c in title):
                title = "网易云音乐会员音频"
            
            # 创建音频信息对象（注意：这里直接使用原始URL，因为无法生成规范化URL）
            audio_info = AudioInfo(
                title=title,
                uploader="网易云音乐",
                duration=0,  # 无法获取准确时长
                url=url,  # 直接使用原始URL
                thumbnail_url=None,
                file_format='mp3'
            )
            
            self.logger.debug(f"从直接URL提取音频信息成功（降级模式）: {title}")
            return audio_info
            
        except Exception as e:
            self.logger.error(f"从直接URL提取音频信息失败: {e}")
            return None
    
    async def _download_audio_impl(
        self,
        url: str,
        progress_callback: Optional[ProgressCallback] = None
    ) -> Tuple[bool, Optional[AudioInfo], Optional[str]]:
        """
        下载网易云音乐音频文件

        下载流程被简化：
        1. 先获取包含元数据和规范化URL的AudioInfo
        2. 解析出真正的可下载URL
        3. 下载文件（不再需要处理URL过期）

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

            # 1. 先获取包含元数据和规范化URL的AudioInfo
            audio_info = await self.extract_audio_info(url)
            if not audio_info:
                return False, None, "无法获取歌曲信息"

            if progress_tracker:
                await progress_tracker(ProgressInfo(
                    operation="netease_download",
                    status=ProgressStatus.IN_PROGRESS,
                    percentage=20.0,
                    message="正在解析下载链接..."
                ))

            # 2. 解析出真正的可下载URL
            download_url = await self.resolve_playable_url(audio_info.url)
            if not download_url:
                return False, audio_info, "无法解析下载链接"

            if progress_tracker:
                await progress_tracker(ProgressInfo(
                    operation="netease_download",
                    status=ProgressStatus.IN_PROGRESS,
                    percentage=30.0,
                    message="开始下载音频文件..."
                ))

            # 3. 生成文件名
            song_id = self._extract_song_id(audio_info.url)  # 从规范化URL提取ID
            safe_title = re.sub(r'[^\w\s-]', '', audio_info.title)[:50]
            filename = f"netease_{song_id}_{safe_title}.mp3"
            file_path = os.path.join(self.temp_dir, filename)

            # 4. 检查文件是否已存在
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

            # 5. 下载音频文件（使用解析出的下载URL）
            success = await self._download_file(
                download_url,
                file_path,
                progress_tracker
            )

            if not success:
                return False, audio_info, "音频文件下载失败"

            # 6. 更新音频信息
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

            self.logger.info(f"网易云音频下载成功: {audio_info.title}")
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

        简化版本：不再需要处理URL过期重试，因为每次都是实时解析的新URL

        Args:
            url: 下载URL（实时解析的可播放直链）
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
            download_url, proxy_headers = self.api_client.proxy_manager.process_url_and_headers(url, headers)

            self.logger.debug(f"开始下载NetEase音频: {download_url}")

            async with aiohttp.ClientSession(timeout=self.timeout) as session:
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
                        response_text = await response.text()
                        self.logger.warning(f"响应不是音频内容，内容类型: {content_type}")
                        self.logger.debug(f"响应内容（前500字符）: {response_text[:500]}")
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
                                progress = 30.0 + (downloaded / total_size) * 60.0
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

    async def is_member_required(self, url: str) -> bool:
        """
        检查歌曲是否需要会员权限

        Args:
            url: 歌曲URL

        Returns:
            如果需要会员权限则返回True
        """
        try:
            song_id = self._extract_song_id(url)
            if not song_id:
                return False

            return await self.api_client.is_song_available_for_member(song_id)
        except Exception as e:
            self.logger.warning(f"检查会员权限时出错: {e}")
            return False
