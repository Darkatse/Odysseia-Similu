"""
网易云音乐默认行为测试 - 验证NetEase搜索作为默认行为

测试修改后的命令解析逻辑，确保：
1. 文本查询默认触发NetEase搜索
2. 所有现有子命令和URL检测保持不变
3. 明确的netease子命令仍然工作
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import discord
from discord.ext import commands

from similubot.commands.music_commands import MusicCommands
from similubot.core.interfaces import NetEaseSearchResult
from similubot.ui.button_interactions import InteractionResult
from similubot.utils.config_manager import ConfigManager


class TestNetEaseDefaultBehavior:
    """测试NetEase默认行为"""

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

    @pytest.mark.asyncio
    async def test_text_query_triggers_netease_search(self, music_commands, mock_ctx):
        """测试文本查询触发NetEase搜索"""
        with patch.object(music_commands, '_handle_netease_command', new_callable=AsyncMock) as mock_netease:
            # 执行文本查询
            await music_commands.music_command(mock_ctx, "初音未来")
            
            # 验证NetEase处理器被调用
            mock_netease.assert_called_once_with(mock_ctx, ("初音未来",))

    @pytest.mark.asyncio
    async def test_multi_word_query_triggers_netease_search(self, music_commands, mock_ctx):
        """测试多词查询触发NetEase搜索"""
        with patch.object(music_commands, '_handle_netease_command', new_callable=AsyncMock) as mock_netease:
            # 执行多词查询
            await music_commands.music_command(mock_ctx, "周杰伦", "青花瓷")
            
            # 验证NetEase处理器被调用，传递所有参数
            mock_netease.assert_called_once_with(mock_ctx, ("周杰伦", "青花瓷"))

    @pytest.mark.asyncio
    async def test_queue_subcommand_still_works(self, music_commands, mock_ctx):
        """测试queue子命令仍然正常工作"""
        with patch.object(music_commands, '_handle_queue_command', new_callable=AsyncMock) as mock_queue:
            # 执行queue命令
            await music_commands.music_command(mock_ctx, "queue")
            
            # 验证queue处理器被调用
            mock_queue.assert_called_once_with(mock_ctx)

    @pytest.mark.asyncio
    async def test_now_subcommand_still_works(self, music_commands, mock_ctx):
        """测试now子命令仍然正常工作"""
        with patch.object(music_commands, '_handle_now_command', new_callable=AsyncMock) as mock_now:
            # 执行now命令
            await music_commands.music_command(mock_ctx, "now")
            
            # 验证now处理器被调用
            mock_now.assert_called_once_with(mock_ctx)

    @pytest.mark.asyncio
    async def test_skip_subcommand_still_works(self, music_commands, mock_ctx):
        """测试skip子命令仍然正常工作"""
        with patch.object(music_commands, '_handle_skip_command', new_callable=AsyncMock) as mock_skip:
            # 执行skip命令
            await music_commands.music_command(mock_ctx, "skip")
            
            # 验证skip处理器被调用
            mock_skip.assert_called_once_with(mock_ctx)

    @pytest.mark.asyncio
    async def test_explicit_netease_subcommand_still_works(self, music_commands, mock_ctx):
        """测试明确的netease子命令仍然正常工作"""
        with patch.object(music_commands, '_handle_netease_command', new_callable=AsyncMock) as mock_netease:
            # 执行明确的netease命令
            await music_commands.music_command(mock_ctx, "netease", "初音未来")
            
            # 验证NetEase处理器被调用
            mock_netease.assert_called_once_with(mock_ctx, ["初音未来"])

    @pytest.mark.asyncio
    async def test_netease_aliases_still_work(self, music_commands, mock_ctx):
        """测试netease别名仍然正常工作"""
        aliases = ["ne", "网易", "网易云"]
        
        for alias in aliases:
            with patch.object(music_commands, '_handle_netease_command', new_callable=AsyncMock) as mock_netease:
                # 执行别名命令
                await music_commands.music_command(mock_ctx, alias, "测试歌曲")
                
                # 验证NetEase处理器被调用
                mock_netease.assert_called_once_with(mock_ctx, ["测试歌曲"])

    @pytest.mark.asyncio
    async def test_youtube_url_still_works(self, music_commands, mock_ctx):
        """测试YouTube URL仍然正常工作"""
        youtube_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        
        with patch.object(music_commands, '_handle_play_command', new_callable=AsyncMock) as mock_play:
            # 执行YouTube URL命令
            await music_commands.music_command(mock_ctx, youtube_url)
            
            # 验证play处理器被调用
            mock_play.assert_called_once_with(mock_ctx, youtube_url)

    @pytest.mark.asyncio
    async def test_bilibili_url_still_works(self, music_commands, mock_ctx):
        """测试Bilibili URL仍然正常工作"""
        bilibili_url = "https://www.bilibili.com/video/BV1234567890"
        
        with patch.object(music_commands, '_handle_play_command', new_callable=AsyncMock) as mock_play:
            # 执行Bilibili URL命令
            await music_commands.music_command(mock_ctx, bilibili_url)
            
            # 验证play处理器被调用
            mock_play.assert_called_once_with(mock_ctx, bilibili_url)

    @pytest.mark.asyncio
    async def test_netease_url_still_works(self, music_commands, mock_ctx):
        """测试NetEase URL仍然正常工作"""
        netease_url = "https://music.163.com/song?id=517567145"
        
        with patch.object(music_commands, '_handle_play_command', new_callable=AsyncMock) as mock_play:
            # 执行NetEase URL命令
            await music_commands.music_command(mock_ctx, netease_url)
            
            # 验证play处理器被调用
            mock_play.assert_called_once_with(mock_ctx, netease_url)

    @pytest.mark.asyncio
    async def test_catbox_url_still_works(self, music_commands, mock_ctx):
        """测试Catbox URL仍然正常工作"""
        catbox_url = "https://files.catbox.moe/abc123.mp3"
        
        with patch.object(music_commands, '_handle_play_command', new_callable=AsyncMock) as mock_play:
            # 执行Catbox URL命令
            await music_commands.music_command(mock_ctx, catbox_url)
            
            # 验证play处理器被调用
            mock_play.assert_called_once_with(mock_ctx, catbox_url)

    @pytest.mark.asyncio
    async def test_empty_command_shows_help(self, music_commands, mock_ctx):
        """测试空命令显示帮助"""
        with patch.object(music_commands, '_show_music_help', new_callable=AsyncMock) as mock_help:
            # 执行空命令
            await music_commands.music_command(mock_ctx)
            
            # 验证帮助被显示
            mock_help.assert_called_once_with(mock_ctx)

    @pytest.mark.asyncio
    async def test_jump_subcommand_with_args_still_works(self, music_commands, mock_ctx):
        """测试带参数的jump子命令仍然正常工作"""
        with patch.object(music_commands, '_handle_jump_command', new_callable=AsyncMock) as mock_jump:
            # 执行jump命令
            await music_commands.music_command(mock_ctx, "jump", "3")
            
            # 验证jump处理器被调用
            mock_jump.assert_called_once_with(mock_ctx, ["3"])

    @pytest.mark.asyncio
    async def test_seek_subcommand_with_args_still_works(self, music_commands, mock_ctx):
        """测试带参数的seek子命令仍然正常工作"""
        with patch.object(music_commands, '_handle_seek_command', new_callable=AsyncMock) as mock_seek:
            # 执行seek命令
            await music_commands.music_command(mock_ctx, "seek", "1:30")
            
            # 验证seek处理器被调用
            mock_seek.assert_called_once_with(mock_ctx, ["1:30"])

    @pytest.mark.asyncio
    async def test_chinese_search_query_triggers_netease(self, music_commands, mock_ctx):
        """测试中文搜索查询触发NetEase搜索"""
        with patch.object(music_commands, '_handle_netease_command', new_callable=AsyncMock) as mock_netease:
            # 执行中文查询
            await music_commands.music_command(mock_ctx, "千本樱")
            
            # 验证NetEase处理器被调用
            mock_netease.assert_called_once_with(mock_ctx, ("千本樱",))

    @pytest.mark.asyncio
    async def test_english_search_query_triggers_netease(self, music_commands, mock_ctx):
        """测试英文搜索查询触发NetEase搜索"""
        with patch.object(music_commands, '_handle_netease_command', new_callable=AsyncMock) as mock_netease:
            # 执行英文查询
            await music_commands.music_command(mock_ctx, "never", "gonna", "give", "you", "up")
            
            # 验证NetEase处理器被调用
            mock_netease.assert_called_once_with(mock_ctx, ("never", "gonna", "give", "you", "up"))

    @pytest.mark.asyncio
    async def test_mixed_language_search_query_triggers_netease(self, music_commands, mock_ctx):
        """测试混合语言搜索查询触发NetEase搜索"""
        with patch.object(music_commands, '_handle_netease_command', new_callable=AsyncMock) as mock_netease:
            # 执行混合语言查询
            await music_commands.music_command(mock_ctx, "初音未来", "world", "is", "mine")
            
            # 验证NetEase处理器被调用
            mock_netease.assert_called_once_with(mock_ctx, ("初音未来", "world", "is", "mine"))

    @pytest.mark.asyncio
    async def test_numeric_search_query_triggers_netease(self, music_commands, mock_ctx):
        """测试包含数字的搜索查询触发NetEase搜索"""
        with patch.object(music_commands, '_handle_netease_command', new_callable=AsyncMock) as mock_netease:
            # 执行包含数字的查询
            await music_commands.music_command(mock_ctx, "告白气球", "2016")
            
            # 验证NetEase处理器被调用
            mock_netease.assert_called_once_with(mock_ctx, ("告白气球", "2016"))

    @pytest.mark.asyncio
    async def test_special_characters_search_query_triggers_netease(self, music_commands, mock_ctx):
        """测试包含特殊字符的搜索查询触发NetEase搜索"""
        with patch.object(music_commands, '_handle_netease_command', new_callable=AsyncMock) as mock_netease:
            # 执行包含特殊字符的查询
            await music_commands.music_command(mock_ctx, "Love@Live!", "μ's")
            
            # 验证NetEase处理器被调用
            mock_netease.assert_called_once_with(mock_ctx, ("Love@Live!", "μ's"))

    @pytest.mark.asyncio
    async def test_command_case_sensitivity(self, music_commands, mock_ctx):
        """测试命令大小写敏感性"""
        # 测试大写的子命令不会被识别，应该触发NetEase搜索
        with patch.object(music_commands, '_handle_netease_command', new_callable=AsyncMock) as mock_netease:
            # 执行大写的"QUEUE"，应该被当作搜索查询
            await music_commands.music_command(mock_ctx, "QUEUE")
            
            # 验证NetEase处理器被调用
            mock_netease.assert_called_once_with(mock_ctx, ("QUEUE",))

    @pytest.mark.asyncio
    async def test_url_like_text_triggers_netease_if_not_supported(self, music_commands, mock_ctx):
        """测试类似URL但不被支持的文本触发NetEase搜索"""
        with patch.object(music_commands, '_handle_netease_command', new_callable=AsyncMock) as mock_netease:
            # 执行类似URL但不被支持的文本
            await music_commands.music_command(mock_ctx, "https://example.com/song")
            
            # 验证NetEase处理器被调用（因为不是支持的URL）
            mock_netease.assert_called_once_with(mock_ctx, ("https://example.com/song",))
