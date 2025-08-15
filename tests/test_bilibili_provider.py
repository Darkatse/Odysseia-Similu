"""
Bilibili 提供者单元测试

测试 BilibiliProvider 的所有功能，包括 URL 检测、音频信息提取、下载功能和错误处理。
"""

import pytest
import asyncio
import os
import tempfile
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Optional

from similubot.core.interfaces import AudioInfo
from similubot.progress.base import ProgressCallback, ProgressInfo, ProgressStatus

# 尝试导入 BilibiliProvider，如果依赖不可用则跳过测试
try:
    from similubot.provider.bilibili_provider import BilibiliProvider
    BILIBILI_PROVIDER_AVAILABLE = True
except ImportError:
    BILIBILI_PROVIDER_AVAILABLE = False


@pytest.mark.skipif(not BILIBILI_PROVIDER_AVAILABLE, reason="bilibili-api-python 库未安装")
class TestBilibiliProvider:
    """Bilibili 提供者测试类"""
    
    def setup_method(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.provider = BilibiliProvider(self.temp_dir)
    
    def teardown_method(self):
        """清理测试环境"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_is_supported_url_valid_bv(self):
        """测试有效的 BV 号 URL 检测"""
        valid_urls = [
            "https://www.bilibili.com/video/BV1uv411q7Mv",
            "https://bilibili.com/video/BV1234567890",
            "http://www.bilibili.com/video/BVabcdefghij",
            "https://www.bilibili.com/video/BV1Ab2Cd3Ef4?p=1",
            "https://www.bilibili.com/video/BV1Ab2Cd3Ef4?t=123"
        ]
        
        for url in valid_urls:
            assert self.provider.is_supported_url(url), f"应该检测到 {url} 为有效的 Bilibili URL"
    
    def test_is_supported_url_valid_av(self):
        """测试有效的 AV 号 URL 检测"""
        valid_urls = [
            "https://www.bilibili.com/video/av123456",
            "https://bilibili.com/video/av987654321",
            "http://www.bilibili.com/video/av1",
        ]
        
        for url in valid_urls:
            assert self.provider.is_supported_url(url), f"应该检测到 {url} 为有效的 Bilibili URL"
    
    def test_is_supported_url_invalid(self):
        """测试无效 URL 检测"""
        invalid_urls = [
            "https://youtube.com/watch?v=abc123",
            "https://www.bilibili.com/bangumi/play/ep123456",
            "https://space.bilibili.com/123456",
            "https://www.bilibili.com/video/",
            "https://www.bilibili.com/video/BV",  # 不完整的 BV 号
            "https://www.bilibili.com/video/BV123",  # BV 号太短
            "https://www.bilibili.com/video/av",  # 不完整的 AV 号
            "not_a_url",
            "",
            "https://example.com/video.mp4"
        ]
        
        for url in invalid_urls:
            assert not self.provider.is_supported_url(url), f"不应该检测到 {url} 为有效的 Bilibili URL"
    
    def test_extract_video_id_bv(self):
        """测试从 BV 号 URL 提取视频 ID"""
        test_cases = [
            ("https://www.bilibili.com/video/BV1uv411q7Mv", "BV1uv411q7Mv"),
            ("https://bilibili.com/video/BV1234567890?p=1", "BV1234567890"),
            ("http://www.bilibili.com/video/BVabcdefghij?t=123", "BVabcdefghij"),
        ]
        
        for url, expected_id in test_cases:
            video_id = self.provider._extract_video_id(url)
            assert video_id == expected_id, f"从 {url} 应该提取到 {expected_id}，实际得到 {video_id}"
    
    def test_extract_video_id_av(self):
        """测试从 AV 号 URL 提取视频 ID"""
        test_cases = [
            ("https://www.bilibili.com/video/av123456", "av123456"),
            ("https://bilibili.com/video/av987654321", "av987654321"),
            ("http://www.bilibili.com/video/av1", "av1"),
        ]
        
        for url, expected_id in test_cases:
            video_id = self.provider._extract_video_id(url)
            assert video_id == expected_id, f"从 {url} 应该提取到 {expected_id}，实际得到 {video_id}"
    
    def test_extract_video_id_invalid(self):
        """测试从无效 URL 提取视频 ID"""
        invalid_urls = [
            "https://youtube.com/watch?v=abc123",
            "https://www.bilibili.com/bangumi/play/ep123456",
            "not_a_url",
            ""
        ]
        
        for url in invalid_urls:
            video_id = self.provider._extract_video_id(url)
            assert video_id is None, f"从无效 URL {url} 应该返回 None，实际得到 {video_id}"
    
    def test_extract_video_id_short_link(self):
        """测试短链接处理（同步版本）"""
        short_urls = [
            "https://b23.tv/abc123",
            "https://bili2233.cn/xyz789"
        ]

        for url in short_urls:
            video_id = self.provider._extract_video_id(url)
            # 短链接应该返回 None，因为需要额外的重定向解析
            assert video_id is None, f"短链接 {url} 应该返回 None 以表示需要进一步处理"

    @pytest.mark.asyncio
    async def test_resolve_short_link_success(self):
        """测试成功解析短链接"""
        short_url = "https://b23.tv/abc123"
        expected_redirect = "https://www.bilibili.com/video/BV1uv411q7Mv"

        # 模拟HTTP响应
        mock_response = Mock()
        mock_response.status = 302
        mock_response.headers = {'Location': expected_redirect}

        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)

        mock_session = Mock()
        mock_session.head = Mock(return_value=mock_context_manager)

        mock_session_context = AsyncMock()
        mock_session_context.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_context.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession', return_value=mock_session_context):
            result = await self.provider._resolve_short_link(short_url)

        assert result == expected_redirect
        mock_session.head.assert_called_once()

    @pytest.mark.asyncio
    async def test_resolve_short_link_invalid_redirect(self):
        """测试短链接重定向到无效URL"""
        short_url = "https://b23.tv/abc123"
        invalid_redirect = "https://example.com/not-bilibili"

        # 模拟HTTP响应
        mock_response = Mock()
        mock_response.status = 302
        mock_response.headers = {'Location': invalid_redirect}

        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)

        mock_session = Mock()
        mock_session.head = Mock(return_value=mock_context_manager)

        mock_session_context = AsyncMock()
        mock_session_context.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_context.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession', return_value=mock_session_context):
            result = await self.provider._resolve_short_link(short_url)

        assert result is None

    @pytest.mark.asyncio
    async def test_resolve_short_link_no_redirect(self):
        """测试短链接没有重定向"""
        short_url = "https://b23.tv/abc123"

        # 模拟HTTP响应 - 200状态码，不是重定向
        mock_response = Mock()
        mock_response.status = 200

        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)

        mock_session = Mock()
        mock_session.head = Mock(return_value=mock_context_manager)

        mock_session_context = AsyncMock()
        mock_session_context.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_context.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession', return_value=mock_session_context):
            result = await self.provider._resolve_short_link(short_url)

        assert result is None

    @pytest.mark.asyncio
    async def test_resolve_short_link_missing_location_header(self):
        """测试短链接重定向响应缺少Location头"""
        short_url = "https://b23.tv/abc123"

        # 模拟HTTP响应 - 302状态码但没有Location头
        mock_response = Mock()
        mock_response.status = 302
        mock_response.headers = {}

        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)

        mock_session = Mock()
        mock_session.head = Mock(return_value=mock_context_manager)

        mock_session_context = AsyncMock()
        mock_session_context.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_context.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession', return_value=mock_session_context):
            result = await self.provider._resolve_short_link(short_url)

        assert result is None

    @pytest.mark.asyncio
    async def test_resolve_short_link_timeout(self):
        """测试短链接解析超时"""
        short_url = "https://b23.tv/abc123"

        with patch('aiohttp.ClientSession', side_effect=asyncio.TimeoutError("Request timeout")):
            result = await self.provider._resolve_short_link(short_url)

        assert result is None

    @pytest.mark.asyncio
    async def test_resolve_short_link_network_error(self):
        """测试短链接解析网络错误"""
        short_url = "https://b23.tv/abc123"

        with patch('aiohttp.ClientSession', side_effect=aiohttp.ClientError("Network error")):
            result = await self.provider._resolve_short_link(short_url)

        assert result is None

    def test_is_valid_bilibili_redirect(self):
        """测试Bilibili重定向URL验证"""
        valid_urls = [
            "https://www.bilibili.com/video/BV1uv411q7Mv",
            "https://bilibili.com/video/BV1234567890",
            "http://www.bilibili.com/video/BVabcdefghij",
            "https://www.bilibili.com/video/av123456",
            "https://bilibili.com/video/av987654321",
        ]

        invalid_urls = [
            "https://example.com/video",
            "https://youtube.com/watch?v=abc123",
            "https://www.bilibili.com/bangumi/play/ep123456",
            "https://space.bilibili.com/123456",
            "https://b23.tv/abc123",  # 短链接不应该被认为是有效的重定向目标
            "https://bili2233.cn/xyz789",
        ]

        for url in valid_urls:
            assert self.provider._is_valid_bilibili_redirect(url), f"应该认为 {url} 是有效的Bilibili重定向URL"

        for url in invalid_urls:
            assert not self.provider._is_valid_bilibili_redirect(url), f"不应该认为 {url} 是有效的Bilibili重定向URL"

    @pytest.mark.asyncio
    async def test_extract_video_id_async_short_link_success(self):
        """测试异步提取视频ID - 短链接成功解析"""
        short_url = "https://b23.tv/abc123"
        resolved_url = "https://www.bilibili.com/video/BV1uv411q7Mv"
        expected_video_id = "BV1uv411q7Mv"

        with patch.object(self.provider, '_resolve_short_link', return_value=resolved_url):
            result = await self.provider._extract_video_id_async(short_url)

        assert result == expected_video_id

    @pytest.mark.asyncio
    async def test_extract_video_id_async_short_link_failure(self):
        """测试异步提取视频ID - 短链接解析失败"""
        short_url = "https://b23.tv/abc123"

        with patch.object(self.provider, '_resolve_short_link', return_value=None):
            result = await self.provider._extract_video_id_async(short_url)

        assert result is None

    @pytest.mark.asyncio
    async def test_extract_video_id_async_normal_url(self):
        """测试异步提取视频ID - 普通URL"""
        normal_url = "https://www.bilibili.com/video/BV1uv411q7Mv"
        expected_video_id = "BV1uv411q7Mv"

        result = await self.provider._extract_video_id_async(normal_url)

        assert result == expected_video_id

    def test_extract_page_index_default(self):
        """测试默认页面索引提取（无 p 参数）"""
        urls_without_p = [
            "https://www.bilibili.com/video/BV1uv411q7Mv",
            "https://bilibili.com/video/BV1234567890?t=123",
            "https://www.bilibili.com/video/BV1Ab2Cd3Ef4?vd_source=abc123"
        ]

        for url in urls_without_p:
            page_index = self.provider._extract_page_index(url)
            assert page_index == 0, f"URL {url} 应该返回默认页面索引 0，实际得到 {page_index}"

    def test_extract_page_index_with_p_parameter(self):
        """测试带 p 参数的页面索引提取"""
        test_cases = [
            ("https://www.bilibili.com/video/BV1uv411q7Mv?p=1", 0),  # p=1 -> index=0
            ("https://www.bilibili.com/video/BV1234567890?p=5", 4),  # p=5 -> index=4
            ("https://www.bilibili.com/video/BV1Ab2Cd3Ef4?p=26", 25),  # p=26 -> index=25
            ("https://www.bilibili.com/video/BV1uv411q7Mv?p=1&t=123", 0),  # 多参数
            ("https://www.bilibili.com/video/BV1uv411q7Mv?vd_source=abc&p=10&spm_id_from=333", 9),  # 多参数
        ]

        for url, expected_index in test_cases:
            page_index = self.provider._extract_page_index(url)
            assert page_index == expected_index, f"URL {url} 应该返回页面索引 {expected_index}，实际得到 {page_index}"

    def test_extract_page_index_invalid_values(self):
        """测试无效 p 参数值的处理"""
        invalid_urls = [
            "https://www.bilibili.com/video/BV1uv411q7Mv?p=0",  # p=0 应该转换为 index=0 (最小值)
            "https://www.bilibili.com/video/BV1uv411q7Mv?p=-1",  # 负数应该转换为 index=0
            "https://www.bilibili.com/video/BV1uv411q7Mv?p=abc",  # 非数字应该使用默认值
            "https://www.bilibili.com/video/BV1uv411q7Mv?p=",  # 空值应该使用默认值
        ]

        for url in invalid_urls:
            page_index = self.provider._extract_page_index(url)
            assert page_index == 0, f"无效 URL {url} 应该返回默认页面索引 0，实际得到 {page_index}"
    
    def test_create_bilibili_video_object_bv(self):
        """测试创建 BV 号的 Bilibili Video 对象"""
        with patch('similubot.provider.bilibili_provider.bilibili_video.Video') as mock_video:
            mock_instance = Mock()
            mock_video.return_value = mock_instance
            
            result = self.provider._create_bilibili_video_object("BV1uv411q7Mv")
            
            mock_video.assert_called_once_with(bvid="BV1uv411q7Mv")
            assert result == mock_instance
    
    def test_create_bilibili_video_object_av(self):
        """测试创建 AV 号的 Bilibili Video 对象"""
        with patch('similubot.provider.bilibili_provider.bilibili_video.Video') as mock_video:
            mock_instance = Mock()
            mock_video.return_value = mock_instance
            
            result = self.provider._create_bilibili_video_object("av123456")
            
            mock_video.assert_called_once_with(aid=123456)
            assert result == mock_instance
    
    def test_create_bilibili_video_object_invalid(self):
        """测试创建无效视频 ID 的 Bilibili Video 对象"""
        with pytest.raises(ValueError, match="不支持的视频 ID 格式"):
            self.provider._create_bilibili_video_object("invalid_id")
    
    @pytest.mark.asyncio
    async def test_extract_audio_info_success(self):
        """测试成功提取音频信息（单P视频）"""
        mock_video_info = {
            'title': '测试视频标题',
            'duration': 300,
            'owner': {'name': '测试UP主'},
            'pic': 'https://example.com/thumbnail.jpg'
        }

        mock_pages_info = [
            {'part': '测试视频标题', 'duration': 300}
        ]

        with patch.object(self.provider, '_extract_video_id_async', return_value="BV1uv411q7Mv"), \
             patch.object(self.provider, '_extract_page_index', return_value=0), \
             patch.object(self.provider, '_create_bilibili_video_object') as mock_create_video, \
             patch('asyncio.run') as mock_asyncio_run:

            mock_video = Mock()
            mock_create_video.return_value = mock_video

            # 第一次调用返回视频信息，第二次调用返回页面信息
            mock_asyncio_run.side_effect = [mock_video_info, mock_pages_info]

            result = await self.provider._extract_audio_info_impl("https://www.bilibili.com/video/BV1uv411q7Mv")

            assert result is not None
            assert result.title == '测试视频标题'
            assert result.duration == 300
            assert result.uploader == '测试UP主'
            assert result.thumbnail_url == 'https://example.com/thumbnail.jpg'
            assert result.url == "https://www.bilibili.com/video/BV1uv411q7Mv"
    
    @pytest.mark.asyncio
    async def test_extract_audio_info_invalid_url(self):
        """测试提取音频信息时 URL 无效"""
        with patch.object(self.provider, '_extract_video_id_async', return_value=None):
            result = await self.provider._extract_audio_info_impl("https://invalid.com/video")
            assert result is None
    
    @pytest.mark.asyncio
    async def test_extract_audio_info_exception(self):
        """测试提取音频信息时发生异常"""
        with patch.object(self.provider, '_extract_video_id_async', return_value="BV1uv411q7Mv"), \
             patch.object(self.provider, '_create_bilibili_video_object', side_effect=Exception("测试异常")):

            result = await self.provider._extract_audio_info_impl("https://www.bilibili.com/video/BV1uv411q7Mv")
            assert result is None

    @pytest.mark.asyncio
    async def test_extract_audio_info_short_link_success(self):
        """测试通过短链接成功提取音频信息"""
        short_url = "https://b23.tv/abc123"
        resolved_url = "https://www.bilibili.com/video/BV1uv411q7Mv"

        mock_video_info = {
            'title': '测试视频标题',
            'duration': 300,
            'owner': {'name': '测试UP主'},
            'pic': 'https://example.com/thumbnail.jpg'
        }

        mock_pages_info = [
            {'part': '测试视频标题', 'duration': 300}
        ]

        with patch.object(self.provider, '_resolve_short_link', return_value=resolved_url), \
             patch.object(self.provider, '_extract_page_index', return_value=0), \
             patch.object(self.provider, '_create_bilibili_video_object') as mock_create_video, \
             patch('asyncio.run') as mock_asyncio_run:

            mock_video = Mock()
            mock_create_video.return_value = mock_video

            # 第一次调用返回视频信息，第二次调用返回页面信息
            mock_asyncio_run.side_effect = [mock_video_info, mock_pages_info]

            result = await self.provider._extract_audio_info_impl(short_url)

            assert result is not None
            assert result.title == '测试视频标题'
            assert result.duration == 300
            assert result.uploader == '测试UP主'
            assert result.thumbnail_url == 'https://example.com/thumbnail.jpg'
            assert result.url == short_url  # 应该保持原始短链接URL

    @pytest.mark.asyncio
    async def test_extract_audio_info_short_link_resolution_failure(self):
        """测试短链接解析失败时的音频信息提取"""
        short_url = "https://b23.tv/abc123"

        with patch.object(self.provider, '_resolve_short_link', return_value=None):
            result = await self.provider._extract_audio_info_impl(short_url)

        assert result is None

    @pytest.mark.asyncio
    async def test_extract_audio_info_multi_part_video(self):
        """测试多P视频的音频信息提取"""
        mock_video_info = {
            'title': '测试合集视频',
            'duration': 1800,  # 总时长30分钟
            'owner': {'name': '测试UP主'},
            'pic': 'https://example.com/thumbnail.jpg'
        }

        mock_pages_info = [
            {'part': '第一部分', 'duration': 300},  # 5分钟
            {'part': '第二部分', 'duration': 450},  # 7.5分钟
            {'part': '第三部分', 'duration': 600},  # 10分钟
        ]

        with patch.object(self.provider, '_extract_video_id_async', return_value="BV1uv411q7Mv"), \
             patch.object(self.provider, '_extract_page_index', return_value=1), \
             patch.object(self.provider, '_create_bilibili_video_object') as mock_create_video, \
             patch('asyncio.run') as mock_asyncio_run:

            mock_video = Mock()
            mock_create_video.return_value = mock_video

            # 第一次调用返回视频信息，第二次调用返回页面信息
            mock_asyncio_run.side_effect = [mock_video_info, mock_pages_info]

            audio_info = await self.provider._extract_audio_info_impl("https://www.bilibili.com/video/BV1uv411q7Mv?p=2")

            assert audio_info is not None
            assert audio_info.title == '测试合集视频 - P2: 第二部分'  # 应该包含分P信息
            assert audio_info.duration == 450  # 应该是第二部分的时长，不是总时长
            assert audio_info.uploader == '测试UP主'
            assert audio_info.thumbnail_url == 'https://example.com/thumbnail.jpg'
            assert audio_info.url == "https://www.bilibili.com/video/BV1uv411q7Mv?p=2"

    @pytest.mark.asyncio
    async def test_extract_audio_info_page_index_out_of_range(self):
        """测试页面索引超出范围的处理"""
        mock_video_info = {
            'title': '测试视频',
            'duration': 300,
            'owner': {'name': '测试UP主'},
            'pic': 'https://example.com/thumbnail.jpg'
        }

        mock_pages_info = [
            {'part': '唯一部分', 'duration': 300}
        ]

        with patch.object(self.provider, '_extract_video_id_async', return_value="BV1uv411q7Mv"), \
             patch.object(self.provider, '_extract_page_index', return_value=5), \
             patch.object(self.provider, '_create_bilibili_video_object') as mock_create_video, \
             patch('asyncio.run') as mock_asyncio_run:

            mock_video = Mock()
            mock_create_video.return_value = mock_video

            # 第一次调用返回视频信息，第二次调用返回页面信息
            mock_asyncio_run.side_effect = [mock_video_info, mock_pages_info]

            audio_info = await self.provider._extract_audio_info_impl("https://www.bilibili.com/video/BV1uv411q7Mv?p=6")

            assert audio_info is not None
            assert audio_info.title == '唯一部分'  # 应该回退到第一页
            assert audio_info.duration == 300  # 应该是第一页的时长
            assert audio_info.uploader == '测试UP主'
    
    @pytest.mark.asyncio
    async def test_download_audio_stream_success(self):
        """测试成功下载音频流"""
        test_file_path = os.path.join(self.temp_dir, "test_audio.mp3")
        test_content = b"fake audio content"

        # 模拟进度回调
        progress_callback = Mock()
        progress_callback.update = AsyncMock()

        # 创建异步迭代器
        class MockAsyncIterator:
            def __init__(self, data):
                self.data = [data]
                self.index = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.index >= len(self.data):
                    raise StopAsyncIteration
                result = self.data[self.index]
                self.index += 1
                return result

        # 模拟 aiohttp 响应
        mock_response = Mock()
        mock_response.status = 200
        mock_response.headers = {'content-length': str(len(test_content))}
        mock_response.content.iter_chunked = Mock(return_value=MockAsyncIterator(test_content))

        # 创建正确的异步上下文管理器
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)

        mock_session = Mock()
        mock_session.get = Mock(return_value=mock_context_manager)

        # 创建会话的异步上下文管理器
        mock_session_context = AsyncMock()
        mock_session_context.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_context.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession', return_value=mock_session_context):
            result = await self.provider._download_audio_stream(
                "https://example.com/audio.mp3",
                test_file_path,
                progress_callback
            )

        assert result is True
        assert os.path.exists(test_file_path)

        # 验证文件内容
        with open(test_file_path, 'rb') as f:
            assert f.read() == test_content

        # 验证进度回调被调用
        assert progress_callback.update.called
    
    @pytest.mark.asyncio
    async def test_download_audio_stream_http_error(self):
        """测试下载音频流时 HTTP 错误"""
        test_file_path = os.path.join(self.temp_dir, "test_audio.mp3")
        
        # 模拟 HTTP 404 响应
        mock_response = Mock()
        mock_response.status = 404

        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)

        mock_session = Mock()
        mock_session.get = Mock(return_value=mock_context_manager)

        mock_session_context = AsyncMock()
        mock_session_context.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_context.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession', return_value=mock_session_context):
            result = await self.provider._download_audio_stream(
                "https://example.com/audio.mp3",
                test_file_path,
                None
            )
        
        assert result is False
        assert not os.path.exists(test_file_path)
    
    @pytest.mark.asyncio
    async def test_download_audio_stream_exception(self):
        """测试下载音频流时发生异常"""
        test_file_path = os.path.join(self.temp_dir, "test_audio.mp3")
        
        with patch('aiohttp.ClientSession', side_effect=Exception("网络错误")):
            result = await self.provider._download_audio_stream(
                "https://example.com/audio.mp3",
                test_file_path,
                None
            )
        
        assert result is False
        assert not os.path.exists(test_file_path)


    @pytest.mark.asyncio
    async def test_download_audio_impl_success(self):
        """测试完整的音频下载流程成功"""
        mock_video_info = {
            'title': '测试视频',
            'duration': 300,
            'owner': {'name': '测试UP主'},
            'pic': 'https://example.com/thumbnail.jpg'
        }

        mock_download_data = {
            'dash': {
                'audio': [{'base_url': 'https://example.com/audio.mp3', 'id': 30232}]
            }
        }

        # 模拟进度回调
        progress_callback = Mock()
        progress_callback.update = AsyncMock()

        with patch.object(self.provider, '_extract_video_id_async', return_value="BV1uv411q7Mv"), \
             patch.object(self.provider, '_extract_page_index', return_value=0), \
             patch.object(self.provider, '_create_bilibili_video_object') as mock_create_video, \
             patch.object(self.provider, '_download_audio_stream', return_value=True), \
             patch('similubot.provider.bilibili_provider.VideoDownloadURLDataDetecter') as mock_detector_class, \
             patch('asyncio.run') as mock_asyncio_run, \
             patch('os.path.getsize', return_value=1024):

            mock_video = Mock()
            mock_create_video.return_value = mock_video

            # 模拟页面信息
            mock_pages_info = [{'part': '测试视频', 'duration': 300}]

            # 第一次调用返回视频信息，第二次返回页面信息，第三次调用返回下载数据
            mock_asyncio_run.side_effect = [mock_video_info, mock_pages_info, mock_download_data]

            # 模拟检测器
            mock_detector = Mock()
            mock_detector.check_video_and_audio_stream.return_value = True

            # 模拟音频流对象
            from similubot.provider.bilibili_provider import AudioStreamDownloadURL
            mock_audio_stream = Mock(spec=AudioStreamDownloadURL)
            mock_audio_stream.url = 'https://example.com/audio.mp3'

            mock_detector.detect_best_streams.return_value = [None, mock_audio_stream]
            mock_detector_class.return_value = mock_detector

            success, audio_info, error = await self.provider._download_audio_impl(
                "https://www.bilibili.com/video/BV1uv411q7Mv",
                progress_callback
            )

            assert success is True
            assert audio_info is not None
            assert error is None
            assert audio_info.title == '测试视频'
            assert audio_info.uploader == '测试UP主'
            assert audio_info.file_format == 'mp3'
            assert progress_callback.update.called

    @pytest.mark.asyncio
    async def test_download_audio_impl_page_index_parameter(self):
        """测试下载时正确传递 page_index 参数"""
        mock_video_info = {'title': '测试视频', 'duration': 300, 'owner': {'name': '测试UP主'}}
        mock_download_data = {'dash': {'audio': [{'base_url': 'https://example.com/audio.mp3', 'id': 30232}]}}

        with patch.object(self.provider, '_extract_video_id_async', return_value="BV1uv411q7Mv"), \
             patch.object(self.provider, '_create_bilibili_video_object') as mock_create_video, \
             patch.object(self.provider, '_download_audio_stream', return_value=True), \
             patch('similubot.provider.bilibili_provider.VideoDownloadURLDataDetecter') as mock_detector_class, \
             patch('asyncio.run') as mock_asyncio_run, \
             patch('os.path.getsize', return_value=1024):

            mock_video = Mock()
            mock_create_video.return_value = mock_video

            # 模拟页面信息
            mock_pages_info = [{'part': '测试视频', 'duration': 300}]

            # 第一次调用返回视频信息，第二次返回页面信息，第三次返回下载数据
            mock_asyncio_run.side_effect = [mock_video_info, mock_pages_info, mock_download_data]

            mock_detector = Mock()
            mock_detector.check_video_and_audio_stream.return_value = True

            from similubot.provider.bilibili_provider import AudioStreamDownloadURL
            mock_audio_stream = Mock(spec=AudioStreamDownloadURL)
            mock_audio_stream.url = 'https://example.com/audio.mp3'
            mock_detector.detect_best_streams.return_value = [None, mock_audio_stream]
            mock_detector_class.return_value = mock_detector

            success, audio_info, error = await self.provider._download_audio_impl(
                "https://www.bilibili.com/video/BV1uv411q7Mv",
                None
            )

            assert success is True
            assert audio_info is not None
            assert error is None

            # 验证 asyncio.run 被调用了三次（一次获取视频信息，一次获取页面信息，一次获取下载链接）
            assert mock_asyncio_run.call_count == 3

    @pytest.mark.asyncio
    async def test_download_audio_impl_no_audio_stream(self):
        """测试下载时没有找到音频流"""
        mock_video_info = {'title': '测试视频', 'duration': 300, 'owner': {'name': '测试UP主'}}
        mock_download_data = {'dash': {'video': []}}

        with patch.object(self.provider, '_extract_video_id_async', return_value="BV1uv411q7Mv"), \
             patch.object(self.provider, '_extract_page_index', return_value=0), \
             patch.object(self.provider, '_create_bilibili_video_object'), \
             patch('similubot.provider.bilibili_provider.VideoDownloadURLDataDetecter') as mock_detector_class, \
             patch('asyncio.run') as mock_asyncio_run:

            # 模拟页面信息
            mock_pages_info = [{'part': '测试视频', 'duration': 300}]
            mock_asyncio_run.side_effect = [mock_video_info, mock_pages_info, mock_download_data]

            mock_detector = Mock()
            mock_detector.check_video_and_audio_stream.return_value = True
            mock_detector.detect_best_streams.return_value = [None, None]  # 没有音频流
            mock_detector_class.return_value = mock_detector

            success, audio_info, error = await self.provider._download_audio_impl(
                "https://www.bilibili.com/video/BV1uv411q7Mv",
                None
            )

            assert success is False
            assert audio_info is None
            assert "未找到可用的音频流" in error

    @pytest.mark.asyncio
    async def test_download_audio_impl_not_dash_format(self):
        """测试下载时视频不支持音视频分离"""
        mock_video_info = {'title': '测试视频', 'duration': 300, 'owner': {'name': '测试UP主'}}
        mock_download_data = {'durl': [{'url': 'https://example.com/video.flv'}]}

        with patch.object(self.provider, '_extract_video_id_async', return_value="BV1uv411q7Mv"), \
             patch.object(self.provider, '_extract_page_index', return_value=0), \
             patch.object(self.provider, '_create_bilibili_video_object'), \
             patch('similubot.provider.bilibili_provider.VideoDownloadURLDataDetecter') as mock_detector_class, \
             patch('asyncio.run') as mock_asyncio_run:

            # 模拟页面信息
            mock_pages_info = [{'part': '测试视频', 'duration': 300}]
            mock_asyncio_run.side_effect = [mock_video_info, mock_pages_info, mock_download_data]

            mock_detector = Mock()
            mock_detector.check_video_and_audio_stream.return_value = False
            mock_detector_class.return_value = mock_detector

            success, audio_info, error = await self.provider._download_audio_impl(
                "https://www.bilibili.com/video/BV1uv411q7Mv",
                None
            )

            assert success is False
            assert audio_info is None
            assert "该视频不支持音视频分离下载" in error

    @pytest.mark.asyncio
    async def test_download_audio_impl_download_failure(self):
        """测试音频文件下载失败"""
        mock_video_info = {'title': '测试视频', 'duration': 300, 'owner': {'name': '测试UP主'}}
        mock_download_data = {'dash': {'audio': [{'base_url': 'https://example.com/audio.mp3', 'id': 30232}]}}

        with patch.object(self.provider, '_extract_video_id_async', return_value="BV1uv411q7Mv"), \
             patch.object(self.provider, '_extract_page_index', return_value=0), \
             patch.object(self.provider, '_create_bilibili_video_object'), \
             patch.object(self.provider, '_download_audio_stream', return_value=False), \
             patch('similubot.provider.bilibili_provider.VideoDownloadURLDataDetecter') as mock_detector_class, \
             patch('asyncio.run') as mock_asyncio_run:

            # 模拟页面信息
            mock_pages_info = [{'part': '测试视频', 'duration': 300}]
            mock_asyncio_run.side_effect = [mock_video_info, mock_pages_info, mock_download_data]

            mock_detector = Mock()
            mock_detector.check_video_and_audio_stream.return_value = True

            from similubot.provider.bilibili_provider import AudioStreamDownloadURL
            mock_audio_stream = Mock(spec=AudioStreamDownloadURL)
            mock_audio_stream.url = 'https://example.com/audio.mp3'
            mock_detector.detect_best_streams.return_value = [None, mock_audio_stream]
            mock_detector_class.return_value = mock_detector

            success, audio_info, error = await self.provider._download_audio_impl(
                "https://www.bilibili.com/video/BV1uv411q7Mv",
                None
            )

            assert success is False
            assert audio_info is None
            assert "音频文件下载失败" in error

    @pytest.mark.asyncio
    async def test_download_audio_impl_multi_part_video_with_short_link(self):
        """测试通过短链接下载多P视频"""
        short_url = "https://b23.tv/abc123"
        resolved_url = "https://www.bilibili.com/video/BV1uv411q7Mv?p=2"

        mock_video_info = {
            'title': '测试合集视频',
            'duration': 1800,  # 总时长30分钟
            'owner': {'name': '测试UP主'},
            'pic': 'https://example.com/thumbnail.jpg'
        }

        mock_pages_info = [
            {'part': '第一部分', 'duration': 300},  # 5分钟
            {'part': '第二部分', 'duration': 450},  # 7.5分钟
            {'part': '第三部分', 'duration': 600},  # 10分钟
        ]

        mock_download_data = {'dash': {'audio': [{'base_url': 'https://example.com/audio.mp3', 'id': 30232}]}}

        with patch.object(self.provider, '_resolve_short_link', return_value=resolved_url), \
             patch.object(self.provider, '_extract_page_index', return_value=1), \
             patch.object(self.provider, '_create_bilibili_video_object') as mock_create_video, \
             patch.object(self.provider, '_download_audio_stream', return_value=True), \
             patch('similubot.provider.bilibili_provider.VideoDownloadURLDataDetecter') as mock_detector_class, \
             patch('asyncio.run') as mock_asyncio_run, \
             patch('os.path.getsize', return_value=1024):

            mock_video = Mock()
            mock_create_video.return_value = mock_video

            # 第一次调用返回视频信息，第二次返回页面信息，第三次返回下载数据
            mock_asyncio_run.side_effect = [mock_video_info, mock_pages_info, mock_download_data]

            mock_detector = Mock()
            mock_detector.check_video_and_audio_stream.return_value = True

            # 模拟音频流对象
            from similubot.provider.bilibili_provider import AudioStreamDownloadURL
            mock_audio_stream = Mock(spec=AudioStreamDownloadURL)
            mock_audio_stream.url = 'https://example.com/audio.mp3'

            mock_detector.detect_best_streams.return_value = [None, mock_audio_stream]
            mock_detector_class.return_value = mock_detector

            success, audio_info, error = await self.provider._download_audio_impl(short_url)

            assert success is True
            assert audio_info is not None
            assert error is None
            assert audio_info.title == '测试合集视频 - P2: 第二部分'  # 应该包含分P信息
            assert audio_info.duration == 450  # 应该是第二部分的时长，不是总时长
            assert audio_info.uploader == '测试UP主'
            assert audio_info.file_format == 'mp3'
            assert audio_info.url == short_url  # 应该保持原始短链接URL


@pytest.mark.skipif(not BILIBILI_PROVIDER_AVAILABLE, reason="测试依赖不可用时的行为")
class TestBilibiliProviderUnavailable:
    """测试 Bilibili 提供者依赖不可用时的行为"""

    def test_import_error_handling(self):
        """测试导入错误处理"""
        # 当 bilibili-api-python 不可用时，导入应该失败
        with pytest.raises(ImportError):
            from similubot.provider.bilibili_provider import BilibiliProvider
            BilibiliProvider("./temp")
