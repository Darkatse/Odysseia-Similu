"""
Catbox 音频提供者 - 处理 Catbox 音频文件的验证和信息提取

基于原有的 CatboxClient 实现，重构为符合新架构的提供者模式。
"""

import os
import re
import asyncio
import aiohttp
from typing import Optional, Tuple
from urllib.parse import urlparse

from .base import BaseAudioProvider
from similubot.core.interfaces import AudioInfo
from similubot.progress.base import ProgressCallback, ProgressTracker, ProgressInfo, ProgressStatus


class CatboxProvider(BaseAudioProvider):
    """
    Catbox 音频提供者
    
    负责验证 Catbox 音频文件的可访问性和提取基本信息。
    Catbox 文件通常直接流式播放，不需要下载到本地。
    """
    
    # Catbox URL 正则表达式 - 支持 catbox.moe 和 files.catbox.moe
    CATBOX_URL_PATTERN = r'https?://(?:(?:www\.|files\.)?catbox\.moe)/[a-zA-Z0-9]+\.[a-zA-Z0-9]+'
    
    # 支持的音频格式
    SUPPORTED_AUDIO_FORMATS = {
        'mp3', 'wav', 'ogg', 'flac', 'm4a', 'aac', 'wma'
    }
    
    def __init__(self, temp_dir: str = "./temp"):
        """
        初始化 Catbox 提供者
        
        Args:
            temp_dir: 临时文件目录（Catbox通常不需要）
        """
        super().__init__("Catbox", temp_dir)
        
        # HTTP 会话配置
        self.session_timeout = aiohttp.ClientTimeout(total=30)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    def is_supported_url(self, url: str) -> bool:
        """
        检查URL是否为Catbox音频链接
        
        Args:
            url: 要检查的URL
            
        Returns:
            如果是Catbox音频链接则返回True
        """
        if not re.match(self.CATBOX_URL_PATTERN, url):
            return False
        
        # 检查文件扩展名
        parsed_url = urlparse(url)
        file_extension = parsed_url.path.split('.')[-1].lower()
        return file_extension in self.SUPPORTED_AUDIO_FORMATS
    
    def _extract_filename_from_url(self, url: str) -> str:
        """从URL中提取文件名"""
        parsed_url = urlparse(url)
        return os.path.basename(parsed_url.path) or "unknown_audio"
    
    def _extract_title_from_filename(self, filename: str) -> str:
        """从文件名提取标题"""
        # 移除扩展名并清理文件名
        title = os.path.splitext(filename)[0]
        # 替换下划线和连字符为空格
        title = re.sub(r'[_-]', ' ', title)
        # 清理多余空格
        title = re.sub(r'\s+', ' ', title).strip()
        return title or "Unknown Audio"
    
    async def _get_file_info_from_headers(self, url: str) -> Tuple[Optional[int], Optional[str]]:
        """
        通过HTTP HEAD请求获取文件信息
        
        Args:
            url: Catbox文件URL
            
        Returns:
            (文件大小, 内容类型)
        """
        try:
            async with aiohttp.ClientSession(timeout=self.session_timeout, headers=self.headers) as session:
                async with session.head(url) as response:
                    if response.status == 200:
                        content_length = response.headers.get('Content-Length')
                        content_type = response.headers.get('Content-Type')
                        
                        file_size = int(content_length) if content_length else None
                        return file_size, content_type
                    else:
                        self.logger.warning(f"Catbox文件HEAD请求失败 - 状态码: {response.status}")
                        return None, None
                        
        except Exception as e:
            self.logger.error(f"获取Catbox文件信息失败: {e}")
            return None, None
    
    async def _extract_audio_info_impl(self, url: str) -> Optional[AudioInfo]:
        """
        提取Catbox音频文件的信息
        
        Args:
            url: Catbox音频文件URL
            
        Returns:
            音频信息，失败时返回None
        """
        try:
            # 验证URL可访问性
            file_size, content_type = await self._get_file_info_from_headers(url)
            
            if file_size is None:
                self.logger.warning(f"无法访问Catbox文件: {url}")
                return None
            
            # 从URL提取基本信息
            filename = self._extract_filename_from_url(url)
            title = self._extract_title_from_filename(filename)
            file_extension = filename.split('.')[-1].lower()
            
            # 估算音频时长（基于文件大小的粗略估算）
            # 这是一个近似值，实际时长可能不同
            estimated_duration = self._estimate_duration_from_size(file_size, file_extension)
            
            return AudioInfo(
                title=title,
                duration=estimated_duration,
                url=url,
                uploader="Catbox",
                file_path=url,  # Catbox文件直接使用URL作为文件路径
                file_size=file_size,
                file_format=file_extension
            )
            
        except Exception as e:
            self.logger.error(f"提取Catbox音频信息时发生错误: {e}")
            return None
    
    def _estimate_duration_from_size(self, file_size: int, file_format: str) -> int:
        """
        根据文件大小估算音频时长
        
        Args:
            file_size: 文件大小（字节）
            file_format: 文件格式
            
        Returns:
            估算的时长（秒）
        """
        # 不同格式的平均比特率估算（kbps）
        bitrate_estimates = {
            'mp3': 128,
            'wav': 1411,  # CD质量
            'ogg': 128,
            'flac': 1000,
            'm4a': 128,
            'aac': 128,
            'wma': 128
        }
        
        estimated_bitrate = bitrate_estimates.get(file_format.lower(), 128)
        
        # 计算估算时长：文件大小(字节) / (比特率(kbps) * 1000 / 8)
        estimated_seconds = (file_size * 8) / (estimated_bitrate * 1000)
        
        return max(1, int(estimated_seconds))  # 至少1秒
    
    async def _download_audio_impl(self, url: str, progress_callback: Optional[ProgressCallback] = None) -> Tuple[bool, Optional[AudioInfo], Optional[str]]:
        """
        验证Catbox音频文件（不实际下载）
        
        Catbox文件通常直接流式播放，这里主要是验证文件的可访问性。
        
        Args:
            url: Catbox音频文件URL
            progress_callback: 进度回调
            
        Returns:
            (成功标志, 音频信息, 错误消息)
        """
        progress_tracker = ProgressTracker(progress_callback) if progress_callback else None
        
        try:
            if progress_tracker:
                await progress_tracker.update(ProgressInfo(
                    status=ProgressStatus.DOWNLOADING,
                    message="正在验证Catbox音频文件...",
                    progress=0.0
                ))
            
            # 获取音频信息（同时验证可访问性）
            audio_info = await self._extract_audio_info_impl(url)
            
            if not audio_info:
                error_msg = "无法访问或验证Catbox音频文件"
                if progress_tracker:
                    await progress_tracker.update(ProgressInfo(
                        status=ProgressStatus.ERROR,
                        message=error_msg,
                        progress=0.0
                    ))
                return False, None, error_msg
            
            if progress_tracker:
                await progress_tracker.update(ProgressInfo(
                    status=ProgressStatus.COMPLETED,
                    message="Catbox音频文件验证完成",
                    progress=1.0
                ))
            
            return True, audio_info, None
            
        except Exception as e:
            error_msg = f"验证Catbox音频文件时发生错误: {e}"
            if progress_tracker:
                await progress_tracker.update(ProgressInfo(
                    status=ProgressStatus.ERROR,
                    message=error_msg,
                    progress=0.0
                ))
            return False, None, error_msg
    
    async def validate_audio_file(self, url: str, progress_callback: Optional[ProgressCallback] = None) -> Tuple[bool, Optional[AudioInfo], Optional[str]]:
        """
        验证音频文件（兼容性方法）
        
        这是为了保持与原有代码的兼容性。
        """
        return await self.download_audio(url, progress_callback)
