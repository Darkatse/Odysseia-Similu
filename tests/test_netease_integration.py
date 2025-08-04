"""
网易云音乐集成测试 - 测试完整的NetEase功能集成

包含搜索功能、提供者集成、UI交互和队列集成的全面测试。
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import discord
from discord.ext import commands

from similubot.utils.netease_search import NetEaseSearchClient, search_songs, get_song_details
from similubot.core.interfaces import NetEaseSearchResult, AudioInfo
from similubot.provider.netease_provider import NetEaseProvider
from similubot.ui.button_interactions import InteractionManager, InteractionResult
from similubot.commands.music_commands import MusicCommands


class TestNetEaseSearchClient:
    """测试网易云音乐搜索客户端"""

    @pytest.fixture
    def client(self):
        """创建搜索客户端实例"""
        return NetEaseSearchClient()

    @pytest.fixture
    def mock_search_response(self):
        """模拟搜索API响应"""
        return {
            "result": {
                "songs": [
                    {
                        "id": 517567145,
                        "name": "初登校",
                        "duration": 225000,  # 毫秒
                        "artists": [{"name": "橋本由香利"}],
                        "album": {
                            "name": "ひなこのーと COMPLETE SOUNDTRACK",
                            "picUrl": "http://example.com/cover.jpg"
                        }
                    },
                    {
                        "id": 123456789,
                        "name": "测试歌曲",
                        "duration": 180000,
                        "artists": [{"name": "测试艺术家"}],
                        "album": {
                            "name": "测试专辑",
                            "picUrl": "http://example.com/cover2.jpg"
                        }
                    }
                ]
            }
        }

    @pytest.fixture
    def mock_song_details_response(self):
        """模拟歌曲详情API响应"""
        return {
            "id": 517567145,
            "title": "初登校",
            "artist": "橋本由香利",
            "album": "ひなこのーと COMPLETE SOUNDTRACK",
            "cover": "http://example.com/cover.jpg",
            "lyric": "歌词内容",
            "sub_lyric": "翻译歌词内容",
            "link": "http://music.163.com/song/media/outer/url?id=517567145.mp3"
        }

    @pytest.mark.asyncio
    async def test_search_songs_success(self, client, mock_search_response):
        """测试成功搜索歌曲"""
        with patch('aiohttp.ClientSession') as mock_session_class:
            # 设置模拟响应
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_search_response)

            # 设置模拟会话
            mock_session = AsyncMock()
            mock_session.get.return_value.__aenter__.return_value = mock_response
            mock_session_class.return_value.__aenter__.return_value = mock_session

            # 执行搜索
            results = await client.search_songs("初登校", limit=2)

            # 验证结果
            assert len(results) == 2
            assert isinstance(results[0], NetEaseSearchResult)
            assert results[0].song_id == "517567145"
            assert results[0].title == "初登校"
            assert results[0].artist == "橋本由香利"
            assert results[0].album == "ひなこのーと COMPLETE SOUNDTRACK"
            assert results[0].duration == 225  # 转换为秒
            assert results[0].cover_url == "http://example.com/cover.jpg"

    @pytest.mark.asyncio
    async def test_search_songs_no_results(self, client):
        """测试搜索无结果"""
        with patch('aiohttp.ClientSession') as mock_session_class:
            # 设置空结果响应
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"result": {"songs": []}})

            # 设置模拟会话
            mock_session = AsyncMock()
            mock_session.get.return_value.__aenter__.return_value = mock_response
            mock_session_class.return_value.__aenter__.return_value = mock_session

            # 执行搜索
            results = await client.search_songs("不存在的歌曲")

            # 验证结果
            assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_songs_api_error(self, client):
        """测试搜索API错误"""
        with patch('aiohttp.ClientSession') as mock_session_class:
            # 设置错误响应
            mock_response = AsyncMock()
            mock_response.status = 500

            # 设置模拟会话
            mock_session = AsyncMock()
            mock_session.get.return_value.__aenter__.return_value = mock_response
            mock_session_class.return_value.__aenter__.return_value = mock_session

            # 执行搜索
            results = await client.search_songs("测试")

            # 验证结果
            assert len(results) == 0

    @pytest.mark.asyncio
    async def test_get_song_details_success(self, client, mock_song_details_response):
        """测试成功获取歌曲详情"""
        with patch('aiohttp.ClientSession') as mock_session_class:
            # 设置模拟响应
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_song_details_response)

            # 设置模拟会话
            mock_session = AsyncMock()
            mock_session.get.return_value.__aenter__.return_value = mock_response
            mock_session_class.return_value.__aenter__.return_value = mock_session

            # 执行获取详情
            details = await client.get_song_details("517567145")

            # 验证结果
            assert details is not None
            assert details["id"] == 517567145
            assert details["title"] == "初登校"
            assert details["artist"] == "橋本由香利"
            assert details["link"] == "http://music.163.com/song/media/outer/url?id=517567145.mp3"

    @pytest.mark.asyncio
    async def test_get_song_details_not_found(self, client):
        """测试获取不存在的歌曲详情"""
        with patch('aiohttp.ClientSession') as mock_session_class:
            # 设置404响应
            mock_response = AsyncMock()
            mock_response.status = 404

            # 设置模拟会话
            mock_session = AsyncMock()
            mock_session.get.return_value.__aenter__.return_value = mock_response
            mock_session_class.return_value.__aenter__.return_value = mock_session

            # 执行获取详情
            details = await client.get_song_details("999999999")

            # 验证结果
            assert details is None

    def test_clean_search_query(self, client):
        """测试搜索查询清理"""
        # 测试各种输入
        assert client._clean_search_query("初音未来") == "初音未来"
        assert client._clean_search_query("  初音未来  ") == "初音未来"
        assert client._clean_search_query("初音@未来#") == "初音 未来"
        assert client._clean_search_query("") == ""
        assert client._clean_search_query("   ") == ""

    def test_get_playback_url(self, client):
        """测试获取播放URL"""
        song_id = "517567145"
        
        # 测试API URL
        api_url = client.get_playback_url(song_id, use_api=True)
        assert api_url == f"https://api.paugram.com/netease/?id={song_id}"
        
        # 测试直接URL
        direct_url = client.get_playback_url(song_id, use_api=False)
        assert direct_url == f"https://music.163.com/song/media/outer/url?id={song_id}.mp3"


class TestNetEaseProvider:
    """测试网易云音乐提供者"""

    @pytest.fixture
    def provider(self):
        """创建提供者实例"""
        return NetEaseProvider("./test_temp")

    @pytest.fixture
    def mock_song_details(self):
        """模拟歌曲详情"""
        return {
            "id": 517567145,
            "title": "初登校",
            "artist": "橋本由香利",
            "album": "ひなこのーと COMPLETE SOUNDTRACK",
            "cover": "http://example.com/cover.jpg",
            "link": "http://music.163.com/song/media/outer/url?id=517567145.mp3"
        }

    def test_is_supported_url(self, provider):
        """测试URL支持检测"""
        # 支持的URL格式
        supported_urls = [
            "https://music.163.com/song?id=517567145",
            "http://music.163.com/#/song?id=517567145",
            "https://music.163.com/m/song?id=123456",
            "https://y.music.163.com/m/song?id=789012"
        ]
        
        for url in supported_urls:
            assert provider.is_supported_url(url), f"应该支持URL: {url}"

        # 不支持的URL格式
        unsupported_urls = [
            "https://www.youtube.com/watch?v=123",
            "https://example.com/song?id=123",
            "not_a_url",
            ""
        ]
        
        for url in unsupported_urls:
            assert not provider.is_supported_url(url), f"不应该支持URL: {url}"

    def test_extract_song_id(self, provider):
        """测试歌曲ID提取"""
        test_cases = [
            ("https://music.163.com/song?id=517567145", "517567145"),
            ("http://music.163.com/#/song?id=123456", "123456"),
            ("https://music.163.com/m/song?id=789012&other=param", "789012"),
            ("invalid_url", None),
            ("", None)
        ]
        
        for url, expected_id in test_cases:
            result = provider._extract_song_id(url)
            assert result == expected_id, f"URL {url} 应该提取出ID {expected_id}，实际得到 {result}"

    @pytest.mark.asyncio
    async def test_extract_audio_info_success(self, provider, mock_song_details):
        """测试成功提取音频信息"""
        url = "https://music.163.com/song?id=517567145"
        
        with patch('similubot.utils.netease_search.get_song_details', new_callable=AsyncMock) as mock_get_details:
            mock_get_details.return_value = mock_song_details
            
            # 执行提取
            audio_info = await provider._extract_audio_info_impl(url)
            
            # 验证结果
            assert audio_info is not None
            assert isinstance(audio_info, AudioInfo)
            assert audio_info.title == "初登校"
            assert audio_info.uploader == "橋本由香利"
            assert audio_info.url == "http://music.163.com/song/media/outer/url?id=517567145.mp3"
            assert audio_info.thumbnail_url == "http://example.com/cover.jpg"
            assert audio_info.file_format == "mp3"

    @pytest.mark.asyncio
    async def test_extract_audio_info_invalid_url(self, provider):
        """测试无效URL的音频信息提取"""
        url = "https://invalid.com/song"
        
        # 执行提取
        audio_info = await provider._extract_audio_info_impl(url)
        
        # 验证结果
        assert audio_info is None

    @pytest.mark.asyncio
    async def test_extract_audio_info_api_failure(self, provider):
        """测试API失败的音频信息提取"""
        url = "https://music.163.com/song?id=517567145"
        
        with patch('similubot.utils.netease_search.get_song_details', new_callable=AsyncMock) as mock_get_details:
            mock_get_details.return_value = None
            
            # 执行提取
            audio_info = await provider._extract_audio_info_impl(url)
            
            # 验证结果
            assert audio_info is None


class TestNetEaseSearchResult:
    """测试网易云搜索结果数据类"""

    @pytest.fixture
    def search_result(self):
        """创建搜索结果实例"""
        return NetEaseSearchResult(
            song_id="517567145",
            title="初登校",
            artist="橋本由香利",
            album="ひなこのーと COMPLETE SOUNDTRACK",
            cover_url="http://example.com/cover.jpg",
            duration=225
        )

    def test_get_display_name(self, search_result):
        """测试获取显示名称"""
        expected = "初登校 - 橋本由香利"
        assert search_result.get_display_name() == expected

    def test_get_full_display_info(self, search_result):
        """测试获取完整显示信息"""
        expected = "初登校 - 橋本由香利 (ひなこのーと COMPLETE SOUNDTRACK)"
        assert search_result.get_full_display_info() == expected

    def test_get_full_display_info_same_title_album(self):
        """测试标题和专辑相同时的完整显示信息"""
        result = NetEaseSearchResult(
            song_id="123",
            title="测试歌曲",
            artist="测试艺术家",
            album="测试歌曲"  # 与标题相同
        )
        expected = "测试歌曲 - 测试艺术家"
        assert result.get_full_display_info() == expected

    def test_format_duration(self, search_result):
        """测试时长格式化"""
        assert search_result.format_duration() == "3:45"

    def test_format_duration_no_duration(self):
        """测试无时长的格式化"""
        result = NetEaseSearchResult(
            song_id="123",
            title="测试歌曲",
            artist="测试艺术家",
            album="测试专辑"
        )
        assert result.format_duration() == "未知时长"

    def test_format_duration_edge_cases(self):
        """测试时长格式化的边界情况"""
        # 测试不同时长
        test_cases = [
            (0, "0:00"),
            (59, "0:59"),
            (60, "1:00"),
            (125, "2:05"),
            (3661, "61:01")  # 超过1小时
        ]
        
        for duration, expected in test_cases:
            result = NetEaseSearchResult(
                song_id="123",
                title="测试",
                artist="测试",
                album="测试",
                duration=duration
            )
            assert result.format_duration() == expected


class TestNetEaseIntegrationFlow:
    """测试完整的NetEase集成流程"""

    @pytest.fixture
    def mock_bot(self):
        """创建模拟的Discord机器人"""
        bot = Mock()
        return bot

    @pytest.fixture
    def mock_guild(self):
        """创建模拟的Discord服务器"""
        guild = Mock()
        guild.id = 12345
        guild.name = "测试服务器"
        return guild

    @pytest.fixture
    def mock_user(self, mock_guild):
        """创建模拟的Discord用户"""
        user = Mock()
        user.id = 67890
        user.display_name = "测试用户"
        user.guild = mock_guild

        # 模拟语音频道
        voice_channel = Mock()
        voice_channel.name = "音乐频道"
        voice_channel.guild = mock_guild

        user.voice = Mock()
        user.voice.channel = voice_channel

        return user

    @pytest.fixture
    def mock_ctx(self, mock_user, mock_guild):
        """创建模拟的命令上下文"""
        ctx = AsyncMock(spec=commands.Context)
        ctx.author = mock_user
        ctx.guild = mock_guild
        ctx.send = AsyncMock()
        ctx.reply = AsyncMock()
        return ctx

    @pytest.mark.asyncio
    async def test_complete_netease_flow_success(self, mock_ctx):
        """测试完整的NetEase流程 - 成功场景"""
        # 模拟搜索结果
        search_results = [
            NetEaseSearchResult("517567145", "初登校", "橋本由香利", "ひなこのーと COMPLETE SOUNDTRACK",
                              cover_url="http://example.com/cover.jpg", duration=225)
        ]

        # 模拟歌曲详情
        song_details = {
            "id": 517567145,
            "title": "初登校",
            "artist": "橋本由香利",
            "album": "ひなこのーと COMPLETE SOUNDTRACK",
            "cover": "http://example.com/cover.jpg",
            "link": "http://music.163.com/song/media/outer/url?id=517567145.mp3"
        }

        # 模拟音频信息
        audio_info = AudioInfo(
            title="初登校",
            duration=225,
            url="http://music.163.com/song/media/outer/url?id=517567145.mp3",
            uploader="橋本由香利",
            thumbnail_url="http://example.com/cover.jpg",
            file_format="mp3"
        )

        with patch('similubot.utils.netease_search.search_songs', new_callable=AsyncMock) as mock_search, \
             patch('similubot.utils.netease_search.get_song_details', new_callable=AsyncMock) as mock_details, \
             patch('similubot.provider.netease_provider.NetEaseProvider') as mock_provider_class:

            # 设置模拟返回值
            mock_search.return_value = search_results
            mock_details.return_value = song_details

            # 设置模拟提供者
            mock_provider = AsyncMock()
            mock_provider.is_supported_url.return_value = True
            mock_provider.extract_audio_info.return_value = audio_info
            mock_provider_class.return_value = mock_provider

            # 创建提供者实例并测试
            provider = NetEaseProvider("./test_temp")

            # 测试URL支持检测
            assert provider.is_supported_url("https://music.163.com/song?id=517567145")

            # 测试搜索功能
            results = await search_songs("初登校")
            assert len(results) == 1
            assert results[0].title == "初登校"

            # 测试歌曲详情获取
            details = await get_song_details("517567145")
            assert details["title"] == "初登校"

            # 验证所有组件正常工作
            mock_search.assert_called_once()
            mock_details.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_netease_flow_with_queue_integration(self, mock_ctx):
        """测试NetEase与队列系统的完整集成"""
        from similubot.queue.queue_manager import QueueManager
        from similubot.queue.persistence_manager import PersistenceManager
        from similubot.queue.duplicate_detector import DuplicateDetector

        # 创建真实的队列管理器组件（但使用模拟的依赖）
        with patch('similubot.queue.persistence_manager.PersistenceManager') as mock_persistence_class, \
             patch('similubot.queue.duplicate_detector.DuplicateDetector') as mock_detector_class:

            # 设置模拟组件
            mock_persistence = Mock()
            mock_persistence_class.return_value = mock_persistence

            mock_detector = Mock()
            mock_detector.can_user_add_song.return_value = (True, "")
            mock_detector.add_song_for_user.return_value = None
            mock_detector_class.return_value = mock_detector

            # 创建队列管理器
            queue_manager = QueueManager(mock_ctx.guild.id, mock_persistence)

            # 创建NetEase音频信息
            netease_audio_info = AudioInfo(
                title="初登校",
                duration=225,
                url="https://api.paugram.com/netease/?id=517567145",
                uploader="橋本由香利",
                thumbnail_url="http://example.com/cover.jpg",
                file_format="mp3"
            )

            # 测试添加NetEase歌曲到队列
            position = await queue_manager.add_song(netease_audio_info, mock_ctx.author)

            # 验证歌曲被成功添加
            assert position == 1

            # 验证重复检测器被调用
            mock_detector.can_user_add_song.assert_called_once_with(
                netease_audio_info, mock_ctx.author, 0
            )
            mock_detector.add_song_for_user.assert_called_once_with(
                netease_audio_info, mock_ctx.author
            )

    @pytest.mark.asyncio
    async def test_netease_error_scenarios(self):
        """测试NetEase各种错误场景"""
        client = NetEaseSearchClient()

        # 测试网络超时
        with patch('aiohttp.ClientSession') as mock_session:
            mock_session.return_value.__aenter__.return_value.get.side_effect = asyncio.TimeoutError()

            results = await client.search_songs("测试")
            assert len(results) == 0

        # 测试API返回错误格式
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"error": "invalid format"})

            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

            results = await client.search_songs("测试")
            assert len(results) == 0

        # 测试歌曲详情获取失败
        details = await client.get_song_details("invalid_id")
        assert details is None

    @pytest.mark.asyncio
    async def test_netease_provider_download_flow(self):
        """测试NetEase提供者下载流程"""
        provider = NetEaseProvider("./test_temp")

        # 模拟成功的下载流程
        with patch('similubot.utils.netease_search.get_song_details', new_callable=AsyncMock) as mock_details, \
             patch.object(provider, '_download_file', new_callable=AsyncMock) as mock_download, \
             patch('os.path.exists') as mock_exists, \
             patch('os.path.getsize') as mock_getsize:

            # 设置模拟返回值
            mock_details.return_value = {
                "id": 517567145,
                "title": "初登校",
                "artist": "橋本由香利",
                "link": "http://music.163.com/song/media/outer/url?id=517567145.mp3"
            }
            mock_download.return_value = True
            mock_exists.return_value = True
            mock_getsize.return_value = 5242880  # 5MB

            # 测试下载
            success, audio_info, error = await provider._download_audio_impl(
                "https://music.163.com/song?id=517567145"
            )

            # 验证结果
            assert success is True
            assert audio_info is not None
            assert audio_info.title == "初登校"
            assert audio_info.file_size == 5242880
            assert error is None

            # 验证下载被调用
            mock_download.assert_called_once()

    def test_netease_search_result_edge_cases(self):
        """测试NetEase搜索结果的边界情况"""
        # 测试最小化的搜索结果
        minimal_result = NetEaseSearchResult(
            song_id="123",
            title="",
            artist="",
            album=""
        )

        assert minimal_result.get_display_name() == " - "
        assert minimal_result.get_full_display_info() == " - "
        assert minimal_result.format_duration() == "未知时长"

        # 测试包含特殊字符的搜索结果
        special_result = NetEaseSearchResult(
            song_id="456",
            title="测试@歌曲#名称",
            artist="艺术家&名称",
            album="专辑(名称)",
            duration=3661  # 1小时1分1秒
        )

        assert "测试@歌曲#名称" in special_result.get_display_name()
        assert "艺术家&名称" in special_result.get_display_name()
        assert special_result.format_duration() == "61:01"

    @pytest.mark.asyncio
    async def test_ui_interaction_timeout_scenarios(self):
        """测试UI交互超时场景"""
        from similubot.ui.button_interactions import SearchConfirmationView, SearchSelectionView

        search_result = NetEaseSearchResult("123", "测试", "艺术家", "专辑")

        # 测试确认视图超时
        confirmation_view = SearchConfirmationView(search_result, timeout=0.1)
        await asyncio.sleep(0.2)
        await confirmation_view.on_timeout()

        assert confirmation_view.result == InteractionResult.TIMEOUT
        for item in confirmation_view.children:
            assert item.disabled

        # 测试选择视图超时
        selection_view = SearchSelectionView([search_result], timeout=0.1)
        await asyncio.sleep(0.2)
        await selection_view.on_timeout()

        assert selection_view.result == InteractionResult.TIMEOUT
        for item in selection_view.children:
            assert item.disabled


# 便捷函数测试
class TestConvenienceFunctions:
    """测试便捷函数"""

    @pytest.mark.asyncio
    async def test_search_songs_function(self):
        """测试搜索歌曲便捷函数"""
        with patch('similubot.utils.netease_search.NetEaseSearchClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.search_songs.return_value = [
                NetEaseSearchResult("123", "测试", "艺术家", "专辑")
            ]
            mock_client_class.return_value = mock_client
            
            # 执行搜索
            results = await search_songs("测试", limit=1)
            
            # 验证结果
            assert len(results) == 1
            assert results[0].title == "测试"

    @pytest.mark.asyncio
    async def test_get_song_details_function(self):
        """测试获取歌曲详情便捷函数"""
        with patch('similubot.utils.netease_search.NetEaseSearchClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get_song_details.return_value = {"id": 123, "title": "测试"}
            mock_client_class.return_value = mock_client
            
            # 执行获取详情
            details = await get_song_details("123")
            
            # 验证结果
            assert details["id"] == 123
            assert details["title"] == "测试"
