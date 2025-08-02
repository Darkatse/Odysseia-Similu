"""
重复检测系统的集成测试

测试从音乐命令到队列添加的完整工作流程，验证用户反馈消息和与现有音乐机器人功能的交互。
"""

import unittest
import asyncio
import sys
import os
from unittest.mock import MagicMock, AsyncMock, patch

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from similubot.commands.music_commands import MusicCommands
from similubot.playback.playback_engine import PlaybackEngine
from similubot.adapters.music_player_adapter import MusicPlayerAdapter
from similubot.queue.queue_manager import QueueManager, DuplicateSongError
from similubot.core.interfaces import AudioInfo
from similubot.utils.config_manager import ConfigManager
import discord
from discord.ext import commands


class TestDuplicateDetectionIntegration(unittest.TestCase):
    """测试重复检测的完整集成"""
    
    def setUp(self):
        """设置测试环境"""
        # 创建模拟配置
        self.mock_config = MagicMock(spec=ConfigManager)
        self.mock_config.get.return_value = True  # Music enabled
        
        # 创建模拟播放引擎
        self.mock_playback_engine = MagicMock(spec=PlaybackEngine)
        
        # 创建音乐播放器适配器
        self.music_player = MusicPlayerAdapter(self.mock_playback_engine)
        
        # 创建音乐命令处理器
        self.music_commands = MusicCommands(self.mock_config, self.music_player)
        
        # 创建模拟上下文
        self.mock_ctx = MagicMock(spec=commands.Context)
        self.mock_ctx.guild = MagicMock()
        self.mock_ctx.guild.id = 12345
        
        # 创建模拟用户
        self.mock_user = MagicMock(spec=discord.Member)
        self.mock_user.id = 1001
        self.mock_user.display_name = "TestUser"
        self.mock_user.voice = MagicMock()
        self.mock_user.voice.channel = MagicMock()
        
        self.mock_ctx.author = self.mock_user
        self.mock_ctx.reply = AsyncMock()
        
        # 创建测试音频信息
        self.test_audio_info = AudioInfo(
            title="Test Song",
            duration=180,
            url="https://www.youtube.com/watch?v=test123",
            uploader="Test Channel",
            thumbnail_url="https://example.com/thumb.jpg"
        )
    
    async def test_successful_song_addition(self):
        """测试成功添加歌曲的完整流程"""
        # 模拟成功的操作
        self.mock_playback_engine.connect_to_user_channel.return_value = (True, None)
        self.mock_playback_engine.add_song_to_queue.return_value = (True, 1, None)
        
        # 模拟音频信息提取
        youtube_provider = MagicMock()
        youtube_provider.extract_audio_info.return_value = self.test_audio_info
        self.mock_playback_engine.audio_provider_factory.get_provider_by_name.return_value = youtube_provider
        
        # 模拟URL支持检查
        self.mock_playback_engine.audio_provider_factory.is_supported_url.return_value = True
        self.mock_playback_engine.audio_provider_factory.detect_provider_for_url.return_value = MagicMock()
        self.mock_playback_engine.audio_provider_factory.detect_provider_for_url.return_value.name = 'youtube'
        
        # 执行命令
        url = "https://www.youtube.com/watch?v=test123"
        await self.music_commands._handle_play_command(self.mock_ctx, url)
        
        # 验证调用
        self.mock_playback_engine.connect_to_user_channel.assert_called_once()
        self.mock_playback_engine.add_song_to_queue.assert_called_once()
        self.mock_ctx.reply.assert_called_once()
    
    async def test_duplicate_song_error_handling(self):
        """测试重复歌曲错误处理"""
        # 模拟成功连接但重复歌曲错误
        self.mock_playback_engine.connect_to_user_channel.return_value = (True, None)
        self.mock_playback_engine.add_song_to_queue.return_value = (
            False, None, "您已经请求了这首歌曲，请等待播放完成后再次请求。"
        )
        
        # 模拟URL支持检查
        self.mock_playback_engine.audio_provider_factory.is_supported_url.return_value = True
        self.mock_playback_engine.audio_provider_factory.detect_provider_for_url.return_value = MagicMock()
        self.mock_playback_engine.audio_provider_factory.detect_provider_for_url.return_value.name = 'youtube'
        
        # 执行命令
        url = "https://www.youtube.com/watch?v=test123"
        await self.music_commands._handle_play_command(self.mock_ctx, url)
        
        # 验证错误处理
        self.mock_ctx.reply.assert_called_once()
        # 检查是否调用了编辑方法（用于显示错误消息）
        call_args = self.mock_ctx.reply.call_args
        self.assertIsNotNone(call_args)
    
    async def test_user_not_in_voice_channel(self):
        """测试用户不在语音频道时的处理"""
        # 用户不在语音频道
        self.mock_ctx.author.voice = None
        
        url = "https://www.youtube.com/watch?v=test123"
        await self.music_commands._handle_play_command(self.mock_ctx, url)
        
        # 应该显示错误消息
        self.mock_ctx.reply.assert_called_once_with(
            "❌ You must be in a voice channel to play music!"
        )
    
    async def test_connection_failure(self):
        """测试连接失败的处理"""
        # 模拟连接失败
        self.mock_playback_engine.connect_to_user_channel.return_value = (False, "Connection failed")
        
        url = "https://www.youtube.com/watch?v=test123"
        await self.music_commands._handle_play_command(self.mock_ctx, url)
        
        # 应该显示连接错误
        self.mock_ctx.reply.assert_called_once_with("❌ Connection failed")


