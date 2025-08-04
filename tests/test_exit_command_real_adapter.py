"""
!music exit 命令真实适配器测试

测试使用真实 MusicPlayerAdapter 的 exit 命令功能
"""

import unittest
from unittest.mock import Mock, AsyncMock, patch
import discord
from discord.ext import commands

from similubot.commands.music_commands import MusicCommands
from similubot.adapters.music_player_adapter import MusicPlayerAdapter
from similubot.utils.config_manager import ConfigManager


class TestExitCommandRealAdapter(unittest.IsolatedAsyncioTestCase):
    """使用真实适配器的 exit 命令测试类"""

    def setUp(self):
        """设置测试环境"""
        print("\n🔧 设置真实适配器测试环境")
        
        # 创建模拟配置管理器
        self.mock_config = Mock(spec=ConfigManager)
        self.mock_config.get.side_effect = lambda key, default=None: {
            'music.enabled': True,
            'bot.owner_id': 123456789,
            'bot.admin_id': None
        }.get(key, default)
        
        # 创建模拟的 PlaybackEngine
        self.mock_playback_engine = Mock()
        self.mock_playback_engine.bot = Mock()
        self.mock_playback_engine.config = self.mock_config
        self.mock_playback_engine.temp_dir = "./temp"
        self.mock_playback_engine.voice_manager = Mock()
        self.mock_playback_engine.seek_manager = Mock()
        self.mock_playback_engine.persistence_manager = Mock()
        self.mock_playback_engine.audio_provider_factory = Mock()
        
        # 模拟关键方法
        self.mock_playback_engine.manual_save = AsyncMock()
        self.mock_playback_engine.get_queue_manager = Mock()
        self.mock_playback_engine.get_current_playback_position = Mock(return_value=None)
        self.mock_playback_engine.pause_playback = Mock(return_value=True)
        self.mock_playback_engine.resume_playback = Mock(return_value=True)
        self.mock_playback_engine.is_paused = Mock(return_value=False)
        self.mock_playback_engine.initialize_persistence = AsyncMock()
        
        # 模拟 voice_manager 的 disconnect_from_guild 方法
        self.mock_playback_engine.voice_manager.disconnect_from_guild = AsyncMock(return_value=True)
        
        # 创建真实的适配器实例
        self.music_player_adapter = MusicPlayerAdapter(self.mock_playback_engine)
        
        # 创建音乐命令实例
        self.music_commands = MusicCommands(self.mock_config, self.music_player_adapter)
        
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
        
        print("   ✅ 真实适配器测试环境设置完成")

    async def test_exit_command_with_real_adapter(self):
        """测试使用真实适配器的 exit 命令"""
        print("\n🧪 测试使用真实适配器的 !music exit 命令")
        
        # 模拟 sys.exit 以避免实际退出
        with patch('sys.exit') as mock_exit:
            # 执行命令
            await self.music_commands._handle_exit_command(self.mock_ctx)
            
            # 验证进度条停止
            self.music_commands.progress_bar.stop_progress_updates.assert_called_once_with(self.mock_guild.id)
            
            # 验证保存状态 - 这应该通过适配器调用到 PlaybackEngine
            self.mock_playback_engine.manual_save.assert_called_once_with(self.mock_guild.id)
            
            # 验证断开连接
            self.mock_playback_engine.voice_manager.disconnect_from_guild.assert_called_once_with(self.mock_guild.id)
            
            # 验证回复消息
            self.mock_ctx.reply.assert_called_once()
            call_args = self.mock_ctx.reply.call_args
            embed = call_args.kwargs['embed']
            self.assertEqual(embed.title, "🔌 已断开连接")
            self.assertEqual(embed.description, "已终止进程。")
            self.assertEqual(embed.color, discord.Color.red())
            
            # 验证系统退出
            mock_exit.assert_called_once_with(0)
            
        print("   ✅ 真实适配器的 exit 命令验证通过")

    async def test_adapter_manual_save_delegation(self):
        """测试适配器的 manual_save 方法委托"""
        print("\n🧪 测试适配器 manual_save 方法委托")
        
        guild_id = 12345
        
        # 直接调用适配器的 manual_save 方法
        await self.music_player_adapter.manual_save(guild_id)
        
        # 验证调用被正确委托给 PlaybackEngine
        self.mock_playback_engine.manual_save.assert_called_once_with(guild_id)
        
        print("   ✅ 适配器 manual_save 方法委托验证通过")

    async def test_exit_command_with_manual_save_failure(self):
        """测试 manual_save 失败时的 exit 命令处理"""
        print("\n🧪 测试 manual_save 失败时的 exit 命令处理")
        
        # 模拟 manual_save 失败
        self.mock_playback_engine.manual_save.side_effect = Exception("持久化保存失败")
        
        # 执行命令
        await self.music_commands._handle_exit_command(self.mock_ctx)
        
        # 验证错误消息
        self.mock_ctx.reply.assert_called_once_with("❌ 断开连接时出错")
        
        # 验证 manual_save 被调用
        self.mock_playback_engine.manual_save.assert_called_once_with(self.mock_guild.id)
        
        print("   ✅ manual_save 失败时的错误处理验证通过")

    def test_adapter_has_required_methods(self):
        """测试适配器具有所需的方法"""
        print("\n🧪 测试适配器具有所需的方法")
        
        # 验证关键方法存在
        required_methods = [
            'manual_save',
            'voice_manager',
            'initialize_persistence',
            'cleanup_all'
        ]
        
        for method_name in required_methods:
            self.assertTrue(
                hasattr(self.music_player_adapter, method_name),
                f"适配器缺少方法: {method_name}"
            )
        
        # 验证 manual_save 是异步方法
        import inspect
        self.assertTrue(
            inspect.iscoroutinefunction(self.music_player_adapter.manual_save),
            "manual_save 应该是异步方法"
        )
        
        print("   ✅ 适配器具有所有必需的方法")

    async def test_complete_exit_flow_with_real_adapter(self):
        """测试使用真实适配器的完整 exit 流程"""
        print("\n🧪 测试使用真实适配器的完整 exit 流程")
        
        # 模拟 sys.exit 以避免实际退出
        with patch('sys.exit') as mock_exit:
            # 通过主命令路由执行 exit
            await self.music_commands.music_command(self.mock_ctx, "exit")
            
            # 验证完整流程
            self.music_commands.progress_bar.stop_progress_updates.assert_called_once_with(self.mock_guild.id)
            self.mock_playback_engine.manual_save.assert_called_once_with(self.mock_guild.id)
            self.mock_playback_engine.voice_manager.disconnect_from_guild.assert_called_once_with(self.mock_guild.id)
            
            # 验证系统退出
            mock_exit.assert_called_once_with(0)
            
        print("   ✅ 完整 exit 流程验证通过")


if __name__ == '__main__':
    print("🚀 开始真实适配器 exit 命令测试")
    unittest.main(verbosity=2)
