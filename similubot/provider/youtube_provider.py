"""
YouTube 音频提供者 - 处理 YouTube 视频的音频提取和下载

基于原有的 YouTubeClient 实现，重构为符合新架构的提供者模式。
"""

import os
import re
import asyncio
import time
from typing import Optional, Tuple
from pytubefix import YouTube
from pytubefix.exceptions import PytubeFixError

from .base import BaseAudioProvider
from similubot.core.interfaces import AudioInfo
from similubot.progress.base import ProgressCallback, ProgressTracker, ProgressInfo, ProgressStatus
from similubot.utils.config_manager import ConfigManager


class YouTubeProvider(BaseAudioProvider):
    """
    YouTube 音频提供者
    
    负责从 YouTube 视频中提取音频信息和下载音频文件。
    支持进度跟踪和配置管理。
    """
    
    # YouTube URL 正则表达式
    YOUTUBE_URL_PATTERNS = [
        r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]+)',
        r'(?:https?://)?(?:www\.)?youtu\.be/([a-zA-Z0-9_-]+)',
        r'(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]+)',
        r'(?:https?://)?(?:www\.)?youtube\.com/v/([a-zA-Z0-9_-]+)'
    ]
    
    def __init__(self, temp_dir: str = "./temp", config: Optional[ConfigManager] = None):
        """
        初始化 YouTube 提供者
        
        Args:
            temp_dir: 临时文件目录
            config: 配置管理器
        """
        super().__init__("YouTube", temp_dir)
        self.config = config
        
        # 创建临时目录
        os.makedirs(temp_dir, exist_ok=True)
        
        # 获取配置
        self.po_token = config.get('youtube.po_token') if config else None
        self.visitor_data = config.get('youtube.visitor_data') if config else None
        
        if self.po_token and self.visitor_data:
            self.logger.info("YouTube 配置已加载 (PoToken 和 VisitorData)")
        else:
            self.logger.warning("YouTube 配置未完整加载，可能影响某些视频的访问")
    
    def is_supported_url(self, url: str) -> bool:
        """
        检查URL是否为YouTube链接
        
        Args:
            url: 要检查的URL
            
        Returns:
            如果是YouTube链接则返回True
        """
        return any(re.search(pattern, url) for pattern in self.YOUTUBE_URL_PATTERNS)
    
    def _extract_video_id(self, url: str) -> Optional[str]:
        """从URL中提取视频ID"""
        for pattern in self.YOUTUBE_URL_PATTERNS:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def _create_youtube_object(self, url: str) -> YouTube:
        """创建YouTube对象，应用配置"""
        kwargs = {}
        
        if self.po_token and self.visitor_data:
            kwargs.update({
                'po_token': self.po_token,
                'visitor_data': self.visitor_data
            })
        
        return YouTube(url, **kwargs)
    
    async def _extract_audio_info_impl(self, url: str) -> Optional[AudioInfo]:
        """
        提取YouTube视频的音频信息
        
        Args:
            url: YouTube视频URL
            
        Returns:
            音频信息，失败时返回None
        """
        try:
            # 在线程池中执行，避免阻塞
            loop = asyncio.get_event_loop()
            yt = await loop.run_in_executor(None, self._create_youtube_object, url)
            
            # 获取视频信息
            title = yt.title or "Unknown Title"
            duration = yt.length or 0
            uploader = yt.author or "Unknown Uploader"
            thumbnail_url = yt.thumbnail_url
            
            return AudioInfo(
                title=title,
                duration=duration,
                url=url,
                uploader=uploader,
                thumbnail_url=thumbnail_url
            )
            
        except PytubeFixError as e:
            self.logger.error(f"PytubeFixError: {e}")
            return None
        except Exception as e:
            self.logger.error(f"提取YouTube音频信息时发生未知错误: {e}")
            return None
    
    async def _download_audio_impl(self, url: str, progress_callback: Optional[ProgressCallback] = None) -> Tuple[bool, Optional[AudioInfo], Optional[str]]:
        """
        下载YouTube视频的音频
        
        Args:
            url: YouTube视频URL
            progress_callback: 进度回调
            
        Returns:
            (成功标志, 音频信息, 错误消息)
        """
        progress_tracker = ProgressTracker(progress_callback) if progress_callback else None
        
        try:
            if progress_tracker:
                await progress_tracker.update(ProgressInfo(
                    status=ProgressStatus.DOWNLOADING,
                    message="正在获取视频信息...",
                    progress=0.0
                ))
            
            # 创建YouTube对象
            loop = asyncio.get_event_loop()
            yt = await loop.run_in_executor(None, self._create_youtube_object, url)
            
            # 获取音频流
            audio_stream = yt.streams.filter(only_audio=True, file_extension='mp4').first()
            if not audio_stream:
                return False, None, "未找到可用的音频流"
            
            if progress_tracker:
                await progress_tracker.update(ProgressInfo(
                    status=ProgressStatus.DOWNLOADING,
                    message="正在下载音频文件...",
                    progress=0.1
                ))
            
            # 生成文件名
            video_id = self._extract_video_id(url)
            safe_title = re.sub(r'[^\w\s-]', '', yt.title or 'unknown')[:50]
            filename = f"youtube_{video_id}_{safe_title}.mp4"
            file_path = os.path.join(self.temp_dir, filename)
            
            # 下载文件
            def download_with_progress():
                def on_progress(stream, chunk, bytes_remaining):
                    if progress_tracker:
                        total_size = stream.filesize
                        downloaded = total_size - bytes_remaining
                        progress = min(0.9, 0.1 + (downloaded / total_size) * 0.8)
                        
                        # 异步更新进度
                        asyncio.create_task(progress_tracker.update(ProgressInfo(
                            status=ProgressStatus.DOWNLOADING,
                            message=f"下载中... {downloaded}/{total_size} 字节",
                            progress=progress
                        )))
                
                yt.register_on_progress_callback(on_progress)
                return audio_stream.download(output_path=self.temp_dir, filename=filename)
            
            downloaded_path = await loop.run_in_executor(None, download_with_progress)
            
            if progress_tracker:
                await progress_tracker.update(ProgressInfo(
                    status=ProgressStatus.COMPLETED,
                    message="下载完成",
                    progress=1.0
                ))
            
            # 创建音频信息
            audio_info = AudioInfo(
                title=yt.title or "Unknown Title",
                duration=yt.length or 0,
                url=url,
                uploader=yt.author or "Unknown Uploader",
                file_path=downloaded_path,
                thumbnail_url=yt.thumbnail_url,
                file_size=os.path.getsize(downloaded_path) if os.path.exists(downloaded_path) else None,
                file_format="mp4"
            )
            
            return True, audio_info, None
            
        except PytubeFixError as e:
            error_msg = f"PytubeFixError: {e}"
            if progress_tracker:
                await progress_tracker.update(ProgressInfo(
                    status=ProgressStatus.ERROR,
                    message=error_msg,
                    progress=0.0
                ))
            return False, None, error_msg
            
        except Exception as e:
            error_msg = f"下载YouTube音频时发生未知错误: {e}"
            if progress_tracker:
                await progress_tracker.update(ProgressInfo(
                    status=ProgressStatus.ERROR,
                    message=error_msg,
                    progress=0.0
                ))
            return False, None, error_msg

    def cleanup_temp_files(self, max_age_hours: int = 24) -> int:
        """
        清理临时文件

        Args:
            max_age_hours: 文件最大保留时间（小时）

        Returns:
            清理的文件数量
        """
        try:
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600
            cleaned_count = 0

            for filename in os.listdir(self.temp_dir):
                if filename.startswith("youtube_") and filename.endswith(".mp4"):
                    file_path = os.path.join(self.temp_dir, filename)
                    try:
                        file_age = current_time - os.path.getmtime(file_path)
                        if file_age > max_age_seconds:
                            os.remove(file_path)
                            cleaned_count += 1
                            self.logger.debug(f"清理过期文件: {filename}")
                    except Exception as e:
                        self.logger.warning(f"清理文件失败 - {filename}: {e}")

            if cleaned_count > 0:
                self.logger.info(f"清理了 {cleaned_count} 个过期的YouTube音频文件")

            return cleaned_count

        except Exception as e:
            self.logger.error(f"清理临时文件时发生错误: {e}")
            return 0
