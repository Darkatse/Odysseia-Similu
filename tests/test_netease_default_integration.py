"""
网易云音乐默认行为集成测试 - 验证完整的用户体验

测试从用户输入到最终结果的完整流程，确保新的默认行为正常工作。
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
import discord
from discord.ext import commands

from similubot.commands.music_commands import MusicCommands
from similubot.core.interfaces import NetEaseSearchResult
from similubot.ui.button_interactions import InteractionResult
from similubot.utils.config_manager import ConfigManager


class TestNetEaseDefaultIntegration:
    """测试NetEase默认行为的完整集成"""

    @pytest.fixture
    def mock_config(self):
        """创建模拟配置管理器"""
        config = Mock(spec=ConfigManager)
        config.get.return_value = True
        return config

    @pytest.fixture
    def mock_music_player(self):
        """创建模拟音乐播放器"""
        player = AsyncMock()
        player.connect_to_user_channel = AsyncMock(return_value=(True, None))
        player.add_song_to_queue = AsyncMock(return_value=(True, 1, None))
        
        # 模拟URL支持检测
        def is_supported_url(url):
            if not url:
                return False
            return any(domain in url.lower() for domain in [
                'youtube.com', 'youtu.be', 'catbox.moe', 'bilibili.com', 'music.163.com'
            ])
        
        player.is_supported_url = Mock(side_effect=is_supported_url)
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
        ctx.reply = AsyncMock()
        ctx.guild = Mock()
        ctx.guild.id = 12345
        return ctx

    @pytest.fixture
    def search_results(self):
        """创建模拟搜索结果"""
        return [
            NetEaseSearchResult(
                song_id="517567145",
                title="初登校",
                artist="橋本由香利",
                album="ひなこのーと COMPLETE SOUNDTRACK",
                cover_url="http://example.com/cover.jpg",
                duration=225
            )
        ]

    @pytest.mark.asyncio
    async def test_complete_default_search_flow_confirmed(self, music_commands, mock_ctx, search_results):
        """测试完整的默认搜索流程 - 用户确认第一个结果"""
        with patch('similubot.utils.netease_search.search_songs', new_callable=AsyncMock) as mock_search, \
             patch('similubot.utils.netease_search.get_playback_url') as mock_get_url:
            
            # 设置模拟返回值
            mock_search.return_value = search_results
            mock_get_url.return_value = "https://api.paugram.com/netease/?id=517567145"
            
            # 模拟用户确认第一个结果
            music_commands.interaction_manager.show_search_confirmation = AsyncMock(
                return_value=(InteractionResult.CONFIRMED, search_results[0])
            )
            
            # 模拟进度更新器
            with patch('similubot.progress.discord_updater.DiscordProgressUpdater') as mock_progress:
                mock_progress_instance = Mock()
                mock_progress.return_value = mock_progress_instance
                
                # 执行默认搜索命令
                await music_commands.music_command(mock_ctx, "初登校")
                
                # 验证搜索被调用
                mock_search.assert_called_once_with("初登校", limit=5)
                
                # 验证确认界面被显示
                music_commands.interaction_manager.show_search_confirmation.assert_called_once_with(
                    mock_ctx, search_results[0], timeout=60.0
                )
                
                # 验证播放URL获取
                mock_get_url.assert_called_once_with("517567145", use_api=True)
                
                # 验证连接语音频道
                music_commands.music_player.connect_to_user_channel.assert_called_once_with(mock_ctx.author)
                
                # 验证添加到队列
                music_commands.music_player.add_song_to_queue.assert_called_once_with(
                    "https://api.paugram.com/netease/?id=517567145", mock_ctx.author, mock_progress_instance
                )
                
                # 验证成功消息
                mock_ctx.send.assert_called()
                call_args = mock_ctx.send.call_args[1]
                embed = call_args['embed']
                assert embed.title == "✅ 已添加到队列"
                assert "初登校 - 橋本由香利" in embed.description

    @pytest.mark.asyncio
    async def test_default_search_vs_explicit_netease_command(self, music_commands, mock_ctx, search_results):
        """测试默认搜索与明确netease命令的行为一致性"""
        with patch('similubot.utils.netease_search.search_songs', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = search_results
            
            # 模拟用户确认
            music_commands.interaction_manager.show_search_confirmation = AsyncMock(
                return_value=(InteractionResult.CONFIRMED, search_results[0])
            )
            
            with patch.object(music_commands, '_add_netease_song_to_queue', new_callable=AsyncMock) as mock_add:
                # 测试默认行为
                await music_commands.music_command(mock_ctx, "初音未来")
                default_call_args = mock_search.call_args
                
                # 重置mock
                mock_search.reset_mock()
                mock_add.reset_mock()
                music_commands.interaction_manager.show_search_confirmation.reset_mock()
                
                # 测试明确的netease命令
                await music_commands.music_command(mock_ctx, "netease", "初音未来")
                explicit_call_args = mock_search.call_args
                
                # 验证两种方式的搜索参数相同
                assert default_call_args == explicit_call_args
                
                # 验证两种方式都调用了相同的处理流程
                assert music_commands.interaction_manager.show_search_confirmation.call_count == 2

    @pytest.mark.asyncio
    async def test_url_detection_priority_over_default_search(self, music_commands, mock_ctx):
        """测试URL检测优先于默认搜索"""
        youtube_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        
        with patch.object(music_commands, '_handle_play_command', new_callable=AsyncMock) as mock_play, \
             patch.object(music_commands, '_handle_netease_command', new_callable=AsyncMock) as mock_netease:
            
            # 执行YouTube URL命令
            await music_commands.music_command(mock_ctx, youtube_url)
            
            # 验证play处理器被调用，而不是NetEase处理器
            mock_play.assert_called_once_with(mock_ctx, youtube_url)
            mock_netease.assert_not_called()

    @pytest.mark.asyncio
    async def test_subcommand_priority_over_default_search(self, music_commands, mock_ctx):
        """测试子命令优先于默认搜索"""
        with patch.object(music_commands, '_handle_queue_command', new_callable=AsyncMock) as mock_queue, \
             patch.object(music_commands, '_handle_netease_command', new_callable=AsyncMock) as mock_netease:
            
            # 执行queue命令
            await music_commands.music_command(mock_ctx, "queue")
            
            # 验证queue处理器被调用，而不是NetEase处理器
            mock_queue.assert_called_once_with(mock_ctx)
            mock_netease.assert_not_called()

    @pytest.mark.asyncio
    async def test_multi_word_search_query_handling(self, music_commands, mock_ctx, search_results):
        """测试多词搜索查询处理"""
        with patch('similubot.utils.netease_search.search_songs', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = search_results
            
            # 模拟用户确认
            music_commands.interaction_manager.show_search_confirmation = AsyncMock(
                return_value=(InteractionResult.CONFIRMED, search_results[0])
            )
            
            with patch.object(music_commands, '_add_netease_song_to_queue', new_callable=AsyncMock):
                # 执行多词搜索
                await music_commands.music_command(mock_ctx, "周杰伦", "青花瓷", "2006")
                
                # 验证搜索被调用，查询字符串正确组合
                mock_search.assert_called_once_with("周杰伦 青花瓷 2006", limit=5)

    @pytest.mark.asyncio
    async def test_search_no_results_fallback(self, music_commands, mock_ctx):
        """测试搜索无结果的回退处理"""
        with patch('similubot.utils.netease_search.search_songs', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = []  # 无搜索结果
            
            # 执行搜索
            await music_commands.music_command(mock_ctx, "不存在的歌曲")
            
            # 验证搜索被调用
            mock_search.assert_called_once_with("不存在的歌曲", limit=5)
            
            # 验证发送了未找到结果的消息
            mock_ctx.send.assert_called()
            call_args = mock_ctx.send.call_args[1]
            embed = call_args['embed']
            assert embed.title == "❌ 未找到结果"

    @pytest.mark.asyncio
    async def test_search_api_error_fallback(self, music_commands, mock_ctx):
        """测试搜索API错误的回退处理"""
        with patch('similubot.utils.netease_search.search_songs', new_callable=AsyncMock) as mock_search:
            mock_search.side_effect = Exception("API错误")
            
            # 执行搜索
            await music_commands.music_command(mock_ctx, "测试歌曲")
            
            # 验证搜索被调用
            mock_search.assert_called_once_with("测试歌曲", limit=5)
            
            # 验证发送了错误消息
            mock_ctx.send.assert_called()
            call_args = mock_ctx.send.call_args[1]
            embed = call_args['embed']
            assert embed.title == "❌ 错误"
            assert "处理网易云音乐搜索时发生错误" in embed.description

    @pytest.mark.asyncio
    async def test_help_command_shows_updated_information(self, music_commands, mock_ctx):
        """测试帮助命令显示更新的信息"""
        # 执行帮助命令
        await music_commands._show_music_help(mock_ctx)
        
        # 验证帮助被显示
        mock_ctx.reply.assert_called_once()
        call_args = mock_ctx.reply.call_args[1]
        embed = call_args['embed']
        
        # 验证帮助内容包含新的默认行为说明
        assert embed.title == "🎵 音乐命令"
        
        # 检查字段内容
        fields = {field.name: field.value for field in embed.fields}
        
        # 验证可用命令字段包含默认搜索说明
        assert "可用命令" in fields
        assert "`!music <搜索关键词>` - 搜索并添加网易云音乐歌曲（默认行为）" in fields["可用命令"]
        
        # 验证使用要求字段包含新的说明
        assert "使用要求" in fields
        assert "直接输入搜索关键词将自动在网易云音乐中搜索" in fields["使用要求"]
        
        # 验证使用示例字段存在
        assert "使用示例" in fields
        assert "`!music 初音未来`" in fields["使用示例"]
        assert "`!music 周杰伦 青花瓷`" in fields["使用示例"]

    @pytest.mark.asyncio
    async def test_edge_case_single_character_search(self, music_commands, mock_ctx, search_results):
        """测试边界情况：单字符搜索"""
        with patch('similubot.utils.netease_search.search_songs', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = search_results
            
            # 模拟用户确认
            music_commands.interaction_manager.show_search_confirmation = AsyncMock(
                return_value=(InteractionResult.CONFIRMED, search_results[0])
            )
            
            with patch.object(music_commands, '_add_netease_song_to_queue', new_callable=AsyncMock):
                # 执行单字符搜索
                await music_commands.music_command(mock_ctx, "爱")
                
                # 验证搜索被调用
                mock_search.assert_called_once_with("爱", limit=5)

    @pytest.mark.asyncio
    async def test_edge_case_numeric_only_search(self, music_commands, mock_ctx, search_results):
        """测试边界情况：纯数字搜索"""
        with patch('similubot.utils.netease_search.search_songs', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = search_results
            
            # 模拟用户确认
            music_commands.interaction_manager.show_search_confirmation = AsyncMock(
                return_value=(InteractionResult.CONFIRMED, search_results[0])
            )
            
            with patch.object(music_commands, '_add_netease_song_to_queue', new_callable=AsyncMock):
                # 执行纯数字搜索
                await music_commands.music_command(mock_ctx, "2023")
                
                # 验证搜索被调用
                mock_search.assert_called_once_with("2023", limit=5)
