"""
网易云音乐反向代理工具 - 处理域名替换和URL重写

用于解决海外部署时网易云音乐版权限制问题，通过反向代理服务器
路由所有网易云音乐相关请求到中国IP地址。

主要功能：
- URL域名替换和重写
- 请求头处理和代理配置
- 支持多种网易云音乐域名映射
- 详细的调试日志记录
"""

import logging
import re
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

from similubot.utils.config_manager import ConfigManager


class NetEaseProxyManager:
    """
    网易云音乐反向代理管理器
    
    负责处理所有网易云音乐相关请求的域名替换和URL重写，
    支持配置化的代理域名映射和请求头处理。
    """
    
    # 支持的网易云音乐域名列表
    NETEASE_DOMAINS = {
        'music.163.com',      # 主要API和网页域名
        'music.126.net',      # CDN和媒体文件域名
        'y.music.163.com',    # 移动端域名
        'api.paugram.com'     # 第三方API代理域名
    }
    
    def __init__(self, config: Optional[ConfigManager] = None):
        """
        初始化网易云音乐代理管理器
        
        Args:
            config: 配置管理器实例，如果为None则创建新实例
        """
        self.logger = logging.getLogger("similubot.utils.netease_proxy")
        self.config = config or ConfigManager()
        
        # 缓存配置以提高性能
        self._enabled = None
        self._domain_mapping = None
        self._proxy_domain = None
        self._use_https = None
        
        self.logger.debug("网易云音乐代理管理器初始化完成")
    
    def is_enabled(self) -> bool:
        """
        检查反向代理功能是否启用
        
        Returns:
            如果启用反向代理则返回True
        """
        if self._enabled is None:
            self._enabled = self.config.is_netease_proxy_enabled()
            if self._enabled:
                self.logger.info("网易云音乐反向代理功能已启用")
            else:
                self.logger.debug("网易云音乐反向代理功能未启用")
        return self._enabled
    
    def get_domain_mapping(self) -> Dict[str, str]:
        """
        获取域名映射配置

        Returns:
            域名映射字典，键为原始域名，值为目标域名
        """
        if self._domain_mapping is None:
            try:
                mapping = self.config.get_netease_domain_mapping()
                # 验证映射是否为字典类型
                if isinstance(mapping, dict):
                    self._domain_mapping = mapping
                else:
                    self.logger.warning(f"域名映射配置类型错误，期望dict，实际{type(mapping)}，使用空字典")
                    self._domain_mapping = {}
            except Exception as e:
                self.logger.error(f"获取域名映射配置时出错: {e}")
                self._domain_mapping = {}

            if self.config.should_log_domain_replacement():
                self.logger.debug(f"加载域名映射配置: {self._domain_mapping}")
        return self._domain_mapping
    
    def get_proxy_domain(self) -> Optional[str]:
        """
        获取默认代理域名
        
        Returns:
            代理域名，如果未配置则返回None
        """
        if self._proxy_domain is None:
            self._proxy_domain = self.config.get_netease_proxy_domain()
            if self._proxy_domain:
                self.logger.debug(f"使用代理域名: {self._proxy_domain}")
        return self._proxy_domain
    
    def should_use_https(self) -> bool:
        """
        检查是否应该使用HTTPS协议
        
        Returns:
            如果应该使用HTTPS则返回True
        """
        if self._use_https is None:
            self._use_https = self.config.should_use_https_for_proxy()
            protocol = "HTTPS" if self._use_https else "HTTP"
            self.logger.debug(f"代理请求将使用 {protocol} 协议")
        return self._use_https
    
    def is_netease_url(self, url: str) -> bool:
        """
        检查URL是否为网易云音乐相关域名
        
        Args:
            url: 要检查的URL
            
        Returns:
            如果是网易云音乐URL则返回True
        """
        if not url:
            return False
            
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # 移除端口号
            if ':' in domain:
                domain = domain.split(':')[0]
            
            # 检查是否匹配任何网易云音乐域名
            for netease_domain in self.NETEASE_DOMAINS:
                if domain == netease_domain or domain.endswith('.' + netease_domain):
                    return True
                    
            return False
            
        except Exception as e:
            self.logger.warning(f"检查网易云音乐URL时出错: {e}")
            return False
    
    def replace_domain_in_url(self, url: str) -> str:
        """
        替换URL中的域名为代理域名
        
        Args:
            url: 原始URL
            
        Returns:
            替换域名后的URL，如果不需要替换则返回原始URL
        """
        if not self.is_enabled() or not url:
            return url
            
        if not self.is_netease_url(url):
            return url
            
        try:
            parsed = urlparse(url)
            original_domain = parsed.netloc.lower()
            
            # 移除端口号进行匹配
            domain_without_port = original_domain.split(':')[0]
            
            # 获取域名映射
            domain_mapping = self.get_domain_mapping()
            target_domain = None
            
            # 查找精确匹配的域名映射
            for source_domain, mapped_domain in domain_mapping.items():
                if domain_without_port == source_domain.lower():
                    target_domain = mapped_domain
                    break
            
            # 如果没有找到精确映射，使用默认代理域名
            if not target_domain:
                target_domain = self.get_proxy_domain()
            
            if not target_domain:
                self.logger.debug(f"未配置代理域名，保持原始URL: {url}")
                return url
            
            # 构建新的URL
            new_scheme = 'https' if self.should_use_https() else 'http'
            new_netloc = target_domain
            
            # 保持原始端口号（如果有）
            if ':' in original_domain and ':' not in target_domain:
                port = original_domain.split(':')[1]
                new_netloc = f"{target_domain}:{port}"
            
            new_url = urlunparse((
                new_scheme,
                new_netloc,
                parsed.path,
                parsed.params,
                parsed.query,
                parsed.fragment
            ))
            
            if self.config.should_log_domain_replacement():
                self.logger.debug(f"域名替换: {url} -> {new_url}")
            
            return new_url
            
        except Exception as e:
            self.logger.error(f"替换URL域名时出错: {e}")
            return url
    
    def get_proxy_headers(self, original_url: str, base_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """
        获取代理请求的HTTP头
        
        Args:
            original_url: 原始URL
            base_headers: 基础请求头字典
            
        Returns:
            处理后的请求头字典
        """
        headers = base_headers.copy() if base_headers else {}
        
        if not self.is_enabled():
            return headers
        
        try:
            parsed_original = urlparse(original_url)
            
            # 处理Referer头
            if self.config.should_preserve_referer():
                if 'Referer' not in headers and 'referer' not in headers:
                    # 设置原始域名作为Referer
                    original_base = f"{parsed_original.scheme}://{parsed_original.netloc}/"
                    headers['Referer'] = original_base
            else:
                # 移除或替换Referer头
                for key in list(headers.keys()):
                    if key.lower() == 'referer':
                        del headers[key]
            
            # 处理Host头
            if not self.config.should_preserve_host():
                # 移除Host头，让aiohttp自动设置为代理域名
                for key in list(headers.keys()):
                    if key.lower() == 'host':
                        del headers[key]
            
            # 添加自定义请求头
            custom_headers = self.config.get_netease_proxy_custom_headers()
            headers.update(custom_headers)
            
            if self.config.should_log_proxy_requests():
                self.logger.debug(f"代理请求头: {headers}")
            
            return headers
            
        except Exception as e:
            self.logger.error(f"处理代理请求头时出错: {e}")
            return headers
    
    def process_url_and_headers(self, url: str, headers: Optional[Dict[str, str]] = None) -> Tuple[str, Dict[str, str]]:
        """
        同时处理URL和请求头的便捷方法
        
        Args:
            url: 原始URL
            headers: 原始请求头
            
        Returns:
            (处理后的URL, 处理后的请求头)
        """
        processed_url = self.replace_domain_in_url(url)
        processed_headers = self.get_proxy_headers(url, headers)
        
        return processed_url, processed_headers
    
    def clear_cache(self):
        """
        清除缓存的配置，强制重新加载
        
        用于配置更新后刷新缓存。
        """
        self._enabled = None
        self._domain_mapping = None
        self._proxy_domain = None
        self._use_https = None
        self.logger.debug("已清除代理配置缓存")


# 全局代理管理器实例
_proxy_manager: Optional[NetEaseProxyManager] = None


def get_proxy_manager(config: Optional[ConfigManager] = None) -> NetEaseProxyManager:
    """
    获取全局代理管理器实例
    
    Args:
        config: 配置管理器实例
        
    Returns:
        代理管理器实例
    """
    global _proxy_manager
    if _proxy_manager is None:
        _proxy_manager = NetEaseProxyManager(config)
    return _proxy_manager


def process_netease_url(url: str, headers: Optional[Dict[str, str]] = None) -> Tuple[str, Dict[str, str]]:
    """
    处理网易云音乐URL和请求头的便捷函数
    
    Args:
        url: 原始URL
        headers: 原始请求头
        
    Returns:
        (处理后的URL, 处理后的请求头)
    """
    manager = get_proxy_manager()
    return manager.process_url_and_headers(url, headers)
