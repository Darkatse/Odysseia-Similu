"""
音乐命令测试

测试音乐相关的Slash命令功能：
- 音乐搜索命令
- 队列管理命令
- 播放控制命令
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import discord

from similubot.app_commands.music import (
    MusicSearchCommands,
    QueueManagementCommands,
    PlaybackControlCommands
)
from similubot.core.interfaces import AudioInfo, NetEaseSearchResult
from similubot.utils.config_manager import ConfigManager


class TestMusicSearchCommands:
    """测试音乐搜索命令"""

    def setup_method(self):
        """设置测试环境"""
        self.config = Mock(spec=ConfigManager)
        self.config.get.return_value = True
        self.music_player = Mock()
        self.command = MusicSearchCommands(self.config, self.music_player)

    @pytest.mark.asyncio
    async def test_handle_song_request_prerequisites_fail(self):
        """测试点歌请求 - 前置条件失败"""
        interaction = Mock(spec=discord.Interaction)
        interaction.guild = None
        interaction.response.send_message = AsyncMock()

        await self.command.handle_song_request(interaction, "test query")

        # 应该因为没有服务器而失败
        interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_song_request_voice_channel_fail(self):
        """测试点歌请求 - 语音频道检查失败"""
        interaction = Mock(spec=discord.Interaction)
        interaction.guild = Mock()
        interaction.user.voice = None
        interaction.response.send_message = AsyncMock()

        await self.command.handle_song_request(interaction, "test query")

        # 应该因为不在语音频道而失败
        interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_song_request_url(self):
        """测试点歌请求 - URL处理"""
        interaction = Mock(spec=discord.Interaction)
        interaction.guild = Mock()
        interaction.user.voice = Mock()
        interaction.user.voice.channel = Mock()
        interaction.user.display_name = "TestUser"
        interaction.response.send_message = AsyncMock()

        # 模拟音乐播放器
        self.music_player.connect_to_user_channel = AsyncMock(return_value=(True, None))
        self.music_player.is_supported_url.return_value = True
        self.music_player.detect_audio_source_type.return_value = Mock(value="youtube")
        self.music_player.add_song_to_queue = AsyncMock(return_value=(True, 1, None))

        # 模拟音频信息
        audio_info = AudioInfo(
            title="Test Song",
            duration=180,
            url="https://youtube.com/test",
            uploader="Test Channel"
        )

        with patch.object(self.command, '_get_audio_info_by_source', return_value=audio_info):
            await self.command.handle_song_request(interaction, "https://youtube.com/test")

        # 验证调用
        self.music_player.connect_to_user_channel.assert_called_once()
        self.music_player.add_song_to_queue.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_song_request_netease_search(self):
        """测试点歌请求 - NetEase搜索"""
        interaction = Mock(spec=discord.Interaction)
        interaction.guild = Mock()
        interaction.user.voice = Mock()
        interaction.user.voice.channel = Mock()
        interaction.user.display_name = "TestUser"
        interaction.response.send_message = AsyncMock()
        interaction.edit_original_response = AsyncMock()

        # 模拟音乐播放器
        self.music_player.connect_to_user_channel = AsyncMock(return_value=(True, None))
        self.music_player.is_supported_url.return_value = False

        # 模拟搜索结果
        search_result = Mock(spec=NetEaseSearchResult)
        search_result.get_display_name.return_value = "Test Song - Test Artist"
        search_result.album = "Test Album"
        search_result.duration = 180
        search_result.format_duration.return_value = "3:00"
        search_result.cover_url = "https://example.com/cover.jpg"

        with patch('similubot.utils.netease_search.search_songs', return_value=[search_result]):
            with patch.object(self.command, '_handle_search_results') as mock_handle:
                await self.command.handle_song_request(interaction, "test song")

                mock_handle.assert_called_once_with(interaction, [search_result])

    @pytest.mark.asyncio
    async def test_handle_song_request_netease_no_results(self):
        """测试点歌请求 - NetEase搜索无结果"""
        interaction = Mock(spec=discord.Interaction)
        interaction.guild = Mock()
        interaction.user.voice = Mock()
        interaction.user.voice.channel = Mock()
        interaction.response.send_message = AsyncMock()
        interaction.edit_original_response = AsyncMock()

        self.music_player.connect_to_user_channel = AsyncMock(return_value=(True, None))
        self.music_player.is_supported_url.return_value = False

        with patch('similubot.utils.netease_search.search_songs', return_value=[]):
            await self.command.handle_song_request(interaction, "nonexistent song")

            interaction.edit_original_response.assert_called_once()
            args, kwargs = interaction.edit_original_response.call_args
            embed = kwargs['embed']
            assert "未找到结果" in embed.title

    @pytest.mark.asyncio
    async def test_handle_queue_fairness_error(self):
        """测试队列公平性错误处理"""
        interaction = Mock(spec=discord.Interaction)
        interaction.guild = Mock()
        interaction.user.voice = Mock()
        interaction.user.voice.channel = Mock()
        interaction.user.display_name = "TestUser"
        interaction.response.send_message = AsyncMock()
        interaction.edit_original_response = AsyncMock()

        self.music_player.connect_to_user_channel = AsyncMock(return_value=(True, None))
        self.music_player.is_supported_url.return_value = True
        self.music_player.add_song_to_queue = AsyncMock(
            return_value=(False, None, "已经有1首歌曲在队列中")
        )

        with patch.object(self.command, '_handle_queue_fairness_error') as mock_handle:
            await self.command.handle_song_request(interaction, "https://youtube.com/test")

            mock_handle.assert_called_once()

    def test_format_duration(self):
        """测试时长格式化"""
        # 测试秒
        assert self.command._format_duration(30) == "30秒"

        # 测试分钟
        assert self.command._format_duration(90) == "1:30"

        # 测试小时
        assert self.command._format_duration(3661) == "1:01:01"


class TestQueueManagementCommands:
    """测试队列管理命令"""

    def setup_method(self):
        """设置测试环境"""
        self.config = Mock(spec=ConfigManager)
        self.config.get.return_value = True
        self.music_player = Mock()
        self.command = QueueManagementCommands(self.config, self.music_player)

    @pytest.mark.asyncio
    async def test_handle_queue_display_empty(self):
        """测试队列显示 - 空队列"""
        interaction = Mock(spec=discord.Interaction)
        interaction.guild = Mock()
        interaction.response.send_message = AsyncMock()

        # 模拟空队列
        queue_info = {
            "is_empty": True,
            "current_song": None
        }
        self.music_player.get_queue_info = AsyncMock(return_value=queue_info)

        await self.command.handle_queue_display(interaction)

        interaction.response.send_message.assert_called_once()
        args, kwargs = interaction.response.send_message.call_args
        embed = kwargs['embed']
        assert "队列为空" in embed.description

    @pytest.mark.asyncio
    async def test_handle_queue_display_with_songs(self):
        """测试队列显示 - 有歌曲"""
        interaction = Mock(spec=discord.Interaction)
        interaction.guild = Mock()
        interaction.response.send_message = AsyncMock()

        # 模拟当前歌曲
        current_song = Mock()
        current_song.title = "Current Song"
        current_song.duration = 180
        current_song.requester.display_name = "TestUser"

        queue_info = {
            "is_empty": False,
            "current_song": current_song,
            "queue_length": 2,
            "total_duration": 360,
            "connected": True,
            "channel": "Test Channel",
            "playing": True,
            "paused": False
        }

        self.music_player.get_queue_info = AsyncMock(return_value=queue_info)

        # 模拟队列管理器
        queue_manager = Mock()
        queue_display = [
            {
                "position": 1,
                "title": "Next Song",
                "duration": "3:00",
                "requester": "User2"
            }
        ]
        queue_manager.get_queue_display = AsyncMock(return_value=queue_display)
        self.music_player.get_queue_manager.return_value = queue_manager

        await self.command.handle_queue_display(interaction)

        interaction.response.send_message.assert_called_once()
        args, kwargs = interaction.response.send_message.call_args
        embed = kwargs['embed']
        assert "正在播放" in str(embed.fields)

    @pytest.mark.asyncio
    async def test_handle_user_queue_status_no_song(self):
        """测试用户队列状态 - 无歌曲"""
        interaction = Mock(spec=discord.Interaction)
        interaction.guild = Mock()
        interaction.user = Mock()
        interaction.response.send_message = AsyncMock()

        # 模拟播放引擎
        self.music_player._playback_engine = Mock()

        # 模拟用户队列服务
        user_info = Mock()
        user_info.has_queued_song = False

        with patch('similubot.queue.user_queue_status.UserQueueStatusService') as MockService:
            mock_service = MockService.return_value
            mock_service.get_user_queue_info.return_value = user_info

            await self.command.handle_user_queue_status(interaction)

            interaction.response.send_message.assert_called_once()
            args, kwargs = interaction.response.send_message.call_args
            assert kwargs['ephemeral'] is True
            embed = kwargs['embed']
            assert "没有歌曲在队列中" in embed.description

    @pytest.mark.asyncio
    async def test_handle_user_queue_status_with_song(self):
        """测试用户队列状态 - 有歌曲"""
        interaction = Mock(spec=discord.Interaction)
        interaction.guild = Mock()
        interaction.user = Mock()
        interaction.response.send_message = AsyncMock()

        self.music_player._playback_engine = Mock()

        # 模拟用户队列信息
        user_info = Mock()
        user_info.has_queued_song = True
        user_info.is_currently_playing = False
        user_info.queued_song_title = "My Song"
        user_info.queue_position = 2
        user_info.estimated_play_time_seconds = 300
        user_info.format_estimated_time.return_value = "5分钟"

        with patch('similubot.queue.user_queue_status.UserQueueStatusService') as MockService:
            mock_service = MockService.return_value
            mock_service.get_user_queue_info.return_value = user_info

            await self.command.handle_user_queue_status(interaction)

            interaction.response.send_message.assert_called_once()
            args, kwargs = interaction.response.send_message.call_args
            assert kwargs['ephemeral'] is True
            embed = kwargs['embed']
            assert "排队歌曲" in str(embed.fields)

    @pytest.mark.asyncio
    async def test_handle_user_queue_status_currently_playing(self):
        """测试用户队列状态 - 正在播放"""
        interaction = Mock(spec=discord.Interaction)
        interaction.guild = Mock()
        interaction.user = Mock()
        interaction.response.send_message = AsyncMock()

        self.music_player._playback_engine = Mock()

        user_info = Mock()
        user_info.has_queued_song = True
        user_info.is_currently_playing = True
        user_info.queued_song_title = "My Song"

        with patch('similubot.queue.user_queue_status.UserQueueStatusService') as MockService:
            mock_service = MockService.return_value
            mock_service.get_user_queue_info.return_value = user_info

            await self.command.handle_user_queue_status(interaction)

            interaction.response.send_message.assert_called_once()
            args, kwargs = interaction.response.send_message.call_args
            embed = kwargs['embed']
            assert "正在播放中" in embed.description


class TestPlaybackControlCommands:
    """测试播放控制命令"""

    def setup_method(self):
        """设置测试环境"""
        self.config = Mock(spec=ConfigManager)
        self.config.get.return_value = True
        self.music_player = Mock()

        # 模拟进度条和投票管理器
        with patch('similubot.progress.music_progress.MusicProgressBar'):
            with patch('similubot.ui.skip_vote_poll.VoteManager'):
                self.command = PlaybackControlCommands(self.config, self.music_player)

    @pytest.mark.asyncio
    async def test_handle_skip_song_no_current_song(self):
        """测试跳过歌曲 - 无当前歌曲"""
        interaction = Mock(spec=discord.Interaction)
        interaction.guild = Mock()
        interaction.response.send_message = AsyncMock()

        # 模拟无当前歌曲
        queue_info = {"current_song": None}
        self.music_player.get_queue_info = AsyncMock(return_value=queue_info)

        await self.command.handle_skip_song(interaction)

        interaction.response.send_message.assert_called_once()
        args, kwargs = interaction.response.send_message.call_args
        assert kwargs['ephemeral'] is True
        embed = kwargs['embed']
        assert "没有歌曲在播放" in embed.description

    @pytest.mark.asyncio
    async def test_handle_skip_song_direct_skip(self):
        """测试跳过歌曲 - 直接跳过"""
        interaction = Mock(spec=discord.Interaction)
        interaction.guild = Mock()
        interaction.response.send_message = AsyncMock()
        interaction.edit_original_response = AsyncMock()

        # 模拟当前歌曲
        current_song = Mock()
        current_song.title = "Test Song"
        queue_info = {"current_song": current_song}
        self.music_player.get_queue_info = AsyncMock(return_value=queue_info)

        # 模拟投票管理器决定不使用投票
        self.command.vote_manager.get_voice_channel_members.return_value = ["user1"]
        self.command.vote_manager.should_use_voting.return_value = False

        # 模拟跳过成功
        self.music_player.skip_current_song = AsyncMock(return_value=(True, "Test Song", None))

        await self.command.handle_skip_song(interaction)

        self.music_player.skip_current_song.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_skip_song_voting(self):
        """测试跳过歌曲 - 投票模式"""
        interaction = Mock(spec=discord.Interaction)
        interaction.guild = Mock()
        interaction.response.send_message = AsyncMock()

        # 模拟当前歌曲
        current_song = Mock()
        current_song.title = "Test Song"
        queue_info = {"current_song": current_song}
        self.music_player.get_queue_info = AsyncMock(return_value=queue_info)

        # 模拟投票管理器决定使用投票
        self.command.vote_manager.get_voice_channel_members.return_value = ["user1", "user2", "user3"]
        self.command.vote_manager.should_use_voting.return_value = True
        self.command.vote_manager.start_skip_vote = AsyncMock(return_value=Mock())

        await self.command.handle_skip_song(interaction)

        self.command.vote_manager.start_skip_vote.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_show_progress_no_current_song(self):
        """测试显示进度 - 无当前歌曲"""
        interaction = Mock(spec=discord.Interaction)
        interaction.guild = Mock()
        interaction.response.send_message = AsyncMock()

        queue_info = {"current_song": None}
        self.music_player.get_queue_info = AsyncMock(return_value=queue_info)

        await self.command.handle_show_progress(interaction)

        interaction.response.send_message.assert_called_once()
        args, kwargs = interaction.response.send_message.call_args
        assert kwargs['ephemeral'] is True

    @pytest.mark.asyncio
    async def test_handle_show_progress_with_song(self):
        """测试显示进度 - 有当前歌曲"""
        interaction = Mock(spec=discord.Interaction)
        interaction.guild = Mock()
        interaction.response.send_message = AsyncMock()
        interaction.edit_original_response = AsyncMock()

        # 模拟当前歌曲
        current_song = Mock()
        current_song.title = "Test Song"
        current_song.duration = 180
        current_song.uploader = "Test Channel"
        current_song.requester.display_name = "TestUser"

        queue_info = {
            "current_song": current_song,
            "playing": True,
            "paused": False
        }
        self.music_player.get_queue_info = AsyncMock(return_value=queue_info)

        # 模拟进度条显示失败，回退到静态显示
        self.command.progress_bar.show_progress_bar = AsyncMock(return_value=False)

        await self.command.handle_show_progress(interaction)

        interaction.edit_original_response.assert_called_once()
        args, kwargs = interaction.edit_original_response.call_args
        embed = kwargs['embed']
        assert "正在播放" in embed.title

    @pytest.mark.asyncio
    async def test_direct_skip_song_success(self):
        """测试直接跳过歌曲成功"""
        interaction = Mock(spec=discord.Interaction)
        interaction.guild = Mock()
        interaction.response.is_done.return_value = False
        interaction.response.send_message = AsyncMock()

        current_song = Mock()
        current_song.title = "Test Song"

        self.music_player.skip_current_song = AsyncMock(return_value=(True, "Test Song", None))

        await self.command._direct_skip_song(interaction, current_song)

        interaction.response.send_message.assert_called_once()
        args, kwargs = interaction.response.send_message.call_args
        embed = kwargs['embed']
        assert "歌曲已跳过" in embed.title
        assert "Test Song" in embed.description

    @pytest.mark.asyncio
    async def test_direct_skip_song_failure(self):
        """测试直接跳过歌曲失败"""
        interaction = Mock(spec=discord.Interaction)
        interaction.guild = Mock()
        interaction.response.send_message = AsyncMock()

        current_song = Mock()
        current_song.title = "Test Song"

        self.music_player.skip_current_song = AsyncMock(return_value=(False, None, "跳过失败"))

        await self.command._direct_skip_song(interaction, current_song)

        interaction.response.send_message.assert_called_once()
        args, kwargs = interaction.response.send_message.call_args
        assert kwargs['ephemeral'] is True

    @pytest.mark.asyncio
    async def test_execute_skip(self):
        """测试执行跳过操作"""
        guild_id = 12345
        song_title = "Test Song"

        self.music_player.skip_current_song = AsyncMock(return_value=(True, "Test Song", None))

        await self.command._execute_skip(guild_id, song_title)

        self.music_player.skip_current_song.assert_called_once_with(guild_id)

    def test_create_temp_context(self):
        """测试创建临时Context对象"""
        interaction = Mock(spec=discord.Interaction)
        interaction.user = Mock()
        interaction.guild = Mock()
        interaction.channel = Mock()
        interaction.client = Mock()
        interaction.followup.send = AsyncMock()

        temp_ctx = self.command._create_temp_context(interaction)

        assert temp_ctx.author is interaction.user
        assert temp_ctx.guild is interaction.guild
        assert temp_ctx.channel is interaction.channel
        assert temp_ctx.bot is interaction.client

    def test_format_duration(self):
        """测试时长格式化"""
        # 测试秒
        assert self.command._format_duration(30) == "30秒"

        # 测试分钟
        assert self.command._format_duration(90) == "1:30"

        # 测试小时
        assert self.command._format_duration(3661) == "1:01:01"