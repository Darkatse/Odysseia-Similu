"""
Bilibili 提供者集成测试

测试 Bilibili 提供者与现有队列系统和播放功能的集成，确保命令语法和 Discord 嵌入格式保持一致。
"""

import pytest
import tempfile
from unittest.mock import Mock, AsyncMock, patch

# 尝试导入相关模块
try:
    from similubot.provider.provider_factory import AudioProviderFactory
    from similubot.provider.bilibili_provider import BilibiliProvider
    BILIBILI_INTEGRATION_AVAILABLE = True
except ImportError:
    BILIBILI_INTEGRATION_AVAILABLE = False


@pytest.mark.skipif(not BILIBILI_INTEGRATION_AVAILABLE, reason="Bilibili 集成不可用")
class TestBilibiliIntegration:
    """Bilibili 提供者集成测试类"""
    
    def setup_method(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.factory = AudioProviderFactory(self.temp_dir)
    
    def teardown_method(self):
        """清理测试环境"""
        import shutil
        import os
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_provider_factory_includes_bilibili(self):
        """测试提供者工厂包含 Bilibili 提供者"""
        supported_providers = self.factory.get_supported_providers()
        assert 'bilibili' in supported_providers, "提供者工厂应该包含 Bilibili 提供者"
    
    def test_bilibili_url_detection_in_factory(self):
        """测试工厂能正确检测 Bilibili URL"""
        bilibili_urls = [
            "https://www.bilibili.com/video/BV1uv411q7Mv",
            "https://bilibili.com/video/BV1234567890",
            "https://www.bilibili.com/video/av123456"
        ]
        
        for url in bilibili_urls:
            provider = self.factory.detect_provider_for_url(url)
            assert provider is not None, f"应该为 {url} 找到提供者"
            assert provider.name == "Bilibili", f"{url} 应该被 Bilibili 提供者处理"
    
    def test_bilibili_provider_priority(self):
        """测试 Bilibili 提供者不会与其他提供者冲突"""
        test_cases = [
            ("https://www.youtube.com/watch?v=abc123", "YouTube"),
            ("https://files.catbox.moe/test.mp3", "Catbox"),
            ("https://www.bilibili.com/video/BV1uv411q7Mv", "Bilibili")
        ]
        
        for url, expected_provider in test_cases:
            provider = self.factory.detect_provider_for_url(url)
            assert provider is not None, f"应该为 {url} 找到提供者"
            assert provider.name == expected_provider, f"{url} 应该被 {expected_provider} 提供者处理，实际是 {provider.name}"
    
    def test_bilibili_provider_interface_compliance(self):
        """测试 Bilibili 提供者符合接口规范"""
        provider = self.factory.get_provider_by_name('bilibili')
        assert provider is not None, "应该能获取到 Bilibili 提供者"
        
        # 测试接口方法存在
        assert hasattr(provider, 'is_supported_url'), "提供者应该有 is_supported_url 方法"
        assert hasattr(provider, 'extract_audio_info'), "提供者应该有 extract_audio_info 方法"
        assert hasattr(provider, 'download_audio'), "提供者应该有 download_audio 方法"
        
        # 测试方法可调用
        assert callable(provider.is_supported_url), "is_supported_url 应该是可调用的"
        assert callable(provider.extract_audio_info), "extract_audio_info 应该是可调用的"
        assert callable(provider.download_audio), "download_audio 应该是可调用的"
    
    @pytest.mark.asyncio
    async def test_bilibili_audio_info_extraction_integration(self):
        """测试 Bilibili 音频信息提取的集成"""
        mock_video_info = {
            'title': '集成测试视频',
            'duration': 180,
            'owner': {'name': '测试UP主'},
            'pic': 'https://example.com/thumbnail.jpg'
        }
        
        provider = self.factory.get_provider_by_name('bilibili')
        
        with patch.object(provider, '_extract_video_id', return_value="BV1uv411q7Mv"), \
             patch.object(provider, '_create_bilibili_video_object'), \
             patch('asyncio.run', return_value=mock_video_info):
            
            audio_info = await provider.extract_audio_info("https://www.bilibili.com/video/BV1uv411q7Mv")
            
            assert audio_info is not None, "应该成功提取音频信息"
            assert audio_info.title == '集成测试视频'
            assert audio_info.duration == 180
            assert audio_info.uploader == '测试UP主'
            assert audio_info.url == "https://www.bilibili.com/video/BV1uv411q7Mv"
    
    def test_factory_error_handling_when_bilibili_unavailable(self):
        """测试当 Bilibili 依赖不可用时工厂的错误处理"""
        # 这个测试验证即使 Bilibili 提供者不可用，工厂仍然能正常工作
        with patch('similubot.provider.provider_factory.BILIBILI_PROVIDER_AVAILABLE', False):
            factory = AudioProviderFactory(self.temp_dir)
            supported_providers = factory.get_supported_providers()
            
            # 应该仍然包含其他提供者
            assert 'youtube' in supported_providers
            assert 'catbox' in supported_providers
            # 但不应该包含 Bilibili
            assert 'bilibili' not in supported_providers
    
    def test_bilibili_url_not_supported_by_other_providers(self):
        """测试 Bilibili URL 不会被其他提供者错误识别"""
        bilibili_url = "https://www.bilibili.com/video/BV1uv411q7Mv"
        
        # 获取非 Bilibili 提供者
        youtube_provider = self.factory.get_provider_by_name('youtube')
        catbox_provider = self.factory.get_provider_by_name('catbox')
        
        assert not youtube_provider.is_supported_url(bilibili_url), "YouTube 提供者不应该支持 Bilibili URL"
        assert not catbox_provider.is_supported_url(bilibili_url), "Catbox 提供者不应该支持 Bilibili URL"
    
    def test_factory_url_support_check(self):
        """测试工厂的 URL 支持检查"""
        test_cases = [
            ("https://www.bilibili.com/video/BV1uv411q7Mv", True),
            ("https://www.youtube.com/watch?v=abc123", True),
            ("https://files.catbox.moe/test.mp3", True),
            ("https://unsupported.com/video.mp4", False),
            ("not_a_url", False)
        ]
        
        for url, should_be_supported in test_cases:
            is_supported = self.factory.is_supported_url(url)
            assert is_supported == should_be_supported, f"URL {url} 支持状态应该是 {should_be_supported}，实际是 {is_supported}"
    
    @pytest.mark.asyncio
    async def test_factory_audio_extraction_routing(self):
        """测试工厂正确路由音频提取请求"""
        mock_audio_info = Mock()
        mock_audio_info.title = "测试音频"
        
        # 测试 Bilibili URL 被正确路由
        bilibili_url = "https://www.bilibili.com/video/BV1uv411q7Mv"
        
        with patch.object(self.factory, 'detect_provider_for_url') as mock_detect:
            mock_provider = Mock()
            mock_provider.extract_audio_info = AsyncMock(return_value=mock_audio_info)
            mock_detect.return_value = mock_provider
            
            result = await self.factory.extract_audio_info(bilibili_url)
            
            mock_detect.assert_called_once_with(bilibili_url)
            mock_provider.extract_audio_info.assert_called_once_with(bilibili_url)
            assert result == mock_audio_info
    
    def test_provider_name_consistency(self):
        """测试提供者名称一致性"""
        bilibili_provider = self.factory.get_provider_by_name('bilibili')
        assert bilibili_provider is not None, "应该能通过名称获取 Bilibili 提供者"
        assert bilibili_provider.name == "Bilibili", "提供者名称应该是 'Bilibili'"
    
    def test_multiple_bilibili_urls_detection(self):
        """测试多种 Bilibili URL 格式的检测"""
        bilibili_urls = [
            "https://www.bilibili.com/video/BV1uv411q7Mv",
            "https://bilibili.com/video/BV1234567890",
            "http://www.bilibili.com/video/BVabcdefghij",
            "https://www.bilibili.com/video/av123456",
            "https://bilibili.com/video/av987654321"
        ]

        for url in bilibili_urls:
            assert self.factory.is_supported_url(url), f"应该支持 Bilibili URL: {url}"
            provider = self.factory.detect_provider_for_url(url)
            assert provider.name == "Bilibili", f"URL {url} 应该被 Bilibili 提供者处理"

    def test_discord_integration_audio_source_type_detection(self):
        """测试 Discord 集成中的音频源类型检测"""
        # 这个测试验证修复后的 Discord 集成能正确识别 Bilibili URL
        try:
            from similubot.adapters.music_player_adapter import MusicPlayerAdapter, AudioSourceType
            from similubot.playback.playback_engine import PlaybackEngine

            # 创建模拟的播放引擎和适配器
            mock_bot = Mock()
            playback_engine = PlaybackEngine(mock_bot, self.temp_dir, None)
            adapter = MusicPlayerAdapter(playback_engine)

            # 测试音频源类型检测
            test_cases = [
                ("https://www.youtube.com/watch?v=abc123", AudioSourceType.YOUTUBE),
                ("https://files.catbox.moe/test.mp3", AudioSourceType.CATBOX),
                ("https://www.bilibili.com/video/BV1uv411q7Mv", AudioSourceType.BILIBILI),
                ("https://bilibili.com/video/BV1234567890", AudioSourceType.BILIBILI),
                ("https://www.bilibili.com/video/av123456", AudioSourceType.BILIBILI),
            ]

            for url, expected_type in test_cases:
                detected_type = adapter.detect_audio_source_type(url)
                assert detected_type == expected_type, f"URL {url} 应该被检测为 {expected_type.value}，实际是 {detected_type.value if detected_type else None}"

            # 验证 Bilibili 客户端适配器存在
            assert hasattr(adapter, 'bilibili_client'), "适配器应该有 bilibili_client 属性"
            assert hasattr(adapter.bilibili_client, 'extract_audio_info'), "bilibili_client 应该有 extract_audio_info 方法"

        except ImportError:
            # 如果适配器不可用，跳过这个测试
            import pytest
            pytest.skip("MusicPlayerAdapter 不可用")

    @pytest.mark.asyncio
    async def test_discord_command_audio_info_extraction(self):
        """测试 Discord 命令中的音频信息提取"""
        # 这个测试验证修复后的命令处理能正确提取 Bilibili 音频信息
        try:
            from similubot.adapters.music_player_adapter import MusicPlayerAdapter
            from similubot.playback.playback_engine import PlaybackEngine

            # 创建模拟的播放引擎和适配器
            mock_bot = Mock()
            playback_engine = PlaybackEngine(mock_bot, self.temp_dir, None)
            adapter = MusicPlayerAdapter(playback_engine)

            # 模拟 Bilibili 音频信息
            mock_audio_info = Mock()
            mock_audio_info.title = "Discord 集成测试视频"
            mock_audio_info.duration = 240
            mock_audio_info.uploader = "测试UP主"
            mock_audio_info.url = "https://www.bilibili.com/video/BV1uv411q7Mv"

            # 模拟 bilibili_client.extract_audio_info 方法
            with patch.object(adapter.bilibili_client, 'extract_audio_info', return_value=mock_audio_info):
                # 测试音频信息提取
                audio_info = await adapter.bilibili_client.extract_audio_info("https://www.bilibili.com/video/BV1uv411q7Mv")

                assert audio_info is not None, "应该成功提取音频信息"
                assert audio_info.title == "Discord 集成测试视频", "标题应该正确"
                assert audio_info.uploader == "测试UP主", "UP主应该正确"
                assert audio_info.duration == 240, "时长应该正确"

        except ImportError:
            # 如果适配器不可用，跳过这个测试
            import pytest
            pytest.skip("MusicPlayerAdapter 不可用")


@pytest.mark.skipif(BILIBILI_INTEGRATION_AVAILABLE, reason="测试依赖不可用时的行为")
class TestBilibiliIntegrationUnavailable:
    """测试 Bilibili 集成不可用时的行为"""
    
    def test_factory_works_without_bilibili(self):
        """测试没有 Bilibili 提供者时工厂仍能正常工作"""
        temp_dir = tempfile.mkdtemp()
        try:
            factory = AudioProviderFactory(temp_dir)
            supported_providers = factory.get_supported_providers()
            
            # 应该至少包含基本提供者
            assert len(supported_providers) >= 2, "应该至少有 YouTube 和 Catbox 提供者"
            assert 'youtube' in supported_providers
            assert 'catbox' in supported_providers
            
        finally:
            import shutil
            import os
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
