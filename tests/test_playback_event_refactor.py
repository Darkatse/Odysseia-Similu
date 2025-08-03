"""
测试重构后的 PlaybackEvent 类功能
"""

import unittest
import asyncio
import sys
import os
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
import discord

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from similubot.playback.playback_event import PlaybackEvent
from similubot.core.interfaces import SongInfo, AudioInfo
from similubot.adapters.music_player_adapter import MusicPlayerAdapter


class TestPlaybackEventRefactor(unittest.TestCase):
    """测试重构后的 PlaybackEvent 类"""

    def setUp(self):
        """设置测试环境"""
        # 创建模拟的音乐播放器适配器
        self.mock_adapter = MagicMock(spec=MusicPlayerAdapter)
        self.mock_adapter.get_queue_info = AsyncMock()
        
        # 创建 PlaybackEvent 实例
        self.playback_event = PlaybackEvent(music_player_adapter=self.mock_adapter)
        
        # 创建模拟的 Discord 对象
        self.mock_bot = MagicMock()
        self.mock_channel = MagicMock()
        self.mock_channel.send = AsyncMock()
        self.mock_bot.get_channel.return_value = self.mock_channel
        
        # 创建模拟的歌曲信息
        self.mock_audio_info = AudioInfo(
            title="Test Song",
            duration=180,
            file_path="/test/path.mp3",
            url="https://example.com/test.mp3",
            uploader="Test Uploader",
            thumbnail_url="https://example.com/thumb.jpg"
        )
        
        self.mock_requester = MagicMock()
        self.mock_requester.name = "TestUser"
        self.mock_requester.display_name = "Test User"
        self.mock_requester.mention = "<@123456789>"
        
        self.mock_song = SongInfo(
            audio_info=self.mock_audio_info,
            requester=self.mock_requester,
            added_at=datetime.now()
        )

    def test_init_without_adapter(self):
        """测试不带适配器的初始化"""
        event = PlaybackEvent()
        self.assertIsNone(event.music_player_adapter)
        self.assertIsNone(event.progress_bar)  # 没有适配器时进度条为None
        self.assertIsNotNone(event.logger)

    def test_init_with_adapter(self):
        """测试带适配器的初始化"""
        self.assertIsNotNone(self.playback_event.music_player_adapter)
        self.assertEqual(self.playback_event.music_player_adapter, self.mock_adapter)

    def test_format_duration(self):
        """测试时长格式化功能"""
        test_cases = [
            (30, "0:30"),
            (90, "1:30"),
            (3600, "1:00:00"),
            (3661, "1:01:01"),
            (0, "0:00")
        ]
        
        for seconds, expected in test_cases:
            with self.subTest(seconds=seconds):
                result = self.playback_event._format_duration(seconds)
                self.assertEqual(result, expected)

    async def test_show_song_info_channel_not_found(self):
        """测试频道不存在时的处理"""
        self.mock_bot.get_channel.return_value = None
        
        # 应该不会抛出异常，只是记录警告
        await self.playback_event.show_song_info(
            bot=self.mock_bot,
            guild_id=12345,
            channel_id=67890,
            song=self.mock_song
        )
        
        # 验证没有尝试发送消息
        self.mock_channel.send.assert_not_called()

    async def test_show_song_info_with_adapter(self):
        """测试带适配器的歌曲信息显示"""
        # 设置适配器返回值
        self.mock_adapter.get_queue_info.return_value = {
            'playing': True,
            'paused': False
        }
        
        # 模拟进度条显示失败，使用静态显示
        with patch.object(self.playback_event.progress_bar, 'show_progress_bar', return_value=False):
            mock_response = MagicMock()
            mock_response.edit = AsyncMock()
            self.mock_channel.send.return_value = mock_response
            
            await self.playback_event.show_song_info(
                bot=self.mock_bot,
                guild_id=12345,
                channel_id=67890,
                song=self.mock_song
            )
            
            # 验证调用
            self.mock_channel.send.assert_called_once_with(content="正在加载进度条...")
            self.mock_adapter.get_queue_info.assert_called_once_with(12345)
            mock_response.edit.assert_called_once()

    async def test_show_song_info_without_adapter(self):
        """测试不带适配器的歌曲信息显示"""
        # 创建没有适配器的实例
        event = PlaybackEvent()
        
        with patch.object(event.progress_bar, 'show_progress_bar', return_value=False):
            mock_response = MagicMock()
            mock_response.edit = AsyncMock()
            self.mock_channel.send.return_value = mock_response
            
            await event.show_song_info(
                bot=self.mock_bot,
                guild_id=12345,
                channel_id=67890,
                song=self.mock_song
            )
            
            # 验证调用
            self.mock_channel.send.assert_called_once_with(content="正在加载进度条...")
            mock_response.edit.assert_called_once()

    async def test_song_requester_absent_skip(self):
        """测试点歌人不在时的跳过通知"""
        await self.playback_event.song_requester_absent_skip(
            bot=self.mock_bot,
            guild_id=12345,
            channel_id=67890,
            song=self.mock_song
        )
        
        # 验证发送了嵌入消息
        self.mock_channel.send.assert_called_once()
        call_args = self.mock_channel.send.call_args
        self.assertIn('embed', call_args.kwargs)
        
        embed = call_args.kwargs['embed']
        self.assertEqual(embed.title, "⏭️ 歌曲已跳过")
        self.assertIn("TestUser", embed.description)
        self.assertIn("Test Song", embed.description)

    async def test_your_song_notification(self):
        """测试轮到你的歌通知"""
        await self.playback_event.your_song_notification(
            bot=self.mock_bot,
            guild_id=12345,
            channel_id=67890,
            song=self.mock_song
        )
        
        # 验证发送了嵌入消息
        self.mock_channel.send.assert_called_once()
        call_args = self.mock_channel.send.call_args
        self.assertIn('embed', call_args.kwargs)
        
        embed = call_args.kwargs['embed']
        self.assertEqual(embed.title, "📣 轮到你的歌了")
        self.assertIn("Test Song", embed.description)

    async def test_error_handling(self):
        """测试错误处理"""
        # 模拟发送消息时出错
        self.mock_channel.send.side_effect = Exception("Test error")
        
        # 应该不会抛出异常，只是记录错误
        await self.playback_event.song_requester_absent_skip(
            bot=self.mock_bot,
            guild_id=12345,
            channel_id=67890,
            song=self.mock_song
        )
        
        # 验证尝试了发送消息
        self.mock_channel.send.assert_called_once()


def run_async_test(coro):
    """运行异步测试的辅助函数"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


if __name__ == '__main__':
    # 为异步测试方法添加运行器
    test_methods = [
        'test_show_song_info_channel_not_found',
        'test_show_song_info_with_adapter', 
        'test_show_song_info_without_adapter',
        'test_song_requester_absent_skip',
        'test_your_song_notification',
        'test_error_handling'
    ]
    
    for method_name in test_methods:
        original_method = getattr(TestPlaybackEventRefactor, method_name)
        setattr(TestPlaybackEventRefactor, method_name, 
                lambda self, method=original_method: run_async_test(method(self)))
    
    unittest.main()
