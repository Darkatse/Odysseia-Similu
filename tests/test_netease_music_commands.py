"""
网易云音乐命令测试 - 测试音乐命令中的NetEase集成

包含命令处理、队列集成和错误处理的测试。
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import discord
from discord.ext import commands

from similubot.commands.music_commands import MusicCommands
from similubot.core.interfaces import NetEaseSearchResult
from similubot.ui.button_interactions import InteractionResult
from similubot.queue.queue_manager import QueueFairnessError, DuplicateSongError, SongTooLongError
from similubot.utils.config_manager import ConfigManager


class TestNetEaseMusicCommands:
    """测试网易云音乐命令集成"""

    @pytest.fixture
    def mock_config(self):
        """创建模拟配置管理器"""
        config = Mock(spec=ConfigManager)
        config.get.return_value = True  # 默认启用音乐功能
        return config

    @pytest.fixture
    def mock_music_player(self):
        """创建模拟音乐播放器"""
        player = AsyncMock()
        player.connect_to_user_channel = AsyncMock(return_value=(True, None))
        player.add_song_to_queue = AsyncMock(return_value=(True, 1, None))
        return player

    @pytest.fixture
    def music_commands(self, mock_config, mock_music_player):
        """创建音乐命令实例"""
        return MusicCommands(mock_config, mock_music_player)

    @pytest.fixture
    def mock_ctx(self):
        """创建模拟的Discord命令上下文"""
        ctx = AsyncMock(spec=commands.Context)
        ctx.author = Mock()
        ctx.author.display_name = "TestUser"
        ctx.author.voice = Mock()
        ctx.author.voice.channel = Mock()
        ctx.send = AsyncMock()
        ctx.guild = Mock()
        ctx.guild.id = 12345
        return ctx

    @pytest.fixture
    def search_result(self):
        """创建搜索结果"""
        return NetEaseSearchResult(
            song_id="517567145",
            title="初登校",
            artist="橋本由香利",
            album="ひなこのーと COMPLETE SOUNDTRACK",
            cover_url="http://example.com/cover.jpg",
            duration=225
        )

    @pytest.fixture
    def search_results(self):
        """创建搜索结果列表"""
        return [
            NetEaseSearchResult("1", "歌曲1", "艺术家1", "专辑1", duration=180),
            NetEaseSearchResult("2", "歌曲2", "艺术家2", "专辑2", duration=200),
            NetEaseSearchResult("3", "歌曲3", "艺术家3", "专辑3", duration=220)
        ]

    @pytest.mark.asyncio
    async def test_netease_command_no_voice_channel(self, music_commands, mock_ctx):
        """测试用户不在语音频道时的NetEase命令"""
        # 设置用户不在语音频道
        mock_ctx.author.voice = None
        
        # 执行命令
        await music_commands._handle_netease_command(mock_ctx, ["初音未来"])
        
        # 验证错误消息
        mock_ctx.send.assert_called_once()
        call_args = mock_ctx.send.call_args[1]
        embed = call_args['embed']
        assert embed.title == "❌ 错误"
        assert "需要先加入语音频道" in embed.description

    @pytest.mark.asyncio
    async def test_netease_command_no_search_query(self, music_commands, mock_ctx):
        """测试没有提供搜索关键词的NetEase命令"""
        # 执行命令（无参数）
        await music_commands._handle_netease_command(mock_ctx, [])
        
        # 验证错误消息
        mock_ctx.send.assert_called_once()
        call_args = mock_ctx.send.call_args[1]
        embed = call_args['embed']
        assert embed.title == "❌ 错误"
        assert "请提供搜索关键词" in embed.description

    @pytest.mark.asyncio
    async def test_netease_command_no_search_results(self, music_commands, mock_ctx):
        """测试搜索无结果的NetEase命令"""
        with patch('similubot.utils.netease_search.search_songs', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = []  # 无搜索结果
            
            # 执行命令
            await music_commands._handle_netease_command(mock_ctx, ["不存在的歌曲"])
            
            # 验证搜索被调用
            mock_search.assert_called_once_with("不存在的歌曲", limit=5)
            
            # 验证错误消息
            assert mock_ctx.send.call_count >= 1
            # 最后一次调用应该是未找到结果的消息
            last_call = mock_ctx.send.call_args_list[-1]
            embed = last_call[1]['embed']
            assert embed.title == "❌ 未找到结果"

    @pytest.mark.asyncio
    async def test_netease_command_confirmed_first_result(self, music_commands, mock_ctx, search_results):
        """测试用户确认第一个搜索结果"""
        with patch('similubot.utils.netease_search.search_songs', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = search_results
            
            # 模拟用户确认第一个结果
            music_commands.interaction_manager.show_search_confirmation = AsyncMock(
                return_value=(InteractionResult.CONFIRMED, search_results[0])
            )
            
            # 模拟添加歌曲成功
            with patch.object(music_commands, '_add_netease_song_to_queue', new_callable=AsyncMock) as mock_add:
                # 执行命令
                await music_commands._handle_netease_command(mock_ctx, ["测试歌曲"])
                
                # 验证搜索被调用
                mock_search.assert_called_once_with("测试歌曲", limit=5)
                
                # 验证确认界面被显示
                music_commands.interaction_manager.show_search_confirmation.assert_called_once_with(
                    mock_ctx, search_results[0], timeout=60.0
                )
                
                # 验证歌曲被添加
                mock_add.assert_called_once_with(mock_ctx, search_results[0])

    @pytest.mark.asyncio
    async def test_netease_command_denied_then_selected(self, music_commands, mock_ctx, search_results):
        """测试用户拒绝第一个结果然后选择其他结果"""
        with patch('similubot.utils.netease_search.search_songs', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = search_results
            
            # 模拟用户拒绝第一个结果
            music_commands.interaction_manager.show_search_confirmation = AsyncMock(
                return_value=(InteractionResult.DENIED, None)
            )
            
            # 模拟用户选择第二个结果
            music_commands.interaction_manager.show_search_selection = AsyncMock(
                return_value=(InteractionResult.SELECTED, search_results[1])
            )
            
            # 模拟添加歌曲成功
            with patch.object(music_commands, '_add_netease_song_to_queue', new_callable=AsyncMock) as mock_add:
                # 执行命令
                await music_commands._handle_netease_command(mock_ctx, ["测试歌曲"])
                
                # 验证确认界面被显示
                music_commands.interaction_manager.show_search_confirmation.assert_called_once()
                
                # 验证选择界面被显示
                music_commands.interaction_manager.show_search_selection.assert_called_once_with(
                    mock_ctx, search_results, timeout=60.0
                )
                
                # 验证第二个歌曲被添加
                mock_add.assert_called_once_with(mock_ctx, search_results[1])

    @pytest.mark.asyncio
    async def test_netease_command_timeout(self, music_commands, mock_ctx, search_results):
        """测试用户交互超时"""
        with patch('similubot.utils.netease_search.search_songs', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = search_results
            
            # 模拟用户确认超时
            music_commands.interaction_manager.show_search_confirmation = AsyncMock(
                return_value=(InteractionResult.TIMEOUT, None)
            )
            
            # 执行命令
            await music_commands._handle_netease_command(mock_ctx, ["测试歌曲"])
            
            # 验证确认界面被显示
            music_commands.interaction_manager.show_search_confirmation.assert_called_once()
            
            # 验证没有添加歌曲
            with patch.object(music_commands, '_add_netease_song_to_queue', new_callable=AsyncMock) as mock_add:
                mock_add.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_netease_song_to_queue_success(self, music_commands, mock_ctx, search_result):
        """测试成功添加NetEase歌曲到队列"""
        with patch('similubot.utils.netease_search.get_playback_url') as mock_get_url:
            mock_get_url.return_value = "http://example.com/song.mp3"
            
            with patch('similubot.progress.discord_updater.DiscordProgressUpdater') as mock_progress:
                mock_progress_instance = Mock()
                mock_progress.return_value = mock_progress_instance
                
                # 执行添加歌曲
                await music_commands._add_netease_song_to_queue(mock_ctx, search_result)
                
                # 验证播放URL获取
                mock_get_url.assert_called_once_with(search_result.song_id, use_api=True)
                
                # 验证连接语音频道
                music_commands.music_player.connect_to_user_channel.assert_called_once_with(mock_ctx.author)
                
                # 验证添加到队列
                music_commands.music_player.add_song_to_queue.assert_called_once_with(
                    "http://example.com/song.mp3", mock_ctx.author, mock_progress_instance
                )
                
                # 验证成功消息
                mock_ctx.send.assert_called_once()
                call_args = mock_ctx.send.call_args[1]
                embed = call_args['embed']
                assert embed.title == "✅ 已添加到队列"
                assert search_result.get_display_name() in embed.description

    @pytest.mark.asyncio
    async def test_add_netease_song_voice_connection_failed(self, music_commands, mock_ctx, search_result):
        """测试语音连接失败"""
        # 设置连接失败
        music_commands.music_player.connect_to_user_channel = AsyncMock(
            return_value=(False, "连接失败")
        )
        
        with patch('similubot.utils.netease_search.get_playback_url') as mock_get_url:
            mock_get_url.return_value = "http://example.com/song.mp3"
            
            # 执行添加歌曲
            await music_commands._add_netease_song_to_queue(mock_ctx, search_result)
            
            # 验证错误消息
            mock_ctx.send.assert_called_once()
            call_args = mock_ctx.send.call_args[1]
            embed = call_args['embed']
            assert embed.title == "❌ 连接失败"
            assert "连接失败" in embed.description

    @pytest.mark.asyncio
    async def test_add_netease_song_queue_fairness_error(self, music_commands, mock_ctx, search_result):
        """测试队列公平性错误"""
        # 设置队列添加失败
        music_commands.music_player.add_song_to_queue = AsyncMock(
            return_value=(False, None, "您已经有1首歌曲在队列中，请等待播放完成后再添加新歌曲")
        )
        
        with patch('similubot.utils.netease_search.get_playback_url') as mock_get_url:
            mock_get_url.return_value = "http://example.com/song.mp3"
            
            with patch.object(music_commands, '_handle_queue_error', new_callable=AsyncMock) as mock_handle_error:
                # 执行添加歌曲
                await music_commands._add_netease_song_to_queue(mock_ctx, search_result)
                
                # 验证错误处理被调用
                mock_handle_error.assert_called_once_with(
                    mock_ctx, 
                    "您已经有1首歌曲在队列中，请等待播放完成后再添加新歌曲",
                    search_result.title
                )

    @pytest.mark.asyncio
    async def test_handle_queue_error_duplicate_song(self, music_commands, mock_ctx):
        """测试处理重复歌曲错误"""
        error_msg = "您已经请求了这首歌曲，请等待播放完成后再次请求。"
        
        # 执行错误处理
        await music_commands._handle_queue_error(mock_ctx, error_msg, "测试歌曲")
        
        # 验证错误消息
        mock_ctx.send.assert_called_once()
        call_args = mock_ctx.send.call_args[1]
        embed = call_args['embed']
        assert embed.title == "❌ 重复歌曲"
        assert error_msg in embed.description

    @pytest.mark.asyncio
    async def test_handle_queue_error_fairness_with_user_info(self, music_commands, mock_ctx):
        """测试处理队列公平性错误并显示用户信息"""
        error_msg = "您已经有1首歌曲在队列中，请等待播放完成后再添加新歌曲"
        
        # 模拟用户队列状态服务
        with patch('similubot.queue.user_queue_status.UserQueueStatusService') as mock_service_class:
            mock_service = AsyncMock()
            mock_user_info = Mock()
            mock_user_info.has_queued_song = True
            mock_user_info.queued_song_title = "当前歌曲"
            mock_user_info.queue_position = 3
            mock_user_info.estimated_play_time_seconds = 180
            
            mock_service.get_user_queue_info = AsyncMock(return_value=mock_user_info)
            mock_service_class.return_value = mock_service
            
            # 执行错误处理
            await music_commands._handle_queue_error(mock_ctx, error_msg, "测试歌曲")
            
            # 验证错误消息
            mock_ctx.send.assert_called_once()
            call_args = mock_ctx.send.call_args[1]
            embed = call_args['embed']
            assert embed.title == "❌ 队列限制"
            
            # 检查字段
            fields = {field.name: field.value for field in embed.fields}
            assert "您当前的歌曲" in fields
            assert "当前歌曲" in fields["您当前的歌曲"]
            assert "第 3 位" in fields["您当前的歌曲"]
            assert "预计播放时间" in fields
            assert "3:00 后" in fields["预计播放时间"]

    @pytest.mark.asyncio
    async def test_handle_queue_error_song_too_long(self, music_commands, mock_ctx):
        """测试处理歌曲过长错误"""
        error_msg = "歌曲时长 10:30 超过了最大限制 8:00。"
        
        # 执行错误处理
        await music_commands._handle_queue_error(mock_ctx, error_msg, "测试歌曲")
        
        # 验证错误消息
        mock_ctx.send.assert_called_once()
        call_args = mock_ctx.send.call_args[1]
        embed = call_args['embed']
        assert embed.title == "❌ 歌曲过长"
        assert error_msg in embed.description

    @pytest.mark.asyncio
    async def test_handle_queue_error_generic_error(self, music_commands, mock_ctx):
        """测试处理通用错误"""
        error_msg = "未知错误"
        
        # 执行错误处理
        await music_commands._handle_queue_error(mock_ctx, error_msg, "测试歌曲")
        
        # 验证错误消息
        mock_ctx.send.assert_called_once()
        call_args = mock_ctx.send.call_args[1]
        embed = call_args['embed']
        assert embed.title == "❌ 添加失败"
        assert error_msg in embed.description

    @pytest.mark.asyncio
    async def test_netease_command_exception_handling(self, music_commands, mock_ctx):
        """测试NetEase命令异常处理"""
        with patch('similubot.utils.netease_search.search_songs', new_callable=AsyncMock) as mock_search:
            mock_search.side_effect = Exception("搜索异常")
            
            # 执行命令
            await music_commands._handle_netease_command(mock_ctx, ["测试"])
            
            # 验证异常处理
            assert mock_ctx.send.call_count >= 1
            # 最后一次调用应该是错误消息
            last_call = mock_ctx.send.call_args_list[-1]
            embed = last_call[1]['embed']
            assert embed.title == "❌ 错误"
            assert "处理网易云音乐搜索时发生错误" in embed.description

    @pytest.mark.asyncio
    async def test_add_netease_song_exception_handling(self, music_commands, mock_ctx, search_result):
        """测试添加NetEase歌曲异常处理"""
        with patch('similubot.utils.netease_search.get_playback_url') as mock_get_url:
            mock_get_url.side_effect = Exception("URL获取异常")
            
            # 执行添加歌曲
            await music_commands._add_netease_song_to_queue(mock_ctx, search_result)
            
            # 验证异常处理
            mock_ctx.send.assert_called_once()
            call_args = mock_ctx.send.call_args[1]
            embed = call_args['embed']
            assert embed.title == "❌ 添加失败"
            assert "添加歌曲到队列时发生错误" in embed.description
