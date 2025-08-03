"""
队列公平性消息改进测试

测试队列公平性拒绝消息的详细信息显示：
1. 显示用户当前排队的歌曲信息
2. 显示队列位置和预计播放时间
3. 错误处理和回退机制
"""

import unittest
from unittest.mock import Mock, AsyncMock, patch
import discord
from discord.ext import commands

from similubot.commands.music_commands import MusicCommands
from similubot.queue.user_queue_status import UserQueueInfo


class TestQueueFairnessMessage(unittest.IsolatedAsyncioTestCase):
    """队列公平性消息测试类"""
    
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
        
        # 创建模拟的Discord消息
        self.mock_message = Mock(spec=discord.Message)
        self.mock_guild = Mock(spec=discord.Guild)
        self.mock_guild.id = 12345
        self.mock_message.guild = self.mock_guild
        self.mock_message.edit = AsyncMock()
        
        # 创建模拟的用户
        self.mock_user = Mock(spec=discord.Member)
        self.mock_user.id = 67890
        self.mock_user.display_name = "TestUser"
    
    async def test_send_queue_fairness_embed_with_detailed_info(self):
        """测试发送包含详细信息的队列公平性消息"""
        print("\n🧪 测试队列公平性消息 - 包含详细信息")
        
        # 模拟用户有歌曲在队列中
        mock_user_info = UserQueueInfo(
            user_id=67890,
            user_name="TestUser",
            has_queued_song=True,
            queued_song_title="User's Queued Song",
            queue_position=2,
            estimated_play_time_seconds=300,  # 5分钟
            is_currently_playing=False
        )
        
        # 模拟队列信息
        mock_queue_info = {
            'queue_length': 5,
            'current_song': {
                'title': 'Currently Playing Song'
            }
        }
        self.mock_music_player.get_queue_info = AsyncMock(return_value=mock_queue_info)
        
        with patch('similubot.commands.music_commands.UserQueueStatusService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_user_queue_info.return_value = mock_user_info
            mock_service_class.return_value = mock_service
            
            # 执行方法
            await self.music_commands._send_queue_fairness_embed(
                self.mock_message, 
                "队列公平性错误消息", 
                self.mock_user
            )
            
            # 验证消息被编辑
            self.mock_message.edit.assert_called_once()
            call_args = self.mock_message.edit.call_args
            embed = call_args[1]['embed']
            
            # 验证基本信息
            self.assertEqual(embed.title, "⚖️ 队列公平性限制")
            self.assertEqual(embed.color, discord.Color.orange())
            
            # 验证用户排队歌曲信息字段
            queued_field = next((field for field in embed.fields if field.name == "🎶 您的排队歌曲"), None)
            self.assertIsNotNone(queued_field)
            self.assertIn("User's Queued Song", queued_field.value)
            self.assertIn("第 2 位", queued_field.value)
            self.assertIn("5分钟", queued_field.value)
            
            # 验证队列状态字段
            status_field = next((field for field in embed.fields if field.name == "📊 当前队列状态"), None)
            self.assertIsNotNone(status_field)
            self.assertIn("5 首歌曲", status_field.value)
            
            # 验证建议字段包含 !music my 命令提示
            suggestion_field = next((field for field in embed.fields if field.name == "💡 建议"), None)
            self.assertIsNotNone(suggestion_field)
            self.assertIn("!music my", suggestion_field.value)
            
        print("   ✅ 包含详细用户队列信息的消息格式正确")
    
    async def test_send_queue_fairness_embed_currently_playing(self):
        """测试用户歌曲正在播放时的队列公平性消息"""
        print("\n🧪 测试队列公平性消息 - 用户歌曲正在播放")
        
        # 模拟用户歌曲正在播放
        mock_user_info = UserQueueInfo(
            user_id=67890,
            user_name="TestUser",
            has_queued_song=True,
            queued_song_title="Currently Playing Song",
            queue_position=0,
            estimated_play_time_seconds=0,
            is_currently_playing=True
        )
        
        with patch('similubot.commands.music_commands.UserQueueStatusService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_user_queue_info.return_value = mock_user_info
            mock_service_class.return_value = mock_service
            
            # 执行方法
            await self.music_commands._send_queue_fairness_embed(
                self.mock_message, 
                "队列公平性错误消息", 
                self.mock_user
            )
            
            # 验证消息被编辑
            self.mock_message.edit.assert_called_once()
            call_args = self.mock_message.edit.call_args
            embed = call_args[1]['embed']
            
            # 验证用户歌曲状态字段
            status_field = next((field for field in embed.fields if field.name == "🎶 您的歌曲状态"), None)
            self.assertIsNotNone(status_field)
            self.assertIn("Currently Playing Song", status_field.value)
            self.assertIn("正在播放中", status_field.value)
            
        print("   ✅ 用户歌曲正在播放时显示正确状态")
    
    async def test_send_queue_fairness_embed_no_user_song(self):
        """测试用户没有歌曲时的队列公平性消息"""
        print("\n🧪 测试队列公平性消息 - 用户没有歌曲")
        
        # 模拟用户没有歌曲
        mock_user_info = UserQueueInfo(
            user_id=67890,
            user_name="TestUser",
            has_queued_song=False
        )
        
        # 模拟队列信息
        mock_queue_info = {'queue_length': 3}
        self.mock_music_player.get_queue_info = AsyncMock(return_value=mock_queue_info)
        
        with patch('similubot.commands.music_commands.UserQueueStatusService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_user_queue_info.return_value = mock_user_info
            mock_service_class.return_value = mock_service
            
            # 执行方法
            await self.music_commands._send_queue_fairness_embed(
                self.mock_message, 
                "队列公平性错误消息", 
                self.mock_user
            )
            
            # 验证消息被编辑
            self.mock_message.edit.assert_called_once()
            call_args = self.mock_message.edit.call_args
            embed = call_args[1]['embed']
            
            # 验证没有用户歌曲相关字段
            user_song_fields = [field for field in embed.fields if "您的" in field.name]
            self.assertEqual(len(user_song_fields), 0)
            
            # 但应该有队列状态字段
            status_field = next((field for field in embed.fields if field.name == "📊 当前队列状态"), None)
            self.assertIsNotNone(status_field)
            self.assertIn("3 首歌曲", status_field.value)
            
        print("   ✅ 用户没有歌曲时不显示用户歌曲信息")
    
    async def test_send_queue_fairness_embed_service_error(self):
        """测试服务出错时的回退机制"""
        print("\n🧪 测试队列公平性消息 - 服务出错回退")
        
        # 模拟基本队列信息（回退机制）
        mock_queue_info = {'queue_length': 4}
        self.mock_music_player.get_queue_info = AsyncMock(return_value=mock_queue_info)
        
        with patch('similubot.commands.music_commands.UserQueueStatusService') as mock_service_class:
            # 模拟服务出错
            mock_service_class.side_effect = Exception("Service error")
            
            # 执行方法
            await self.music_commands._send_queue_fairness_embed(
                self.mock_message, 
                "队列公平性错误消息", 
                self.mock_user
            )
            
            # 验证消息被编辑
            self.mock_message.edit.assert_called_once()
            call_args = self.mock_message.edit.call_args
            embed = call_args[1]['embed']
            
            # 验证基本信息仍然存在
            self.assertEqual(embed.title, "⚖️ 队列公平性限制")
            
            # 验证回退到基本队列状态信息
            status_field = next((field for field in embed.fields if field.name == "📊 当前队列状态"), None)
            self.assertIsNotNone(status_field)
            self.assertIn("4 首歌曲", status_field.value)
            
            # 验证建议字段仍然存在
            suggestion_field = next((field for field in embed.fields if field.name == "💡 建议"), None)
            self.assertIsNotNone(suggestion_field)
            
        print("   ✅ 服务出错时正确回退到基本信息")
    
    async def test_send_queue_fairness_embed_no_guild(self):
        """测试没有服务器信息时的处理"""
        print("\n🧪 测试队列公平性消息 - 没有服务器信息")
        
        # 设置没有服务器的消息
        self.mock_message.guild = None
        
        # 执行方法
        await self.music_commands._send_queue_fairness_embed(
            self.mock_message, 
            "队列公平性错误消息", 
            self.mock_user
        )
        
        # 验证消息被编辑
        self.mock_message.edit.assert_called_once()
        call_args = self.mock_message.edit.call_args
        embed = call_args[1]['embed']
        
        # 验证基本信息存在
        self.assertEqual(embed.title, "⚖️ 队列公平性限制")
        
        # 验证队列规则字段存在
        rules_field = next((field for field in embed.fields if field.name == "📋 队列规则"), None)
        self.assertIsNotNone(rules_field)
        
        print("   ✅ 没有服务器信息时仍能显示基本消息")
    
    async def test_send_queue_fairness_embed_non_member_user(self):
        """测试非成员用户的处理"""
        print("\n🧪 测试队列公平性消息 - 非成员用户")
        
        # 创建非成员用户
        mock_non_member_user = Mock(spec=discord.User)
        mock_non_member_user.id = 11111
        mock_non_member_user.display_name = "NonMemberUser"
        
        # 模拟队列信息
        mock_queue_info = {'queue_length': 2}
        self.mock_music_player.get_queue_info = AsyncMock(return_value=mock_queue_info)

        # 确保 hasattr 检查通过
        self.assertTrue(hasattr(self.mock_music_player, 'get_queue_info'))
        
        # 执行方法
        await self.music_commands._send_queue_fairness_embed(
            self.mock_message, 
            "队列公平性错误消息", 
            mock_non_member_user
        )
        
        # 验证消息被编辑
        self.mock_message.edit.assert_called_once()
        call_args = self.mock_message.edit.call_args
        embed = call_args[1]['embed']
        
        # 验证基本信息存在
        self.assertEqual(embed.title, "⚖️ 队列公平性限制")
        
        # 验证队列状态字段存在（回退机制）
        status_field = next((field for field in embed.fields if field.name == "📊 当前队列状态"), None)
        self.assertIsNotNone(status_field)
        self.assertIn("2 首歌曲", status_field.value)
        
        print("   ✅ 非成员用户时正确回退到基本信息")


if __name__ == '__main__':
    print("🚀 开始队列公平性消息改进测试")
    unittest.main(verbosity=2)
