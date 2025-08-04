"""
!music exit 命令集成测试

测试 !music exit 命令的各种场景：
1. 所有者权限验证
2. 管理员权限验证
3. 无权限用户拒绝
4. 命令路由测试
5. 错误处理
6. 安全关闭流程
"""

import unittest
import sys
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import discord
from discord.ext import commands

from similubot.commands.music_commands import MusicCommands
from similubot.utils.config_manager import ConfigManager


class TestMusicExitCommand(unittest.IsolatedAsyncioTestCase):
    """!music exit 命令测试类"""

    def setUp(self):
        """设置测试环境"""
        print("\n🔧 设置测试环境")
        
        # 创建模拟配置管理器
        self.mock_config = Mock(spec=ConfigManager)
        self.mock_config.get.return_value = True  # 默认启用音乐功能
        
        # 创建模拟音乐播放器（MusicPlayerAdapter）
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
        
        # 创建模拟公会
        self.mock_guild = Mock()
        self.mock_guild.id = 12345
        self.mock_ctx.guild = self.mock_guild
        
        # 创建模拟用户
        self.mock_author = Mock()
        self.mock_author.id = 123456789
        self.mock_ctx.author = self.mock_author
        
        # 模拟进度条
        self.music_commands.progress_bar = Mock()
        self.music_commands.progress_bar.stop_progress_updates = Mock()
        
        print("   ✅ 测试环境设置完成")

    async def test_exit_command_owner_access(self):
        """测试所有者权限访问"""
        print("\n🧪 测试 !music exit 命令 - 所有者权限")
        
        # 设置所有者ID
        owner_id = 123456789
        self.mock_config.get.side_effect = lambda key, default=None: {
            'music.enabled': True,
            'bot.owner_id': owner_id,
            'bot.admin_id': None
        }.get(key, default)
        
        self.mock_author.id = owner_id
        
        # 模拟 sys.exit 以避免实际退出
        with patch('sys.exit') as mock_exit:
            # 执行命令
            await self.music_commands._handle_exit_command(self.mock_ctx)
            
            # 验证进度条停止
            self.music_commands.progress_bar.stop_progress_updates.assert_called_once_with(self.mock_guild.id)
            
            # 验证保存状态
            self.mock_music_player.manual_save.assert_called_once_with(self.mock_guild.id)
            
            # 验证断开连接
            self.mock_music_player.voice_manager.disconnect_from_guild.assert_called_once_with(self.mock_guild.id)
            
            # 验证回复消息
            self.mock_ctx.reply.assert_called_once()
            call_args = self.mock_ctx.reply.call_args
            embed = call_args.kwargs['embed']
            self.assertEqual(embed.title, "🔌 已断开连接")
            self.assertEqual(embed.description, "已终止进程。")
            self.assertEqual(embed.color, discord.Color.red())
            
            # 验证系统退出
            mock_exit.assert_called_once_with(0)
            
        print("   ✅ 所有者权限验证通过")

    async def test_exit_command_admin_access(self):
        """测试管理员权限访问"""
        print("\n🧪 测试 !music exit 命令 - 管理员权限")
        
        # 设置管理员ID
        admin_id = 987654321
        self.mock_config.get.side_effect = lambda key, default=None: {
            'music.enabled': True,
            'bot.owner_id': 123456789,  # 不同的所有者ID
            'bot.admin_id': admin_id
        }.get(key, default)
        
        self.mock_author.id = admin_id
        
        # 模拟 sys.exit 以避免实际退出
        with patch('sys.exit') as mock_exit:
            # 执行命令
            await self.music_commands._handle_exit_command(self.mock_ctx)
            
            # 验证系统退出
            mock_exit.assert_called_once_with(0)
            
        print("   ✅ 管理员权限验证通过")

    async def test_exit_command_unauthorized_access(self):
        """测试无权限用户访问"""
        print("\n🧪 测试 !music exit 命令 - 无权限用户")
        
        # 设置权限配置
        self.mock_config.get.side_effect = lambda key, default=None: {
            'music.enabled': True,
            'bot.owner_id': 123456789,
            'bot.admin_id': 987654321
        }.get(key, default)
        
        # 设置无权限用户ID
        self.mock_author.id = 555555555
        
        # 执行命令
        await self.music_commands._handle_exit_command(self.mock_ctx)
        
        # 验证拒绝消息
        self.mock_ctx.reply.assert_called_once_with("❌ 您没有权限执行此命令")
        
        # 验证没有执行关闭操作
        self.music_commands.progress_bar.stop_progress_updates.assert_not_called()
        self.mock_music_player.manual_save.assert_not_called()
        self.mock_music_player.voice_manager.disconnect_from_guild.assert_not_called()
        
        print("   ✅ 无权限用户正确被拒绝")

    async def test_exit_command_no_guild(self):
        """测试在非服务器环境中使用命令"""
        print("\n🧪 测试 !music exit 命令 - 非服务器环境")
        
        # 设置所有者权限
        owner_id = 123456789
        self.mock_config.get.side_effect = lambda key, default=None: {
            'music.enabled': True,
            'bot.owner_id': owner_id,
            'bot.admin_id': None
        }.get(key, default)
        
        self.mock_author.id = owner_id
        self.mock_ctx.guild = None  # 设置为私聊环境
        
        # 执行命令
        await self.music_commands._handle_exit_command(self.mock_ctx)
        
        # 验证错误消息
        self.mock_ctx.reply.assert_called_once_with("❌ 此命令只能在服务器中使用")
        
        print("   ✅ 非服务器环境正确处理")

    async def test_exit_command_disconnect_failure(self):
        """测试断开连接失败的情况"""
        print("\n🧪 测试 !music exit 命令 - 断开连接失败")
        
        # 设置所有者权限
        owner_id = 123456789
        self.mock_config.get.side_effect = lambda key, default=None: {
            'music.enabled': True,
            'bot.owner_id': owner_id,
            'bot.admin_id': None
        }.get(key, default)
        
        self.mock_author.id = owner_id
        
        # 模拟断开连接失败
        self.mock_music_player.voice_manager.disconnect_from_guild.return_value = False
        
        # 执行命令
        await self.music_commands._handle_exit_command(self.mock_ctx)
        
        # 验证错误消息
        self.mock_ctx.reply.assert_called_once_with("❌ 断开连接失败")
        
        print("   ✅ 断开连接失败正确处理")

    async def test_exit_command_exception_handling(self):
        """测试异常处理"""
        print("\n🧪 测试 !music exit 命令 - 异常处理")
        
        # 设置所有者权限
        owner_id = 123456789
        self.mock_config.get.side_effect = lambda key, default=None: {
            'music.enabled': True,
            'bot.owner_id': owner_id,
            'bot.admin_id': None
        }.get(key, default)
        
        self.mock_author.id = owner_id
        
        # 模拟保存状态时出错
        self.mock_music_player.manual_save.side_effect = Exception("保存失败")
        
        # 执行命令
        await self.music_commands._handle_exit_command(self.mock_ctx)
        
        # 验证错误消息
        self.mock_ctx.reply.assert_called_once_with("❌ 断开连接时出错")
        
        print("   ✅ 异常处理正确")

    async def test_music_command_routing_to_exit(self):
        """测试音乐命令路由到 exit 子命令"""
        print("\n🧪 测试音乐命令路由")
        
        # 模拟 _handle_exit_command 方法
        self.music_commands._handle_exit_command = AsyncMock()
        
        # 测试不同的 exit 命令别名
        test_cases = ["exit", "quit", "shutdown"]
        
        for subcommand in test_cases:
            # 重置模拟
            self.music_commands._handle_exit_command.reset_mock()
            
            # 执行命令
            await self.music_commands.music_command(self.mock_ctx, subcommand)
            
            # 验证正确的处理方法被调用
            self.music_commands._handle_exit_command.assert_called_once_with(self.mock_ctx)
            
            print(f"   ✅ '{subcommand}' 命令正确路由到 _handle_exit_command")


if __name__ == '__main__':
    print("🚀 开始 !music exit 命令集成测试")
    unittest.main(verbosity=2)
