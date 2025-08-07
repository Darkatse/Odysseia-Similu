"""
网易云音乐反向代理功能测试

测试反向代理管理器的域名替换、URL重写、请求头处理等核心功能，
确保在海外部署环境下能够正确路由网易云音乐请求。
"""

import pytest
import unittest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

from similubot.utils.netease_proxy import NetEaseProxyManager, get_proxy_manager, process_netease_url
from similubot.utils.config_manager import ConfigManager


class TestNetEaseProxyManager(unittest.TestCase):
    """网易云音乐反向代理管理器测试类"""

    def setUp(self):
        """测试前准备"""
        # 创建模拟配置
        self.mock_config = Mock(spec=ConfigManager)
        
        # 设置默认配置返回值
        self.mock_config.is_netease_proxy_enabled.return_value = True
        self.mock_config.get_netease_proxy_domain.return_value = "proxy.example.com"
        self.mock_config.should_use_https_for_proxy.return_value = False
        self.mock_config.get_netease_domain_mapping.return_value = {
            "music.163.com": "proxy.example.com",
            "music.126.net": "proxy.example.com",
            "api.paugram.com": "proxy.example.com"
        }
        self.mock_config.should_preserve_referer.return_value = True
        self.mock_config.should_preserve_host.return_value = False
        self.mock_config.get_netease_proxy_custom_headers.return_value = {}
        self.mock_config.should_log_domain_replacement.return_value = True
        self.mock_config.should_log_proxy_requests.return_value = False
        
        # 创建代理管理器实例
        self.proxy_manager = NetEaseProxyManager(self.mock_config)

    def test_initialization(self):
        """测试代理管理器初始化"""
        self.assertIsNotNone(self.proxy_manager)
        self.assertEqual(self.proxy_manager.config, self.mock_config)
        self.assertIsNotNone(self.proxy_manager.logger)

    def test_is_enabled_true(self):
        """测试代理功能启用状态检查 - 启用情况"""
        self.assertTrue(self.proxy_manager.is_enabled())
        self.mock_config.is_netease_proxy_enabled.assert_called_once()

    def test_is_enabled_false(self):
        """测试代理功能启用状态检查 - 禁用情况"""
        self.mock_config.is_netease_proxy_enabled.return_value = False
        proxy_manager = NetEaseProxyManager(self.mock_config)
        
        self.assertFalse(proxy_manager.is_enabled())

    def test_is_netease_url_valid_domains(self):
        """测试网易云音乐URL识别 - 有效域名"""
        test_urls = [
            "https://music.163.com/song?id=123456",
            "http://music.126.net/audio/123456.mp3",
            "https://y.music.163.com/m/song?id=123456",
            "https://api.paugram.com/netease/?id=123456",
            "https://subdomain.music.163.com/path",
        ]
        
        for url in test_urls:
            with self.subTest(url=url):
                self.assertTrue(self.proxy_manager.is_netease_url(url))

    def test_is_netease_url_invalid_domains(self):
        """测试网易云音乐URL识别 - 无效域名"""
        test_urls = [
            "https://youtube.com/watch?v=123456",
            "https://spotify.com/track/123456",
            "https://example.com/music",
            "https://music.google.com/song",
            "",
            None,
        ]
        
        for url in test_urls:
            with self.subTest(url=url):
                self.assertFalse(self.proxy_manager.is_netease_url(url))

    def test_replace_domain_in_url_basic(self):
        """测试基本域名替换功能"""
        test_cases = [
            {
                "input": "https://music.163.com/song?id=123456",
                "expected": "http://proxy.example.com/song?id=123456"
            },
            {
                "input": "https://music.126.net/audio/123456.mp3",
                "expected": "http://proxy.example.com/audio/123456.mp3"
            },
            {
                "input": "https://api.paugram.com/netease/?id=123456",
                "expected": "http://proxy.example.com/netease/?id=123456"
            }
        ]
        
        for case in test_cases:
            with self.subTest(input_url=case["input"]):
                result = self.proxy_manager.replace_domain_in_url(case["input"])
                self.assertEqual(result, case["expected"])

    def test_replace_domain_in_url_with_https(self):
        """测试使用HTTPS的域名替换"""
        self.mock_config.should_use_https_for_proxy.return_value = True
        proxy_manager = NetEaseProxyManager(self.mock_config)
        
        input_url = "https://music.163.com/song?id=123456"
        expected = "https://proxy.example.com/song?id=123456"
        
        result = proxy_manager.replace_domain_in_url(input_url)
        self.assertEqual(result, expected)

    def test_replace_domain_in_url_disabled(self):
        """测试代理功能禁用时的域名替换"""
        self.mock_config.is_netease_proxy_enabled.return_value = False
        proxy_manager = NetEaseProxyManager(self.mock_config)
        
        input_url = "https://music.163.com/song?id=123456"
        result = proxy_manager.replace_domain_in_url(input_url)
        
        # 应该返回原始URL
        self.assertEqual(result, input_url)

    def test_replace_domain_in_url_non_netease(self):
        """测试非网易云音乐URL的域名替换"""
        input_url = "https://youtube.com/watch?v=123456"
        result = self.proxy_manager.replace_domain_in_url(input_url)
        
        # 应该返回原始URL
        self.assertEqual(result, input_url)

    def test_get_proxy_headers_basic(self):
        """测试基本代理请求头处理"""
        original_url = "https://music.163.com/song?id=123456"
        base_headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json"
        }
        
        result = self.proxy_manager.get_proxy_headers(original_url, base_headers)
        
        # 应该包含原始请求头
        self.assertIn("User-Agent", result)
        self.assertIn("Accept", result)
        self.assertEqual(result["User-Agent"], "Mozilla/5.0")
        
        # 应该添加Referer头
        self.assertIn("Referer", result)
        self.assertEqual(result["Referer"], "https://music.163.com/")

    def test_get_proxy_headers_preserve_referer_false(self):
        """测试不保留Referer头的情况"""
        self.mock_config.should_preserve_referer.return_value = False
        proxy_manager = NetEaseProxyManager(self.mock_config)
        
        original_url = "https://music.163.com/song?id=123456"
        base_headers = {"Referer": "https://example.com/"}
        
        result = proxy_manager.get_proxy_headers(original_url, base_headers)
        
        # Referer头应该被移除
        self.assertNotIn("Referer", result)

    def test_get_proxy_headers_custom_headers(self):
        """测试自定义请求头添加"""
        custom_headers = {
            "X-Forwarded-For": "192.168.1.1",
            "X-Real-IP": "192.168.1.1"
        }
        self.mock_config.get_netease_proxy_custom_headers.return_value = custom_headers
        proxy_manager = NetEaseProxyManager(self.mock_config)
        
        original_url = "https://music.163.com/song?id=123456"
        result = proxy_manager.get_proxy_headers(original_url, {})
        
        # 应该包含自定义请求头
        self.assertIn("X-Forwarded-For", result)
        self.assertIn("X-Real-IP", result)
        self.assertEqual(result["X-Forwarded-For"], "192.168.1.1")

    def test_process_url_and_headers(self):
        """测试同时处理URL和请求头"""
        original_url = "https://music.163.com/song?id=123456"
        original_headers = {"User-Agent": "Mozilla/5.0"}
        
        processed_url, processed_headers = self.proxy_manager.process_url_and_headers(
            original_url, original_headers
        )
        
        # URL应该被替换
        self.assertEqual(processed_url, "http://proxy.example.com/song?id=123456")
        
        # 请求头应该被处理
        self.assertIn("User-Agent", processed_headers)
        self.assertIn("Referer", processed_headers)

    def test_clear_cache(self):
        """测试缓存清除功能"""
        # 先触发缓存
        self.proxy_manager.is_enabled()
        self.proxy_manager.get_domain_mapping()
        
        # 清除缓存
        self.proxy_manager.clear_cache()
        
        # 验证缓存已清除
        self.assertIsNone(self.proxy_manager._enabled)
        self.assertIsNone(self.proxy_manager._domain_mapping)
        self.assertIsNone(self.proxy_manager._proxy_domain)
        self.assertIsNone(self.proxy_manager._use_https)

    def test_domain_mapping_priority(self):
        """测试域名映射优先级"""
        # 设置特定域名映射
        self.mock_config.get_netease_domain_mapping.return_value = {
            "music.163.com": "specific.proxy.com",
            "music.126.net": ""  # 空值，应该使用默认代理域名
        }
        proxy_manager = NetEaseProxyManager(self.mock_config)
        
        # 测试特定映射
        result1 = proxy_manager.replace_domain_in_url("https://music.163.com/song?id=123")
        self.assertEqual(result1, "http://specific.proxy.com/song?id=123")
        
        # 测试默认映射
        result2 = proxy_manager.replace_domain_in_url("https://music.126.net/audio/123.mp3")
        self.assertEqual(result2, "http://proxy.example.com/audio/123.mp3")

    def test_url_with_port(self):
        """测试带端口号的URL处理"""
        input_url = "https://music.163.com:8080/song?id=123456"
        expected = "http://proxy.example.com:8080/song?id=123456"
        
        result = self.proxy_manager.replace_domain_in_url(input_url)
        self.assertEqual(result, expected)

    def test_malformed_url_handling(self):
        """测试畸形URL的处理"""
        malformed_urls = [
            "not-a-url",
            "://missing-scheme",
            "https://",
            "music.163.com/song?id=123"  # 缺少协议
        ]
        
        for url in malformed_urls:
            with self.subTest(url=url):
                # 应该返回原始URL而不抛出异常
                result = self.proxy_manager.replace_domain_in_url(url)
                self.assertEqual(result, url)


