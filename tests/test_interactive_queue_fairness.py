"""
交互式队列公平性集成测试

测试完整的交互式队列公平性流程，包括：
1. 音乐命令与UI组件的集成
2. 队列管理器与交互系统的协作
3. 端到端的用户体验流程
4. 错误恢复和回退机制
"""

import unittest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
import discord
from discord.ext import commands

from similubot.commands.music_commands import MusicCommands
from similubot.core.interfaces import AudioInfo
from similubot.ui.button_interactions import InteractionResult
from similubot.queue.user_queue_status import UserQueueInfo


class TestInteractiveQueueFairness(unittest.IsolatedAsyncioTestCase):
    """交互式队列公平性集成测试类"""
    
    def setUp(self):
        """设置测试环境"""
        # 创建模拟的配置管理器
        self.mock_config_manager = Mock()
        self.mock_config_manager.get.return_value = True
        
        # 创建模拟的音乐播放器
        self.mock_music_player = Mock()
        self.mock_playback_engine = Mock()
        self.mock_music_player._playback_engine = self.mock_playback_engine
        self.mock_music_player.get_queue_manager = Mock()
        
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
        self.mock_ctx.send = AsyncMock()
        
        # 创建模拟用户
        self.mock_user = Mock(spec=discord.Member)
        self.mock_user.id = 67890
        self.mock_user.display_name = "TestUser"
        self.mock_ctx.author = self.mock_user
        
        # 创建测试音频信息
        self.new_audio_info = AudioInfo(
            title="New Song",
            uploader="New Artist",
            duration=200,
            url="http://example.com/new.mp3",
            thumbnail_url="http://example.com/thumb.jpg"
        )
        
        # 创建用户队列信息
        self.user_queue_info = UserQueueInfo(
            user_id=67890,
            user_name="TestUser",
            has_queued_song=True,
            queued_song_title="Existing Song",
            queue_position=2,
            estimated_play_time_seconds=300,
            is_currently_playing=False
        )
    
    async def test_successful_interactive_replacement(self):
        """测试成功的交互式替换流程"""
        print("\n🧪 测试成功的交互式替换流程")
        
        # 模拟队列管理器
        mock_queue_manager = Mock()
        mock_queue_manager.replace_user_song = AsyncMock(return_value=(True, 2, None))
        self.mock_music_player.get_queue_manager.return_value = mock_queue_manager
        
        # 模拟用户队列状态服务
        with patch('similubot.commands.music_commands.UserQueueStatusService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_user_queue_info.return_value = self.user_queue_info
            mock_service_class.return_value = mock_service
            
            # 模拟交互管理器返回REPLACED结果
            with patch('similubot.commands.music_commands.InteractionManager') as mock_manager_class:
                mock_manager = Mock()
                mock_manager.show_queue_fairness_replacement = AsyncMock(
                    return_value=(InteractionResult.REPLACED, None)
                )
                mock_manager_class.return_value = mock_manager
                
                # 执行交互式队列公平性处理
                result = await self.music_commands._handle_queue_fairness_interactive(
                    self.mock_ctx, self.new_audio_info, self.mock_user
                )
                
                # 验证处理成功
                self.assertTrue(result)
                
                # 验证交互管理器被调用
                mock_manager.show_queue_fairness_replacement.assert_called_once_with(
                    ctx=self.mock_ctx,
                    new_song_title="New Song",
                    existing_song_title="Existing Song",
                    queue_position=2
                )
                
                # 验证队列管理器被调用
                mock_queue_manager.replace_user_song.assert_called_once_with(
                    self.mock_user, self.new_audio_info
                )
                
                # 验证发送了成功消息
                self.mock_ctx.send.assert_called_once()
                call_args = self.mock_ctx.send.call_args
                embed = call_args[1]['embed']
                self.assertEqual(embed.title, "✅ 歌曲替换成功")
        
        print("   ✅ 交互式替换流程成功")
    
    async def test_user_denies_replacement(self):
        """测试用户拒绝替换"""
        print("\n🧪 测试用户拒绝替换")
        
        # 模拟用户队列状态服务
        with patch('similubot.commands.music_commands.UserQueueStatusService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_user_queue_info.return_value = self.user_queue_info
            mock_service_class.return_value = mock_service
            
            # 模拟交互管理器返回DENIED结果
            with patch('similubot.commands.music_commands.InteractionManager') as mock_manager_class:
                mock_manager = Mock()
                mock_manager.show_queue_fairness_replacement = AsyncMock(
                    return_value=(InteractionResult.DENIED, None)
                )
                mock_manager_class.return_value = mock_manager
                
                # 执行交互式队列公平性处理
                result = await self.music_commands._handle_queue_fairness_interactive(
                    self.mock_ctx, self.new_audio_info, self.mock_user
                )
                
                # 验证处理失败（用户拒绝）
                self.assertFalse(result)
                
                # 验证没有发送消息
                self.mock_ctx.send.assert_not_called()
        
        print("   ✅ 用户拒绝替换处理正确")
    
    async def test_interaction_timeout(self):
        """测试交互超时处理"""
        print("\n🧪 测试交互超时处理")
        
        # 模拟用户队列状态服务
        with patch('similubot.commands.music_commands.UserQueueStatusService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_user_queue_info.return_value = self.user_queue_info
            mock_service_class.return_value = mock_service
            
            # 模拟交互管理器返回TIMEOUT结果
            with patch('similubot.commands.music_commands.InteractionManager') as mock_manager_class:
                mock_manager = Mock()
                mock_manager.show_queue_fairness_replacement = AsyncMock(
                    return_value=(InteractionResult.TIMEOUT, None)
                )
                mock_manager_class.return_value = mock_manager
                
                # 执行交互式队列公平性处理
                result = await self.music_commands._handle_queue_fairness_interactive(
                    self.mock_ctx, self.new_audio_info, self.mock_user
                )
                
                # 验证处理失败（超时）
                self.assertFalse(result)
                
                # 验证没有发送消息
                self.mock_ctx.send.assert_not_called()
        
        print("   ✅ 交互超时处理正确")
    
    async def test_queue_replacement_failure(self):
        """测试队列替换失败处理"""
        print("\n🧪 测试队列替换失败处理")
        
        # 模拟队列管理器替换失败
        mock_queue_manager = Mock()
        mock_queue_manager.replace_user_song = AsyncMock(
            return_value=(False, None, "替换失败：歌曲正在播放")
        )
        self.mock_music_player.get_queue_manager.return_value = mock_queue_manager
        
        # 模拟用户队列状态服务
        with patch('similubot.commands.music_commands.UserQueueStatusService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_user_queue_info.return_value = self.user_queue_info
            mock_service_class.return_value = mock_service
            
            # 模拟交互管理器返回REPLACED结果
            with patch('similubot.commands.music_commands.InteractionManager') as mock_manager_class:
                mock_manager = Mock()
                mock_manager.show_queue_fairness_replacement = AsyncMock(
                    return_value=(InteractionResult.REPLACED, None)
                )
                mock_manager_class.return_value = mock_manager
                
                # 执行交互式队列公平性处理
                result = await self.music_commands._handle_queue_fairness_interactive(
                    self.mock_ctx, self.new_audio_info, self.mock_user
                )
                
                # 验证处理失败
                self.assertFalse(result)
                
                # 验证发送了错误消息
                self.mock_ctx.send.assert_called_once()
                call_args = self.mock_ctx.send.call_args
                embed = call_args[1]['embed']
                self.assertEqual(embed.title, "❌ 歌曲替换失败")
                self.assertIn("替换失败：歌曲正在播放", embed.description)
        
        print("   ✅ 队列替换失败处理正确")
    
    async def test_user_no_queued_song(self):
        """测试用户没有排队歌曲的情况"""
        print("\n🧪 测试用户没有排队歌曲的情况")
        
        # 创建没有排队歌曲的用户信息
        no_song_user_info = UserQueueInfo(
            user_id=67890,
            user_name="TestUser",
            has_queued_song=False
        )
        
        # 模拟用户队列状态服务
        with patch('similubot.commands.music_commands.UserQueueStatusService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_user_queue_info.return_value = no_song_user_info
            mock_service_class.return_value = mock_service
            
            # 执行交互式队列公平性处理
            result = await self.music_commands._handle_queue_fairness_interactive(
                self.mock_ctx, self.new_audio_info, self.mock_user
            )
            
            # 验证处理失败
            self.assertFalse(result)
            
            # 验证没有发送消息
            self.mock_ctx.send.assert_not_called()
        
        print("   ✅ 用户没有排队歌曲处理正确")
    
    async def test_exception_handling(self):
        """测试异常处理"""
        print("\n🧪 测试异常处理")
        
        # 模拟用户队列状态服务抛出异常
        with patch('similubot.commands.music_commands.UserQueueStatusService') as mock_service_class:
            mock_service_class.side_effect = Exception("Service error")
            
            # 执行交互式队列公平性处理
            result = await self.music_commands._handle_queue_fairness_interactive(
                self.mock_ctx, self.new_audio_info, self.mock_user
            )
            
            # 验证处理失败
            self.assertFalse(result)
            
            # 验证发送了错误消息
            self.mock_ctx.send.assert_called_once()
            call_args = self.mock_ctx.send.call_args
            embed = call_args[1]['embed']
            self.assertEqual(embed.title, "❌ 处理失败")
        
        print("   ✅ 异常处理正确")


if __name__ == '__main__':
    unittest.main()
