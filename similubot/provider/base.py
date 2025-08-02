"""
音频提供者基类 - 定义音频提供者的通用功能

提供音频提供者的基础实现，包含通用的错误处理和日志记录。
"""

import logging
from abc import ABC
from typing import Optional, Tuple
from similubot.core.interfaces import IAudioProvider, AudioInfo
from similubot.progress.base import ProgressCallback


class BaseAudioProvider(IAudioProvider, ABC):
    """
    音频提供者基类
    
    提供音频提供者的通用功能，包括日志记录和错误处理。
    子类需要实现具体的音频源处理逻辑。
    """
    
    def __init__(self, name: str, temp_dir: str = "./temp"):
        """
        初始化音频提供者
        
        Args:
            name: 提供者名称
            temp_dir: 临时文件目录
        """
        self.name = name
        self.temp_dir = temp_dir
        self.logger = logging.getLogger(f"similubot.provider.{name.lower()}")
        
        self.logger.debug(f"{name} 音频提供者初始化完成")
    
    def _log_extraction_start(self, url: str) -> None:
        """记录开始提取音频信息"""
        self.logger.debug(f"开始提取 {self.name} 音频信息: {url}")
    
    def _log_extraction_success(self, audio_info: AudioInfo) -> None:
        """记录提取成功"""
        self.logger.info(f"{self.name} 音频信息提取成功: {audio_info.title} ({audio_info.duration}s)")
    
    def _log_extraction_error(self, url: str, error: Exception) -> None:
        """记录提取错误"""
        self.logger.error(f"{self.name} 音频信息提取失败 - {url}: {error}")
    
    def _log_download_start(self, url: str) -> None:
        """记录开始下载"""
        self.logger.debug(f"开始下载 {self.name} 音频: {url}")
    
    def _log_download_success(self, audio_info: AudioInfo) -> None:
        """记录下载成功"""
        self.logger.info(f"{self.name} 音频下载成功: {audio_info.title}")
    
    def _log_download_error(self, url: str, error: Exception) -> None:
        """记录下载错误"""
        self.logger.error(f"{self.name} 音频下载失败 - {url}: {error}")
    
    async def extract_audio_info(self, url: str) -> Optional[AudioInfo]:
        """
        提取音频信息（带错误处理的包装方法）
        
        Args:
            url: 音频URL
            
        Returns:
            音频信息，失败时返回None
        """
        try:
            self._log_extraction_start(url)
            audio_info = await self._extract_audio_info_impl(url)
            
            if audio_info:
                self._log_extraction_success(audio_info)
                return audio_info
            else:
                self.logger.warning(f"{self.name} 音频信息提取返回空结果: {url}")
                return None
                
        except Exception as e:
            self._log_extraction_error(url, e)
            return None
    
    async def download_audio(self, url: str, progress_callback: Optional[ProgressCallback] = None) -> Tuple[bool, Optional[AudioInfo], Optional[str]]:
        """
        下载音频文件（带错误处理的包装方法）
        
        Args:
            url: 音频URL
            progress_callback: 进度回调
            
        Returns:
            (成功标志, 音频信息, 错误消息)
        """
        try:
            self._log_download_start(url)
            success, audio_info, error = await self._download_audio_impl(url, progress_callback)
            
            if success and audio_info:
                self._log_download_success(audio_info)
                return True, audio_info, None
            else:
                error_msg = error or f"{self.name} 音频下载失败"
                self.logger.warning(error_msg)
                return False, None, error_msg
                
        except Exception as e:
            self._log_download_error(url, e)
            return False, None, str(e)
    
    # 抽象方法，由子类实现
    async def _extract_audio_info_impl(self, url: str) -> Optional[AudioInfo]:
        """子类实现的音频信息提取逻辑"""
        raise NotImplementedError
    
    async def _download_audio_impl(self, url: str, progress_callback: Optional[ProgressCallback] = None) -> Tuple[bool, Optional[AudioInfo], Optional[str]]:
        """子类实现的音频下载逻辑"""
        raise NotImplementedError
