"""
音频提供者工厂 - 管理和创建音频提供者实例

提供统一的接口来获取合适的音频提供者，支持多种音频源的自动检测和处理。
"""

from typing import List, Optional, Dict, Any
from similubot.core.interfaces import IAudioProvider, AudioInfo
from similubot.utils.config_manager import ConfigManager
from .youtube_provider import YouTubeProvider
from .catbox_provider import CatboxProvider
from .netease_provider import NetEaseProvider
from .bilibili_provider import BilibiliProvider


class AudioProviderFactory:
    """
    音频提供者工厂
    
    负责管理所有音频提供者，提供统一的接口来处理不同类型的音频源。
    支持自动检测URL类型并选择合适的提供者。
    """
    
    def __init__(self, temp_dir: str = "./temp", config: Optional[ConfigManager] = None):
        """
        初始化音频提供者工厂
        
        Args:
            temp_dir: 临时文件目录
            config: 配置管理器
        """
        self.temp_dir = temp_dir
        self.config = config
        
        # 初始化所有提供者
        self._providers: List[IAudioProvider] = [
            YouTubeProvider(temp_dir, config),
            CatboxProvider(temp_dir),
            NetEaseProvider(temp_dir, config),  # 传递配置给网易云提供者
            BilibiliProvider(temp_dir)
        ]

        # 创建提供者映射
        self._provider_map: Dict[str, IAudioProvider] = {
            'youtube': self._providers[0],
            'catbox': self._providers[1],
            'netease': self._providers[2],
            'bilibili': self._providers[3]
        }

    def get_supported_providers(self) -> List[str]:
        """
        获取支持的提供者列表
        
        Returns:
            提供者名称列表
        """
        return list(self._provider_map.keys())
    
    def get_provider_by_name(self, name: str) -> Optional[IAudioProvider]:
        """
        根据名称获取提供者
        
        Args:
            name: 提供者名称
            
        Returns:
            提供者实例，未找到时返回None
        """
        return self._provider_map.get(name.lower())
    
    def detect_provider_for_url(self, url: str) -> Optional[IAudioProvider]:
        """
        自动检测URL对应的提供者
        
        Args:
            url: 音频URL
            
        Returns:
            合适的提供者，未找到时返回None
        """
        for provider in self._providers:
            if provider.is_supported_url(url):
                return provider
        return None
    
    def is_supported_url(self, url: str) -> bool:
        """
        检查URL是否被任何提供者支持
        
        Args:
            url: 要检查的URL
            
        Returns:
            如果被支持则返回True
        """
        return self.detect_provider_for_url(url) is not None
    
    def get_supported_url_patterns(self) -> Dict[str, List[str]]:
        """
        获取所有提供者支持的URL模式
        
        Returns:
            提供者名称到URL模式的映射
        """
        patterns = {}
        
        # YouTube 模式
        patterns['youtube'] = [
            'https://www.youtube.com/watch?v=*',
            'https://youtu.be/*',
            'https://www.youtube.com/embed/*',
            'https://www.youtube.com/v/*'
        ]
        
        # Catbox 模式
        patterns['catbox'] = [
            'https://catbox.moe/*.mp3',
            'https://catbox.moe/*.wav',
            'https://catbox.moe/*.ogg',
            'https://catbox.moe/*.flac',
            'https://catbox.moe/*.m4a',
            'https://catbox.moe/*.aac',
            'https://catbox.moe/*.wma'
        ]
        
        return patterns
    
    async def extract_audio_info(self, url: str) -> Optional[AudioInfo]:
        """
        从URL提取音频信息
        
        Args:
            url: 音频URL
            
        Returns:
            音频信息，失败时返回None
        """
        provider = self.detect_provider_for_url(url)
        if not provider:
            return None
        
        return await provider.extract_audio_info(url)
    
    async def download_audio(self, url: str, progress_callback=None):
        """
        下载音频文件
        
        Args:
            url: 音频URL
            progress_callback: 进度回调
            
        Returns:
            (成功标志, 音频信息, 错误消息)
        """
        provider = self.detect_provider_for_url(url)
        if not provider:
            return False, None, "不支持的URL格式"
        
        return await provider.download_audio(url, progress_callback)
    
    def get_provider_stats(self) -> Dict[str, Any]:
        """
        获取提供者统计信息
        
        Returns:
            统计信息字典
        """
        stats = {
            'total_providers': len(self._providers),
            'supported_providers': self.get_supported_providers(),
            'url_patterns': self.get_supported_url_patterns()
        }
        
        return stats
    
    def cleanup_temp_files(self, max_age_hours: int = 24) -> Dict[str, int]:
        """
        清理所有提供者的临时文件
        
        Args:
            max_age_hours: 文件最大保留时间（小时）
            
        Returns:
            每个提供者清理的文件数量
        """
        cleanup_results = {}
        
        for provider in self._providers:
            if hasattr(provider, 'cleanup_temp_files'):
                try:
                    cleaned_count = provider.cleanup_temp_files(max_age_hours)
                    cleanup_results[provider.name] = cleaned_count
                except Exception as e:
                    cleanup_results[provider.name] = f"清理失败: {e}"
        
        return cleanup_results