class TestGlobalFunctions(unittest.TestCase):
    """测试全局函数"""

    @patch('similubot.utils.netease_proxy._proxy_manager', None)
    def test_get_proxy_manager(self):
        """测试全局代理管理器获取"""
        mock_config = Mock(spec=ConfigManager)
        
        manager = get_proxy_manager(mock_config)
        
        self.assertIsInstance(manager, NetEaseProxyManager)
        self.assertEqual(manager.config, mock_config)

    def test_process_netease_url(self):
        """测试便捷URL处理函数"""
        with patch('similubot.utils.netease_proxy.get_proxy_manager') as mock_get_manager:
            mock_manager = Mock()
            mock_manager.process_url_and_headers.return_value = (
                "http://proxy.example.com/song?id=123",
                {"User-Agent": "Mozilla/5.0", "Referer": "https://music.163.com/"}
            )
            mock_get_manager.return_value = mock_manager
            
            url, headers = process_netease_url(
                "https://music.163.com/song?id=123",
                {"User-Agent": "Mozilla/5.0"}
            )
            
            self.assertEqual(url, "http://proxy.example.com/song?id=123")
            self.assertIn("Referer", headers)


class TestNetEaseIntegration(unittest.TestCase):
    """测试与NetEase组件的集成"""

    def setUp(self):
        """测试前准备"""
        self.mock_config = Mock(spec=ConfigManager)
        self.mock_config.is_netease_proxy_enabled.return_value = True
        self.mock_config.get_netease_proxy_domain.return_value = "proxy.example.com"
        self.mock_config.should_use_https_for_proxy.return_value = False
        self.mock_config.get_netease_domain_mapping.return_value = {
            "music.163.com": "proxy.example.com",
            "api.paugram.com": "proxy.example.com"
        }
        self.mock_config.should_preserve_referer.return_value = True
        self.mock_config.should_preserve_host.return_value = False
        self.mock_config.get_netease_proxy_custom_headers.return_value = {}
        self.mock_config.should_log_domain_replacement.return_value = False
        self.mock_config.should_log_proxy_requests.return_value = False

    @patch('similubot.utils.netease_search.get_proxy_manager')
    def test_netease_search_client_integration(self, mock_get_proxy_manager):
        """测试NetEaseSearchClient与代理的集成"""
        from similubot.utils.netease_search import NetEaseSearchClient

        # 设置模拟代理管理器
        mock_proxy_manager = Mock()
        mock_proxy_manager.process_url_and_headers.return_value = (
            "http://proxy.example.com/api/search/get",
            {"User-Agent": "Mozilla/5.0", "Referer": "http://proxy.example.com/"}
        )
        mock_proxy_manager.replace_domain_in_url.return_value = "http://proxy.example.com/netease/?id=123"
        mock_get_proxy_manager.return_value = mock_proxy_manager

        # 创建搜索客户端
        client = NetEaseSearchClient(self.mock_config)

        # 验证代理管理器被正确初始化
        mock_get_proxy_manager.assert_called_once_with(self.mock_config)
        self.assertEqual(client.proxy_manager, mock_proxy_manager)

        # 测试播放URL生成
        playback_url = client.get_playback_url("123456", use_api=True)
        mock_proxy_manager.replace_domain_in_url.assert_called()
        self.assertEqual(playback_url, "http://proxy.example.com/netease/?id=123")

    @patch('similubot.utils.netease_proxy.get_proxy_manager')
    def test_netease_provider_integration(self, mock_get_proxy_manager):
        """测试NetEaseProvider与代理的集成"""
        from similubot.provider.netease_provider import NetEaseProvider

        # 设置模拟代理管理器
        mock_proxy_manager = Mock()
        mock_proxy_manager.process_url_and_headers.return_value = (
            "http://proxy.example.com/song/media/outer/url?id=123.mp3",
            {"User-Agent": "Mozilla/5.0", "Referer": "http://proxy.example.com/"}
        )
        mock_get_proxy_manager.return_value = mock_proxy_manager

        # 创建提供者
        provider = NetEaseProvider("./temp", self.mock_config)

        # 验证代理管理器被正确初始化
        mock_get_proxy_manager.assert_called_once_with(self.mock_config)
        self.assertEqual(provider.proxy_manager, mock_proxy_manager)

    @patch('similubot.utils.netease_proxy.get_proxy_manager')
    def test_lyrics_client_integration(self, mock_get_proxy_manager):
        """测试歌词客户端与代理的集成"""
        from similubot.lyrics.lyrics_client import NetEaseCloudMusicClient

        # 设置模拟代理管理器
        mock_proxy_manager = Mock()
        mock_proxy_manager.process_url_and_headers.return_value = (
            "http://proxy.example.com/netease/?id=123",
            {"User-Agent": "Mozilla/5.0", "Referer": "http://proxy.example.com/"}
        )
        mock_get_proxy_manager.return_value = mock_proxy_manager

        # 创建歌词客户端
        client = NetEaseCloudMusicClient(self.mock_config)

        # 验证代理管理器被正确初始化
        mock_get_proxy_manager.assert_called_once_with(self.mock_config)
        self.assertEqual(client.proxy_manager, mock_proxy_manager)


