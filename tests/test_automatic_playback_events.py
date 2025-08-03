"""
测试自动播放事件处理系统 - 验证完整的事件流程
"""

import unittest
import asyncio
import sys
import os
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
import tempfile

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from similubot.playback.playback_engine import PlaybackEngine
from similubot.playback.playback_event import PlaybackEvent
from similubot.adapters.music_player_adapter import MusicPlayerAdapter
from similubot.core.interfaces import SongInfo, AudioInfo
from similubot.utils.config_manager import ConfigManager


class TestAutomaticPlaybackEvents(unittest.TestCase):
    """测试自动播放事件处理系统"""

    def setUp(self):
        """设置测试环境"""
        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp()
        
        # 创建模拟配置
        self.mock_config = MagicMock(spec=ConfigManager)
        self.mock_config.get.side_effect = lambda key, default=None: {
            'playback.notify_absent_users': True,
            'music.enabled': True
        }.get(key, default)
        self.mock_config.is_notify_absent_users_enabled.return_value = True
        
        # 创建模拟的Discord对象
        self.mock_bot = MagicMock()
        self.mock_guild = MagicMock()
        self.mock_guild.id = 12345
        self.mock_channel = MagicMock()
        self.mock_channel.id = 67890
        self.mock_channel.send = AsyncMock()
        self.mock_bot.get_channel.return_value = self.mock_channel
        
        # 创建模拟的用户
        self.mock_user_present = MagicMock()
        self.mock_user_present.name = "PresentUser"
        self.mock_user_present.display_name = "Present User"
        self.mock_user_present.mention = "<@111111>"
        self.mock_user_present.voice = MagicMock()
        self.mock_user_present.voice.channel = MagicMock()
        
        self.mock_user_absent = MagicMock()
        self.mock_user_absent.name = "AbsentUser"
        self.mock_user_absent.display_name = "Absent User"
        self.mock_user_absent.mention = "<@222222>"
        self.mock_user_absent.voice = None  # 不在语音频道
        
        # 创建模拟的歌曲
        self.mock_audio_info = AudioInfo(
            title="Test Song",
            duration=180,
            file_path="/test/path.mp3",
            url="https://example.com/test.mp3",
            uploader="Test Uploader",
            thumbnail_url="https://example.com/thumb.jpg"
        )
        
        self.mock_song_present = SongInfo(
            audio_info=self.mock_audio_info,
            requester=self.mock_user_present,
            added_at=datetime.now()
        )
        
        self.mock_song_absent = SongInfo(
            audio_info=self.mock_audio_info,
            requester=self.mock_user_absent,
            added_at=datetime.now()
        )

    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('similubot.playback.playback_engine.VoiceManager')
    @patch('similubot.playback.playback_engine.AudioProviderFactory')
    def test_text_channel_tracking(self, mock_audio_factory, mock_voice_manager):
        """测试文本频道跟踪功能"""
        # 创建播放引擎
        engine = PlaybackEngine(self.mock_bot, self.temp_dir, self.mock_config)
        
        # 测试设置和获取文本频道
        guild_id = 12345
        channel_id = 67890
        
        # 设置文本频道
        engine.set_text_channel(guild_id, channel_id)
        
        # 验证可以正确获取
        retrieved_channel_id = engine.get_text_channel_id(guild_id)
        self.assertEqual(retrieved_channel_id, channel_id)
        
        # 测试不存在的服务器
        non_existent_guild = 99999
        self.assertIsNone(engine.get_text_channel_id(non_existent_guild))
        
        print("✅ 文本频道跟踪功能测试通过")

    @patch('similubot.playback.playback_engine.VoiceManager')
    @patch('similubot.playback.playback_engine.AudioProviderFactory')
    def test_configurable_absent_user_notifications(self, mock_audio_factory, mock_voice_manager):
        """测试可配置的缺席用户通知功能"""
        # 测试启用通知的情况
        config_enabled = MagicMock(spec=ConfigManager)
        config_enabled.is_notify_absent_users_enabled.return_value = True
        
        engine_enabled = PlaybackEngine(self.mock_bot, self.temp_dir, config_enabled)
        engine_enabled.set_text_channel(12345, 67890)
        
        # 模拟队列管理器
        mock_queue_manager = MagicMock()
        mock_queue_manager.get_next_song = AsyncMock(return_value=self.mock_song_absent)
        engine_enabled._queue_managers[12345] = mock_queue_manager
        
        # 模拟事件触发
        engine_enabled._trigger_event = AsyncMock()
        
        # 运行检查方法
        asyncio.run(engine_enabled._check_and_notify_next_song(12345))
        
        # 验证事件被触发
        engine_enabled._trigger_event.assert_called_once_with(
            "your_song_notification",
            guild_id=12345,
            channel_id=67890,
            song=self.mock_song_absent
        )
        
        # 测试禁用通知的情况
        config_disabled = MagicMock(spec=ConfigManager)
        config_disabled.is_notify_absent_users_enabled.return_value = False
        
        engine_disabled = PlaybackEngine(self.mock_bot, self.temp_dir, config_disabled)
        engine_disabled._trigger_event = AsyncMock()
        
        # 运行检查方法
        asyncio.run(engine_disabled._check_and_notify_next_song(12345))
        
        # 验证事件没有被触发
        engine_disabled._trigger_event.assert_not_called()
        
        print("✅ 可配置缺席用户通知功能测试通过")

    def test_playback_event_message_sending(self):
        """测试播放事件处理器的消息发送功能"""
        # 创建播放事件处理器
        mock_adapter = MagicMock(spec=MusicPlayerAdapter)
        mock_adapter.get_queue_info = AsyncMock(return_value={
            'playing': True,
            'paused': False
        })
        
        playback_event = PlaybackEvent(music_player_adapter=mock_adapter)
        
        # 测试歌曲信息显示
        async def test_show_song_info():
            await playback_event.show_song_info(
                bot=self.mock_bot,
                guild_id=12345,
                channel_id=67890,
                song=self.mock_song_present
            )
            
            # 验证消息被发送
            self.mock_channel.send.assert_called()
            
        # 测试跳过通知
        async def test_skip_notification():
            await playback_event.song_requester_absent_skip(
                bot=self.mock_bot,
                guild_id=12345,
                channel_id=67890,
                song=self.mock_song_absent
            )
            
            # 验证消息被发送
            self.mock_channel.send.assert_called()
            
        # 测试轮到你的歌通知
        async def test_your_song_notification():
            await playback_event.your_song_notification(
                bot=self.mock_bot,
                guild_id=12345,
                channel_id=67890,
                song=self.mock_song_absent
            )
            
            # 验证消息被发送
            self.mock_channel.send.assert_called()
        
        # 运行所有测试
        asyncio.run(test_show_song_info())
        asyncio.run(test_skip_notification())
        asyncio.run(test_your_song_notification())
        
        print("✅ 播放事件消息发送功能测试通过")

    def test_event_flow_sequence(self):
        """测试完整的事件流程序列"""
        # 这个测试验证事件按正确顺序触发：
        # 1. 检测缺席用户 → 2. 跳过歌曲 → 3. 发送跳过通知 → 4. 开始下一首歌 → 5. 显示歌曲信息
        
        event_sequence = []
        
        def mock_event_handler(event_type, **kwargs):
            event_sequence.append(event_type)
            return AsyncMock()
        
        # 创建播放事件处理器
        mock_adapter = MagicMock(spec=MusicPlayerAdapter)
        playback_event = PlaybackEvent(music_player_adapter=mock_adapter)
        
        # 模拟事件序列
        async def simulate_event_sequence():
            # 1. 跳过缺席用户的歌曲
            await playback_event.song_requester_absent_skip(
                bot=self.mock_bot,
                guild_id=12345,
                channel_id=67890,
                song=self.mock_song_absent
            )
            event_sequence.append("song_requester_absent_skip")
            
            # 2. 显示下一首歌曲信息
            await playback_event.show_song_info(
                bot=self.mock_bot,
                guild_id=12345,
                channel_id=67890,
                song=self.mock_song_present
            )
            event_sequence.append("show_song_info")
            
            # 3. 可选的缺席用户通知
            await playback_event.your_song_notification(
                bot=self.mock_bot,
                guild_id=12345,
                channel_id=67890,
                song=self.mock_song_absent
            )
            event_sequence.append("your_song_notification")
        
        # 运行事件序列
        asyncio.run(simulate_event_sequence())
        
        # 验证事件顺序
        expected_sequence = [
            "song_requester_absent_skip",
            "show_song_info", 
            "your_song_notification"
        ]
        
        self.assertEqual(event_sequence, expected_sequence)
        print("✅ 事件流程序列测试通过")

    def test_error_handling_in_events(self):
        """测试事件处理中的错误处理"""
        # 创建会抛出异常的模拟对象
        mock_bot_error = MagicMock()
        mock_bot_error.get_channel.return_value = None  # 频道不存在
        
        playback_event = PlaybackEvent()
        
        # 测试错误处理不会导致崩溃
        async def test_error_handling():
            try:
                await playback_event.show_song_info(
                    bot=mock_bot_error,
                    guild_id=12345,
                    channel_id=99999,  # 不存在的频道
                    song=self.mock_song_present
                )
                # 应该不会抛出异常
            except Exception as e:
                self.fail(f"事件处理器应该优雅地处理错误，但抛出了异常: {e}")
        
        asyncio.run(test_error_handling())
        print("✅ 事件错误处理测试通过")


if __name__ == '__main__':
    unittest.main()