class TestPlaybackEngineDuplicateHandling(unittest.TestCase):
    """测试播放引擎的重复处理"""
    
    def setUp(self):
        """设置测试环境"""
        # 创建模拟组件
        self.mock_bot = MagicMock()
        self.mock_config = MagicMock()
        self.mock_voice_manager = MagicMock()
        self.mock_seek_manager = MagicMock()
        self.mock_audio_provider_factory = MagicMock()
        self.mock_persistence_manager = MagicMock()
        
        # 创建播放引擎
        self.playback_engine = PlaybackEngine(
            bot=self.mock_bot,
            config=self.mock_config,
            voice_manager=self.mock_voice_manager,
            seek_manager=self.mock_seek_manager,
            audio_provider_factory=self.mock_audio_provider_factory,
            persistence_manager=self.mock_persistence_manager
        )
        
        # 创建模拟用户
        self.mock_user = MagicMock(spec=discord.Member)
        self.mock_user.id = 1001
        self.mock_user.display_name = "TestUser"
        self.mock_user.guild = MagicMock()
        self.mock_user.guild.id = 12345
        
        # 创建测试音频信息
        self.test_audio_info = AudioInfo(
            title="Test Song",
            duration=180,
            url="https://www.youtube.com/watch?v=test123",
            uploader="Test Channel"
        )
    
    async def test_add_song_success(self):
        """测试成功添加歌曲"""
        # 模拟URL支持和音频信息提取
        self.mock_audio_provider_factory.is_supported_url.return_value = True
        self.mock_audio_provider_factory.extract_audio_info.return_value = self.test_audio_info
        
        # 模拟队列管理器
        mock_queue_manager = MagicMock()
        mock_queue_manager.add_song.return_value = 1  # 返回位置
        self.playback_engine._queue_managers[12345] = mock_queue_manager
        
        # 模拟不在播放状态
        self.playback_engine._playback_tasks = {}
        
        # 执行添加歌曲
        success, position, error = await self.playback_engine.add_song_to_queue(
            "https://www.youtube.com/watch?v=test123", self.mock_user
        )
        
        # 验证结果
        self.assertTrue(success)
        self.assertEqual(position, 1)
        self.assertIsNone(error)
    
    async def test_add_duplicate_song_error(self):
        """测试添加重复歌曲的错误处理"""
        # 模拟URL支持和音频信息提取
        self.mock_audio_provider_factory.is_supported_url.return_value = True
        self.mock_audio_provider_factory.extract_audio_info.return_value = self.test_audio_info
        
        # 模拟队列管理器抛出重复错误
        mock_queue_manager = MagicMock()
        mock_queue_manager.add_song.side_effect = DuplicateSongError(
            "您已经请求了这首歌曲，请等待播放完成后再次请求。",
            "Test Song",
            "TestUser"
        )
        self.playback_engine._queue_managers[12345] = mock_queue_manager
        
        # 执行添加歌曲
        success, position, error = await self.playback_engine.add_song_to_queue(
            "https://www.youtube.com/watch?v=test123", self.mock_user
        )
        
        # 验证结果
        self.assertFalse(success)
        self.assertIsNone(position)
        self.assertIn("已经请求了这首歌曲", error)
    
    async def test_unsupported_url(self):
        """测试不支持的URL"""
        # 模拟不支持的URL
        self.mock_audio_provider_factory.is_supported_url.return_value = False
        
        # 执行添加歌曲
        success, position, error = await self.playback_engine.add_song_to_queue(
            "https://unsupported.com/audio.mp3", self.mock_user
        )
        
        # 验证结果
        self.assertFalse(success)
        self.assertIsNone(position)
        self.assertEqual(error, "不支持的URL格式")
    
    async def test_audio_info_extraction_failure(self):
        """测试音频信息提取失败"""
        # 模拟URL支持但信息提取失败
        self.mock_audio_provider_factory.is_supported_url.return_value = True
        self.mock_audio_provider_factory.extract_audio_info.return_value = None
        
        # 执行添加歌曲
        success, position, error = await self.playback_engine.add_song_to_queue(
            "https://www.youtube.com/watch?v=invalid", self.mock_user
        )
        
        # 验证结果
        self.assertFalse(success)
        self.assertIsNone(position)
        self.assertEqual(error, "无法获取音频信息")