class TestConfigurationEdgeCases(unittest.TestCase):
    """测试配置边界情况"""

    def test_empty_proxy_domain(self):
        """测试空代理域名配置"""
        mock_config = Mock(spec=ConfigManager)
        mock_config.is_netease_proxy_enabled.return_value = True
        mock_config.get_netease_proxy_domain.return_value = ""
        mock_config.get_netease_domain_mapping.return_value = {}

        proxy_manager = NetEaseProxyManager(mock_config)

        # 空代理域名时应该返回原始URL
        original_url = "https://music.163.com/song?id=123"
        result = proxy_manager.replace_domain_in_url(original_url)
        self.assertEqual(result, original_url)

    def test_none_proxy_domain(self):
        """测试None代理域名配置"""
        mock_config = Mock(spec=ConfigManager)
        mock_config.is_netease_proxy_enabled.return_value = True
        mock_config.get_netease_proxy_domain.return_value = None
        mock_config.get_netease_domain_mapping.return_value = {}

        proxy_manager = NetEaseProxyManager(mock_config)

        # None代理域名时应该返回原始URL
        original_url = "https://music.163.com/song?id=123"
        result = proxy_manager.replace_domain_in_url(original_url)
        self.assertEqual(result, original_url)

    def test_invalid_domain_mapping(self):
        """测试无效域名映射配置"""
        mock_config = Mock(spec=ConfigManager)
        mock_config.is_netease_proxy_enabled.return_value = True
        mock_config.get_netease_proxy_domain.return_value = "proxy.example.com"
        mock_config.get_netease_domain_mapping.return_value = "invalid_mapping"  # 不是字典
        mock_config.should_log_domain_replacement.return_value = False

        proxy_manager = NetEaseProxyManager(mock_config)

        # 应该处理无效配置而不崩溃
        mapping = proxy_manager.get_domain_mapping()
        self.assertEqual(mapping, {})

    def test_exception_handling_in_url_replacement(self):
        """测试URL替换中的异常处理"""
        mock_config = Mock(spec=ConfigManager)
        mock_config.is_netease_proxy_enabled.return_value = True
        mock_config.get_netease_proxy_domain.side_effect = Exception("Config error")

        proxy_manager = NetEaseProxyManager(mock_config)

        # 异常情况下应该返回原始URL
        original_url = "https://music.163.com/song?id=123"
        result = proxy_manager.replace_domain_in_url(original_url)
        self.assertEqual(result, original_url)


if __name__ == '__main__':
    unittest.main()
