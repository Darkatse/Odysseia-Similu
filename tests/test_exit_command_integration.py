"""
!music exit 命令集成测试 - 验证完整的命令流程

测试从命令注册到执行的完整流程
"""

import unittest
from unittest.mock import Mock, AsyncMock, patch
import discord
from discord.ext import commands

from similubot.commands.music_commands import MusicCommands
from similubot.core.command_registry import CommandRegistry
from similubot.utils.config_manager import ConfigManager


class TestExitCommandIntegration(unittest.IsolatedAsyncioTestCase):
    """!music exit 命令集成测试类"""

    def setUp(self):
        """设置测试环境"""
        print("\n🔧 设置集成测试环境")
        
        # 创建模拟配置管理器
        self.mock_config = Mock(spec=ConfigManager)
        self.mock_config.get.side_effect = lambda key, default=None: {
            'music.enabled': True,
            'bot.owner_id': 123456789,
            'bot.admin_id': None
        }.get(key, default)
        
        # 创建模拟音乐播放器
        self.mock_music_player = Mock()
        self.mock_music_player.voice_manager = Mock()
        self.mock_music_player.voice_manager.disconnect_from_guild = AsyncMock(return_value=True)
        self.mock_music_player.manual_save = AsyncMock()
        
        # 创建音乐命令实例
        self.music_commands = MusicCommands(self.mock_config, self.mock_music_player)
        
        # 创建模拟上下文
        self.mock_ctx = Mock(spec=commands.Context)
        self.mock_ctx.reply = AsyncMock()
        self.mock_ctx.send = AsyncMock()
        
        # 创建模拟公会和用户
        self.mock_guild = Mock()
        self.mock_guild.id = 12345
        self.mock_ctx.guild = self.mock_guild
        
        self.mock_author = Mock()
        self.mock_author.id = 123456789  # 所有者ID
        self.mock_ctx.author = self.mock_author
        
        # 模拟进度条
        self.music_commands.progress_bar = Mock()
        self.music_commands.progress_bar.stop_progress_updates = Mock()
        
        print("   ✅ 集成测试环境设置完成")

    async def test_complete_exit_command_flow(self):
        """测试完整的 exit 命令流程"""
        print("\n🧪 测试完整的 !music exit 命令流程")
        
        # 模拟 sys.exit 以避免实际退出
        with patch('sys.exit') as mock_exit:
            # 测试主命令路由
            await self.music_commands.music_command(self.mock_ctx, "exit")
            
            # 验证完整流程
            self.music_commands.progress_bar.stop_progress_updates.assert_called_once_with(self.mock_guild.id)
            self.mock_music_player.manual_save.assert_called_once_with(self.mock_guild.id)
            self.mock_music_player.voice_manager.disconnect_from_guild.assert_called_once_with(self.mock_guild.id)
            
            # 验证回复消息
            self.mock_ctx.reply.assert_called_once()
            call_args = self.mock_ctx.reply.call_args
            embed = call_args.kwargs['embed']
            self.assertEqual(embed.title, "🔌 已断开连接")
            
            # 验证系统退出
            mock_exit.assert_called_once_with(0)
            
        print("   ✅ 完整流程验证通过")

    async def test_exit_command_aliases(self):
        """测试 exit 命令的所有别名"""
        print("\n🧪 测试 exit 命令别名")
        
        aliases = ["exit", "quit", "shutdown"]
        
        for alias in aliases:
            print(f"   🔍 测试别名: {alias}")
            
            # 重置模拟
            self.mock_ctx.reply.reset_mock()
            self.music_commands.progress_bar.stop_progress_updates.reset_mock()
            self.mock_music_player.manual_save.reset_mock()
            self.mock_music_player.voice_manager.disconnect_from_guild.reset_mock()
            
            # 模拟 sys.exit 以避免实际退出
            with patch('sys.exit') as mock_exit:
                # 执行命令
                await self.music_commands.music_command(self.mock_ctx, alias)
                
                # 验证命令被正确处理
                self.mock_ctx.reply.assert_called_once()
                mock_exit.assert_called_once_with(0)
                
            print(f"   ✅ 别名 '{alias}' 验证通过")

    def test_command_registration_includes_exit(self):
        """测试命令注册包含 exit 命令信息"""
        print("\n🧪 测试命令注册包含 exit 信息")
        
        # 创建模拟注册表
        mock_registry = Mock(spec=CommandRegistry)
        
        # 注册命令
        self.music_commands.register_commands(mock_registry)
        
        # 验证注册被调用
        mock_registry.register_command.assert_called_once()
        
        # 获取注册参数
        call_args = mock_registry.register_command.call_args
        kwargs = call_args.kwargs
        
        # 验证 usage_examples 包含 exit 命令
        usage_examples = kwargs['usage_examples']
        exit_example_found = any('exit' in example for example in usage_examples)
        self.assertTrue(exit_example_found, "Exit command not found in usage examples")
        
        print("   ✅ 命令注册包含 exit 信息")

    async def test_help_display_includes_exit(self):
        """测试帮助显示包含 exit 命令"""
        print("\n🧪 测试帮助显示包含 exit 命令")
        
        # 执行帮助命令
        await self.music_commands._show_music_help(self.mock_ctx)
        
        # 验证回复被调用
        self.mock_ctx.reply.assert_called_once()
        
        # 获取回复参数
        call_args = self.mock_ctx.reply.call_args
        embed = call_args.kwargs['embed']
        
        # 验证 embed 包含 exit 命令信息
        fields = embed.fields
        commands_field = next((field for field in fields if field.name == "可用命令"), None)
        self.assertIsNotNone(commands_field, "Commands field not found in help embed")
        
        # 验证 exit 命令在帮助文本中
        self.assertIn('exit', commands_field.value, "Exit command not found in help text")
        
        print("   ✅ 帮助显示包含 exit 命令")


if __name__ == '__main__':
    print("🚀 开始 !music exit 命令集成测试")
    unittest.main(verbosity=2)