class TestQueueManagerRestoration(unittest.TestCase):
    """测试队列管理器的恢复功能"""
    
    def setUp(self):
        """设置测试环境"""
        self.queue_manager = QueueManager(guild_id=12345)
        
        # 创建模拟持久化管理器
        self.mock_persistence_manager = MagicMock()
        self.queue_manager.set_persistence_manager(self.mock_persistence_manager)
        
        # 创建模拟Discord服务器
        self.mock_guild = MagicMock(spec=discord.Guild)
        self.mock_guild.id = 12345
        
        # 创建模拟用户
        self.mock_user = MagicMock(spec=discord.Member)
        self.mock_user.id = 1001
        self.mock_user.display_name = "TestUser"
        
        # 创建测试歌曲
        from similubot.queue.song import Song
        self.test_song = Song(
            audio_info=AudioInfo(
                title="Test Song",
                duration=180,
                url="https://www.youtube.com/watch?v=test123",
                uploader="Test Channel"
            ),
            requester=self.mock_user
        )
    
    async def test_restore_with_duplicate_detection(self):
        """测试恢复时重建重复检测状态"""
        # 模拟恢复数据
        restored_data = {
            'current_song': None,
            'queue': [self.test_song],
            'current_position': 0.0,
            'invalid_songs': []
        }
        
        self.mock_persistence_manager.load_queue_state.return_value = restored_data
        
        # 执行恢复
        success = await self.queue_manager.restore_from_persistence(self.mock_guild)
        
        # 验证恢复成功
        self.assertTrue(success)
        
        # 验证重复检测器状态
        stats = self.queue_manager.get_duplicate_detection_stats()
        self.assertEqual(stats['total_tracked_songs'], 1)
        self.assertEqual(stats['total_users_with_songs'], 1)
        
        # 验证用户歌曲数量
        user_count = self.queue_manager.get_user_song_count(self.mock_user)
        self.assertEqual(user_count, 1)
    
    async def test_restore_failure(self):
        """测试恢复失败的处理"""
        # 模拟恢复失败
        self.mock_persistence_manager.load_queue_state.return_value = None
        
        # 执行恢复
        success = await self.queue_manager.restore_from_persistence(self.mock_guild)
        
        # 验证恢复失败
        self.assertFalse(success)


if __name__ == '__main__':
    # 运行异步测试
    async def run_async_tests():
        """运行所有异步测试"""
        test_classes = [
            TestDuplicateDetectionIntegration,
            TestPlaybackEngineDuplicateHandling,
            TestQueueManagerRestoration
        ]
        
        for test_class in test_classes:
            suite = unittest.TestLoader().loadTestsFromTestCase(test_class)
            
            for test in suite:
                if asyncio.iscoroutinefunction(getattr(test, test._testMethodName)):
                    try:
                        await getattr(test, test._testMethodName)()
                        print(f"✅ {test_class.__name__}.{test._testMethodName}")
                    except Exception as e:
                        print(f"❌ {test_class.__name__}.{test._testMethodName}: {e}")
                else:
                    try:
                        getattr(test, test._testMethodName)()
                        print(f"✅ {test_class.__name__}.{test._testMethodName}")
                    except Exception as e:
                        print(f"❌ {test_class.__name__}.{test._testMethodName}: {e}")
    
    # 运行测试
    asyncio.run(run_async_tests())
