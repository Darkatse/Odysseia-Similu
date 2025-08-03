"""
!music my 命令集成测试

测试 !music my 命令的各种场景：
1. 用户没有歌曲在队列中
2. 用户歌曲正在播放
3. 用户歌曲在队列中等待
4. 错误处理
"""

import unittest
from unittest.mock import Mock, AsyncMock, patch
import discord
from discord.ext import commands

from similubot.commands.music_commands import MusicCommands
from similubot.queue.user_queue_status import UserQueueInfo


class TestMusicMyCommand(unittest.IsolatedAsyncioTestCase):
    """!music my 命令测试类"""
    
    def setUp(self):
        """设置测试环境"""
        # 创建模拟的音乐播放器
        self.mock_music_player = Mock()
        self.mock_playback_engine = Mock()
        self.mock_music_player._playback_engine = self.mock_playback_engine
        
        # 创建模拟的配置管理器
        self.mock_config_manager = Mock()
        self.mock_config_manager.get.return_value = True  # music.enabled = True
        
        # 创建音乐命令实例
        self.music_commands = MusicCommands(
            config=self.mock_config_manager,
            music_player=self.mock_music_player
        )
        
        # 创建模拟的Discord上下文
        self.mock_ctx = Mock(spec=commands.Context)
        self.mock_guild = Mock(spec=discord.Guild)
        self.mock_guild.id = 12345
        self.mock_ctx.guild = self.mock_guild
        
        self.mock_author = Mock(spec=discord.Member)
        self.mock_author.id = 67890
        self.mock_author.display_name = "TestUser"
        self.mock_ctx.author = self.mock_author
        
        # 创建模拟的回复方法
        self.mock_ctx.reply = AsyncMock()
    
    async def test_handle_my_command_no_song(self):
        """测试用户没有歌曲在队列中的情况"""
        print("\n🧪 测试 !music my 命令 - 用户没有歌曲")
        
        # 模拟用户没有歌曲的情况
        mock_user_info = UserQueueInfo(
            user_id=67890,
            user_name="TestUser",
            has_queued_song=False
        )
        
        with patch('similubot.commands.music_commands.UserQueueStatusService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_user_queue_info.return_value = mock_user_info
            mock_service_class.return_value = mock_service
            
            # 执行命令
            await self.music_commands._handle_my_command(self.mock_ctx)
            
            # 验证回复被调用
            self.mock_ctx.reply.assert_called_once()
            call_args = self.mock_ctx.reply.call_args
            embed = call_args[1]['embed']
            
            # 验证嵌入消息内容
            self.assertEqual(embed.title, "🎵 我的队列状态")
            self.assertIn("没有歌曲在队列中", embed.description)
            
            # 验证提示字段
            tip_field = next((field for field in embed.fields if field.name == "💡 提示"), None)
            self.assertIsNotNone(tip_field)
            self.assertIn("!music", tip_field.value)
            
        print("   ✅ 用户没有歌曲时显示正确消息")
    
    async def test_handle_my_command_currently_playing(self):
        """测试用户歌曲正在播放的情况"""
        print("\n🧪 测试 !music my 命令 - 歌曲正在播放")
        
        # 模拟用户歌曲正在播放的情况
        mock_user_info = UserQueueInfo(
            user_id=67890,
            user_name="TestUser",
            has_queued_song=True,
            queued_song_title="Test Song Playing",
            queue_position=0,
            estimated_play_time_seconds=0,
            is_currently_playing=True
        )
        
        with patch('similubot.commands.music_commands.UserQueueStatusService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_user_queue_info.return_value = mock_user_info
            mock_service_class.return_value = mock_service
            
            # 执行命令
            await self.music_commands._handle_my_command(self.mock_ctx)
            
            # 验证回复被调用
            self.mock_ctx.reply.assert_called_once()
            call_args = self.mock_ctx.reply.call_args
            embed = call_args[1]['embed']
            
            # 验证嵌入消息内容
            self.assertEqual(embed.title, "🎵 我的队列状态")
            self.assertIn("正在播放中", embed.description)
            self.assertEqual(embed.color, discord.Color.green())
            
            # 验证正在播放字段
            playing_field = next((field for field in embed.fields if field.name == "🎶 正在播放"), None)
            self.assertIsNotNone(playing_field)
            self.assertIn("Test Song Playing", playing_field.value)
            
        print("   ✅ 用户歌曲正在播放时显示正确消息")
    
    async def test_handle_my_command_queued_song(self):
        """测试用户歌曲在队列中等待的情况"""
        print("\n🧪 测试 !music my 命令 - 歌曲在队列中")
        
        # 模拟用户歌曲在队列中的情况
        mock_user_info = UserQueueInfo(
            user_id=67890,
            user_name="TestUser",
            has_queued_song=True,
            queued_song_title="Test Song Queued",
            queue_position=3,
            estimated_play_time_seconds=420,  # 7分钟
            is_currently_playing=False
        )
        
        with patch('similubot.commands.music_commands.UserQueueStatusService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_user_queue_info.return_value = mock_user_info
            mock_service_class.return_value = mock_service
            
            # 执行命令
            await self.music_commands._handle_my_command(self.mock_ctx)
            
            # 验证回复被调用
            self.mock_ctx.reply.assert_called_once()
            call_args = self.mock_ctx.reply.call_args
            embed = call_args[1]['embed']
            
            # 验证嵌入消息内容
            self.assertEqual(embed.title, "🎵 我的队列状态")
            self.assertIn("等待播放", embed.description)
            self.assertEqual(embed.color, discord.Color.orange())
            
            # 验证排队歌曲字段
            queued_field = next((field for field in embed.fields if field.name == "🎶 排队歌曲"), None)
            self.assertIsNotNone(queued_field)
            self.assertIn("Test Song Queued", queued_field.value)
            
            # 验证队列位置字段
            position_field = next((field for field in embed.fields if field.name == "📍 队列位置"), None)
            self.assertIsNotNone(position_field)
            self.assertIn("第 3 位", position_field.value)
            
            # 验证预计播放时间字段
            time_field = next((field for field in embed.fields if field.name == "⏰ 预计播放时间"), None)
            self.assertIsNotNone(time_field)
            self.assertIn("7分钟", time_field.value)
            
        print("   ✅ 用户歌曲在队列中时显示正确详细信息")
    
    async def test_handle_my_command_no_guild(self):
        """测试在非服务器环境中使用命令的情况"""
        print("\n🧪 测试 !music my 命令 - 非服务器环境")
        
        # 设置无服务器上下文
        self.mock_ctx.guild = None
        
        # 执行命令
        await self.music_commands._handle_my_command(self.mock_ctx)
        
        # 验证错误消息
        self.mock_ctx.reply.assert_called_once_with("❌ 此命令只能在服务器中使用")
        
        print("   ✅ 非服务器环境时显示正确错误消息")
    
    async def test_handle_my_command_no_playback_engine(self):
        """测试播放引擎未初始化的情况"""
        print("\n🧪 测试 !music my 命令 - 播放引擎未初始化")

        # 移除播放引擎属性
        delattr(self.mock_music_player, '_playback_engine')
        
        # 执行命令
        await self.music_commands._handle_my_command(self.mock_ctx)
        
        # 验证错误消息
        self.mock_ctx.reply.assert_called_once_with("❌ 音乐播放器未正确初始化")
        
        print("   ✅ 播放引擎未初始化时显示正确错误消息")
    
    async def test_handle_my_command_service_error(self):
        """测试服务出错的情况"""
        print("\n🧪 测试 !music my 命令 - 服务出错")
        
        with patch('similubot.commands.music_commands.UserQueueStatusService') as mock_service_class:
            # 模拟服务初始化时出错
            mock_service_class.side_effect = Exception("Service initialization error")
            
            # 执行命令
            await self.music_commands._handle_my_command(self.mock_ctx)
            
            # 验证错误消息
            self.mock_ctx.reply.assert_called_once_with("❌ 获取您的队列状态时出错")
            
        print("   ✅ 服务出错时显示正确错误消息")
    
    async def test_music_command_routing(self):
        """测试音乐命令路由到 my 子命令"""
        print("\n🧪 测试音乐命令路由")
        
        # 模拟 _handle_my_command 方法
        self.music_commands._handle_my_command = AsyncMock()
        
        # 测试不同的 my 命令别名
        test_cases = ["my", "mine", "mystatus"]
        
        for subcommand in test_cases:
            # 重置模拟
            self.music_commands._handle_my_command.reset_mock()
            
            # 执行命令
            await self.music_commands.music_command(self.mock_ctx, subcommand)
            
            # 验证正确的处理方法被调用
            self.music_commands._handle_my_command.assert_called_once_with(self.mock_ctx)
            
            print(f"   ✅ '{subcommand}' 命令正确路由到 _handle_my_command")


if __name__ == '__main__':
    print("🚀 开始 !music my 命令集成测试")
    unittest.main(verbosity=2)
