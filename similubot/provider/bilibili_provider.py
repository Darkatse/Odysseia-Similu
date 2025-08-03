"""
Bilibili 音频提供者 - 处理 Bilibili 视频的音频提取和下载

支持 Bilibili 视频链接的音频提取，使用 bilibili-api-python 库进行视频信息获取和音频流下载。
遵循项目的领域驱动设计原则，提供完整的错误处理和日志记录。
"""

import os
import re
import asyncio
import logging
from typing import Optional, Tuple
from urllib.parse import urlparse, parse_qs

from similubot.core.interfaces import AudioInfo
from similubot.progress.base import ProgressCallback, ProgressInfo, ProgressStatus
from .base import BaseAudioProvider

try:
    from bilibili_api import video as bilibili_video
    from bilibili_api.video import VideoDownloadURLDataDetecter, AudioStreamDownloadURL
    BILIBILI_API_AVAILABLE = True
except ImportError:
    BILIBILI_API_AVAILABLE = False


class BilibiliProvider(BaseAudioProvider):
    """
    Bilibili 音频提供者
    
    负责处理 Bilibili 视频链接的音频信息提取和下载。
    支持标准的 BV 号和 AV 号格式的 Bilibili 视频链接。
    """
    
    # Bilibili URL 匹配模式
    BILIBILI_URL_PATTERNS = [
        r'https?://(?:www\.)?bilibili\.com/video/(BV[a-zA-Z0-9]{10})',
        r'https?://(?:www\.)?bilibili\.com/video/(av\d+)',
        r'https?://(?:b23\.tv|bili2233\.cn)/([a-zA-Z0-9]+)',  # 短链接
    ]
    
    def __init__(self, temp_dir: str = "./temp"):
        """
        初始化 Bilibili 提供者
        
        Args:
            temp_dir: 临时文件目录
        """
        super().__init__("Bilibili", temp_dir)
        
        # 检查 bilibili-api-python 是否可用
        if not BILIBILI_API_AVAILABLE:
            self.logger.error("bilibili-api-python 库未安装，Bilibili 提供者将无法工作")
            raise ImportError("请安装 bilibili-api-python: pip install bilibili-api-python")
        
        # 创建临时目录
        os.makedirs(temp_dir, exist_ok=True)
        
        self.logger.info("Bilibili 音频提供者初始化完成")
    
    def is_supported_url(self, url: str) -> bool:
        """
        检查 URL 是否为 Bilibili 链接
        
        Args:
            url: 要检查的 URL
            
        Returns:
            如果是 Bilibili 链接则返回 True
        """
        return any(re.search(pattern, url) for pattern in self.BILIBILI_URL_PATTERNS)
    
    def _extract_video_id(self, url: str) -> Optional[str]:
        """
        从 URL 中提取视频 ID (BV号或AV号)
        
        Args:
            url: Bilibili 视频 URL
            
        Returns:
            视频 ID，提取失败时返回 None
        """
        for pattern in self.BILIBILI_URL_PATTERNS:
            match = re.search(pattern, url)
            if match:
                video_id = match.group(1)
                
                # 处理短链接的情况，需要进一步解析
                if 'b23.tv' in url or 'bili2233.cn' in url:
                    # 短链接需要重定向解析，这里简化处理
                    # 实际应用中可能需要发送 HTTP 请求获取重定向后的真实 URL
                    self.logger.warning(f"检测到短链接，可能需要手动解析: {url}")
                    return None
                
                return video_id
        
        return None
    
    def _create_bilibili_video_object(self, video_id: str) -> 'bilibili_video.Video':
        """
        创建 Bilibili Video 对象
        
        Args:
            video_id: 视频 ID (BV号或AV号)
            
        Returns:
            Bilibili Video 对象
        """
        try:
            if video_id.startswith('BV'):
                return bilibili_video.Video(bvid=video_id)
            elif video_id.startswith('av'):
                aid = int(video_id[2:])  # 移除 'av' 前缀
                return bilibili_video.Video(aid=aid)
            else:
                raise ValueError(f"不支持的视频 ID 格式: {video_id}")
        except Exception as e:
            self.logger.error(f"创建 Bilibili Video 对象失败: {e}")
            raise
    
    async def _extract_audio_info_impl(self, url: str) -> Optional[AudioInfo]:
        """
        提取 Bilibili 视频的音频信息
        
        Args:
            url: Bilibili 视频 URL
            
        Returns:
            音频信息，失败时返回 None
        """
        try:
            # 提取视频 ID
            video_id = self._extract_video_id(url)
            if not video_id:
                self.logger.error(f"无法从 URL 中提取视频 ID: {url}")
                return None
            
            # 创建 Bilibili Video 对象
            video = self._create_bilibili_video_object(video_id)
            
            # 在线程池中执行，避免阻塞
            loop = asyncio.get_event_loop()
            video_info = await loop.run_in_executor(None, lambda: asyncio.run(video.get_info()))
            
            # 提取基本信息
            title = video_info.get('title', 'Unknown Title')
            duration = video_info.get('duration', 0)
            uploader = video_info.get('owner', {}).get('name', 'Unknown Uploader')
            thumbnail_url = video_info.get('pic', '')
            
            self.logger.debug(f"成功获取 Bilibili 视频信息: {title} - {uploader}")
            
            return AudioInfo(
                title=title,
                duration=duration,
                url=url,
                uploader=uploader,
                thumbnail_url=thumbnail_url
            )
            
        except Exception as e:
            self.logger.error(f"提取 Bilibili 音频信息时发生错误: {e}")
            return None
    
    async def _download_audio_impl(self, url: str, progress_callback: Optional[ProgressCallback] = None) -> Tuple[bool, Optional[AudioInfo], Optional[str]]:
        """
        下载 Bilibili 视频的音频文件
        
        Args:
            url: Bilibili 视频 URL
            progress_callback: 进度回调
            
        Returns:
            (成功标志, 音频信息, 错误消息)
        """
        progress_tracker = progress_callback
        
        try:
            if progress_tracker:
                await progress_tracker.update(ProgressInfo(
                    operation="bilibili_download",
                    status=ProgressStatus.IN_PROGRESS,
                    percentage=0.0,
                    message="正在获取 Bilibili 视频信息..."
                ))
            
            # 提取视频 ID
            video_id = self._extract_video_id(url)
            if not video_id:
                return False, None, f"无法从 URL 中提取视频 ID: {url}"
            
            # 创建 Bilibili Video 对象
            video = self._create_bilibili_video_object(video_id)
            
            # 获取视频信息
            loop = asyncio.get_event_loop()
            video_info = await loop.run_in_executor(None, lambda: asyncio.run(video.get_info()))
            
            if progress_tracker:
                await progress_tracker.update(ProgressInfo(
                    operation="bilibili_download",
                    status=ProgressStatus.IN_PROGRESS,
                    percentage=20.0,
                    message="正在获取音频下载链接..."
                ))
            
            # 获取下载链接 (默认使用第一个分P，page_index=0)
            download_data = await loop.run_in_executor(None, lambda: asyncio.run(video.get_download_url(page_index=0)))
            
            # 解析下载数据
            detector = VideoDownloadURLDataDetecter(download_data)
            
            if not detector.check_video_and_audio_stream():
                return False, None, "该视频不支持音视频分离下载"
            
            # 获取最佳音频流
            streams = detector.detect_best_streams()
            audio_stream = None
            
            for stream in streams:
                if isinstance(stream, AudioStreamDownloadURL):
                    audio_stream = stream
                    break
            
            if not audio_stream:
                return False, None, "未找到可用的音频流"
            
            if progress_tracker:
                await progress_tracker.update(ProgressInfo(
                    operation="bilibili_download",
                    status=ProgressStatus.IN_PROGRESS,
                    percentage=40.0,
                    message="正在下载音频文件..."
                ))
            
            # 生成文件名
            title = video_info.get('title', 'unknown')
            safe_title = re.sub(r'[^\w\s-]', '', title)[:50]
            filename = f"bilibili_{video_id}_{safe_title}.mp3"
            file_path = os.path.join(self.temp_dir, filename)
            
            # 下载音频文件
            success = await self._download_audio_stream(audio_stream.url, file_path, progress_tracker)
            
            if not success:
                return False, None, "音频文件下载失败"
            
            # 创建音频信息对象
            audio_info = AudioInfo(
                title=video_info.get('title', 'Unknown Title'),
                duration=video_info.get('duration', 0),
                url=url,
                uploader=video_info.get('owner', {}).get('name', 'Unknown Uploader'),
                thumbnail_url=video_info.get('pic', ''),
                file_path=file_path,
                file_size=os.path.getsize(file_path) if os.path.exists(file_path) else None,
                file_format='mp3'
            )
            
            if progress_tracker:
                await progress_tracker.update(ProgressInfo(
                    operation="bilibili_download",
                    status=ProgressStatus.COMPLETED,
                    percentage=100.0,
                    message="Bilibili 音频下载完成"
                ))
            
            return True, audio_info, None
            
        except Exception as e:
            error_msg = f"下载 Bilibili 音频时发生错误: {str(e)}"
            self.logger.error(error_msg)
            return False, None, error_msg

    async def _download_audio_stream(self, stream_url: str, file_path: str, progress_tracker: Optional[ProgressCallback] = None) -> bool:
        """
        下载音频流到指定文件

        Args:
            stream_url: 音频流 URL
            file_path: 保存文件路径
            progress_tracker: 进度跟踪器

        Returns:
            下载是否成功
        """
        try:
            import aiohttp

            # 设置请求头，模拟浏览器请求
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Referer': 'https://www.bilibili.com/'
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(stream_url, headers=headers) as response:
                    if response.status != 200:
                        self.logger.error(f"音频流请求失败，状态码: {response.status}")
                        return False

                    total_size = int(response.headers.get('content-length', 0))
                    downloaded = 0

                    with open(file_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)
                            downloaded += len(chunk)

                            # 更新进度
                            if progress_tracker and total_size > 0:
                                progress_percent = 40.0 + (downloaded / total_size) * 50.0  # 40%-90% 的进度范围
                                await progress_tracker.update(ProgressInfo(
                                    operation="bilibili_download",
                                    status=ProgressStatus.IN_PROGRESS,
                                    percentage=progress_percent,
                                    message=f"下载中... {downloaded}/{total_size} 字节"
                                ))

            self.logger.debug(f"音频流下载完成: {file_path}")
            return True

        except Exception as e:
            self.logger.error(f"下载音频流时发生错误: {e}")
            if os.path.exists(file_path):
                os.remove(file_path)  # 清理不完整的文件
            return False
