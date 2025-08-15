"""
测试NetEase URL刷新功能 - 验证过期URL的自动刷新机制

测试过期URL检测和刷新逻辑，确保当NetEase直接下载链接过期时，
系统能够自动使用歌曲ID重新生成新的下载链接。
"""

import pytest
import asyncio
import aiohttp
from unittest.mock import AsyncMock, MagicMock, patch
import tempfile
import os

from similubot.provider.netease_provider import NetEaseProvider
from similubot.utils.config_manager import ConfigManager
from similubot.core.interfaces import AudioInfo


class TestNetEaseURLRefresh:
    """NetEase URL刷新功能测试类"""

    @pytest.fixture
    def config(self):
        """创建测试配置"""
        config = ConfigManager()
        # 禁用会员功能以简化测试
        config.config_data = {
            'netease': {
                'member': {
                    'enabled': False
                }
            }
        }
        return config

    @pytest.fixture
    def provider(self, config):
        """创建NetEase提供者实例"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = NetEaseProvider(config, temp_dir)
            yield provider

    @pytest.mark.asyncio
    async def test_detect_expired_url_403_error(self, provider):
        """测试检测403过期URL错误"""
        expired_url = "http://m701.music.126.net/20250816001402/expired/test.mp3"
        file_path = os.path.join(provider.temp_dir, "test.mp3")
        
        # 模拟403响应，包含过期URL错误信息
        mock_response = MagicMock()
        mock_response.status = 403
        mock_response.headers = {'X-AUTH-MSG': 'auth failed - expired url'}
        
        # 模拟刷新URL成功
        fresh_url = "http://m701.music.126.net/20250816123456/fresh/test.mp3"
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            mock_session.get.return_value.__aenter__.return_value = mock_response
            
            # 模拟URL刷新方法
            provider._refresh_expired_url = AsyncMock(return_value=fresh_url)
            
            # 执行下载
            result = await provider._download_file_with_retry(expired_url, file_path, None, 0)
            
            # 验证检测到过期URL并尝试刷新
            provider._refresh_expired_url.assert_called_once_with(expired_url)

    @pytest.mark.asyncio
    async def test_refresh_expired_url_with_cached_song_id(self, provider):
        """测试使用缓存的歌曲ID刷新过期URL"""
        expired_url = "http://m701.music.126.net/expired/test.mp3"
        song_id = "517567145"
        fresh_url = "https://api.paugram.com/netease/?id=517567145"
        
        # 设置缓存映射
        provider._cache_url_song_id_mapping(expired_url, song_id)
        
        with patch('similubot.utils.netease_search.get_playback_url') as mock_get_url:
            mock_get_url.return_value = fresh_url
            
            # 执行URL刷新
            result = await provider._refresh_expired_url(expired_url)
            
            # 验证结果
            assert result == fresh_url
            mock_get_url.assert_called_with(song_id, use_api=True, config=provider.config)

    @pytest.mark.asyncio
    async def test_refresh_expired_url_with_api_url(self, provider):
        """测试从API URL中提取歌曲ID并刷新"""
        expired_url = "https://api.paugram.com/netease/?id=517567145"
        song_id = "517567145"
        fresh_url = "http://music.163.com/song/media/outer/url?id=517567145.mp3"
        
        with patch('similubot.utils.netease_search.get_playback_url') as mock_get_url:
            mock_get_url.return_value = fresh_url
            
            # 执行URL刷新
            result = await provider._refresh_expired_url(expired_url)
            
            # 验证结果
            assert result == fresh_url
            # 应该先尝试API模式，然后尝试直接模式
            assert mock_get_url.call_count >= 1

    @pytest.mark.asyncio
    async def test_refresh_expired_url_with_member_auth(self, provider):
        """测试使用会员认证刷新过期URL"""
        expired_url = "http://m701.music.126.net/expired/test.mp3"
        song_id = "517567145"
        fresh_member_url = "http://m701.music.126.net/fresh/member/test.mp3"
        
        # 启用会员功能
        provider.member_auth.is_enabled = MagicMock(return_value=True)
        provider.member_auth.get_member_audio_url = AsyncMock(return_value=fresh_member_url)
        
        # 设置缓存映射
        provider._cache_url_song_id_mapping(expired_url, song_id)
        
        # 执行URL刷新
        result = await provider._refresh_expired_url(expired_url)
        
        # 验证结果
        assert result == fresh_member_url
        provider.member_auth.get_member_audio_url.assert_called_once_with(song_id)

    @pytest.mark.asyncio
    async def test_refresh_expired_url_fallback_modes(self, provider):
        """测试URL刷新的回退模式"""
        expired_url = "https://api.paugram.com/netease/?id=517567145"
        song_id = "517567145"
        
        # 模拟API模式失败，直接模式成功
        fresh_direct_url = "http://music.163.com/song/media/outer/url?id=517567145.mp3"
        
        with patch('similubot.utils.netease_search.get_playback_url') as mock_get_url:
            # 第一次调用（API模式）返回相同URL（视为失败）
            # 第二次调用（直接模式）返回新URL
            mock_get_url.side_effect = [expired_url, fresh_direct_url]
            
            # 执行URL刷新
            result = await provider._refresh_expired_url(expired_url)
            
            # 验证结果
            assert result == fresh_direct_url
            assert mock_get_url.call_count == 2
            
            # 验证调用参数
            calls = mock_get_url.call_args_list
            assert calls[0][1]['use_api'] == True  # 第一次调用使用API模式
            assert calls[1][1]['use_api'] == False  # 第二次调用使用直接模式

    @pytest.mark.asyncio
    async def test_refresh_expired_url_no_song_id(self, provider):
        """测试无法提取歌曲ID时的处理"""
        expired_url = "http://unknown.domain.com/audio.mp3"
        
        # 执行URL刷新
        result = await provider._refresh_expired_url(expired_url)
        
        # 验证结果
        assert result is None

    @pytest.mark.asyncio
    async def test_download_file_retry_mechanism(self, provider):
        """测试下载文件的重试机制"""
        expired_url = "http://m701.music.126.net/expired/test.mp3"
        fresh_url = "http://m701.music.126.net/fresh/test.mp3"
        file_path = os.path.join(provider.temp_dir, "test.mp3")

        # 模拟URL刷新
        provider._refresh_expired_url = AsyncMock(return_value=fresh_url)

        # 模拟下载文件的重试逻辑
        with patch.object(provider, '_download_file_with_retry') as mock_retry:
            mock_retry.return_value = True

            # 执行下载
            result = await provider._download_file(expired_url, file_path)

            # 验证重试方法被调用
            mock_retry.assert_called_once_with(expired_url, file_path, None, 0)

    @pytest.mark.asyncio
    async def test_max_retry_limit(self, provider):
        """测试最大重试次数限制"""
        expired_url = "http://m701.music.126.net/expired/test.mp3"
        file_path = os.path.join(provider.temp_dir, "test.mp3")
        
        # 模拟持续返回403错误
        mock_response = MagicMock()
        mock_response.status = 403
        mock_response.headers = {'X-AUTH-MSG': 'auth failed - expired url'}
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            mock_session.get.return_value.__aenter__.return_value = mock_response
            
            # 模拟URL刷新总是返回相同URL（刷新失败）
            provider._refresh_expired_url = AsyncMock(return_value=expired_url)
            
            # 执行下载
            result = await provider._download_file(expired_url, file_path)
            
            # 验证结果失败
            assert result == False
            
            # 验证刷新只被调用一次（达到重试限制）
            assert provider._refresh_expired_url.call_count <= 1

    def test_extract_song_id_from_api_url(self, provider):
        """测试从API URL中提取歌曲ID"""
        # 测试标准API URL
        api_url = "https://api.paugram.com/netease/?id=517567145"
        song_id = provider._extract_song_id_from_api_url(api_url)
        assert song_id == "517567145"
        
        # 测试无效URL
        invalid_url = "https://example.com/audio.mp3"
        song_id = provider._extract_song_id_from_api_url(invalid_url)
        assert song_id is None

    def test_extract_song_id_from_direct_url(self, provider):
        """测试从直接URL中提取歌曲ID"""
        # 对于直接音频URL，通常无法提取歌曲ID
        direct_url = "http://m701.music.126.net/20250816001402/test.mp3"
        song_id = provider._extract_song_id_from_direct_url(direct_url)
        assert song_id is None

    @pytest.mark.asyncio
    async def test_integration_download_with_url_refresh(self, provider):
        """集成测试：完整的下载流程包含URL刷新"""
        # 这个测试验证整个流程：提取音频信息 -> 下载 -> URL过期 -> 刷新 -> 重试下载
        url = "https://music.163.com/song?id=517567145"
        
        # 模拟音频信息
        mock_audio_info = AudioInfo(
            title="测试歌曲",
            duration=180,
            url="http://m701.music.126.net/expired/test.mp3",
            uploader="测试艺术家",
            file_format="mp3"
        )
        
        with patch.object(provider, '_extract_audio_info_impl', return_value=mock_audio_info):
            with patch.object(provider, '_download_file', return_value=True) as mock_download:
                # 执行下载
                success, audio_info, error = await provider._download_audio_impl(url)
                
                # 验证结果
                assert success == True
                assert audio_info is not None
                assert error is None
                mock_download.assert_called_once()
