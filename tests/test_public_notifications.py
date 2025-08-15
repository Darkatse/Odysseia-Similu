"""
公共歌曲添加通知测试

测试歌曲添加到队列时的公共通知功能：
- 正常点歌的公共通知
- 抽卡歌曲的公共通知
- 通知内容的正确性
- 错误处理
"""

import unittest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from similubot.playback.playback_event import PlaybackEvent
from similubot.playback.playback_engine import PlaybackEngine
from similubot.core.interfaces import AudioInfo, SongInfo
from similubot.app_commands.card_draw.card_draw_commands import CardDrawCommands
from similubot.app_commands.card_draw.database import SongHistoryEntry
import discord


class MockBot:
    """模拟Discord机器人"""
    
    def __init__(self):
        self.get_channel = Mock()


class MockChannel:
    """模拟Discord频道"""
    
    def __init__(self):
        self.send = AsyncMock()


class MockMember:
    """模拟Discord成员"""
    
    def __init__(self, user_id: int, display_name: str):
        self.id = user_id
        self.display_name = display_name
        self.mention = f"<@{user_id}>"


class MockInteraction:
    """模拟Discord交互"""
    
    def __init__(self, user_id=12345, guild_id=67890):
        self.user = MockMember(user_id, "测试用户")
        self.guild = Mock()
        self.guild.id = guild_id
        self.channel = Mock()
        self.channel.id = 11111


class TestPublicNotifications(unittest.TestCase):
    """公共通知测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.mock_bot = MockBot()
        self.mock_channel = MockChannel()
        self.mock_bot.get_channel.return_value = self.mock_channel
        
        # 创建播放事件处理器
        self.playback_event = PlaybackEvent()
        
        # 创建测试数据
        self.test_audio_info = AudioInfo(
            title="测试歌曲",
            duration=180,
            url="https://youtube.com/watch?v=test",
            uploader="测试艺术家",
            thumbnail_url="https://example.com/thumb.jpg",
            file_format="mp4"
        )
        
        self.test_song_info = SongInfo(
            title="测试歌曲",
            duration=180,
            url="https://youtube.com/watch?v=test",
            requester=MockMember(12345, "测试用户"),
            uploader="测试艺术家",
            thumbnail_url="https://example.com/thumb.jpg"
        )
        
        self.guild_id = 67890
        self.channel_id = 11111
    
    async def test_song_added_notification_normal_song(self):
        """测试正常点歌的公共通知"""
        await self.playback_event.song_added_notification(
            bot=self.mock_bot,
            guild_id=self.guild_id,
            channel_id=self.channel_id,
            song=self.test_audio_info,
            position=1,
            source_type="点歌"
        )
        
        # 验证消息被发送
        self.mock_channel.send.assert_called_once()
        
        # 获取发送的嵌入消息
        call_args = self.mock_channel.send.call_args
        embed = call_args[1]['embed']
        
        # 验证嵌入消息内容
        self.assertEqual(embed.title, "🎵 歌曲已添加到队列")
        self.assertEqual(embed.color, discord.Color.green())
        self.assertIn("测试歌曲", str(embed.fields))
        self.assertIn("第 1 位", str(embed.fields))
    
    async def test_song_added_notification_card_draw(self):
        """测试抽卡歌曲的公共通知"""
        await self.playback_event.song_added_notification(
            bot=self.mock_bot,
            guild_id=self.guild_id,
            channel_id=self.channel_id,
            song=self.test_audio_info,
            position=3,
            source_type="抽卡"
        )
        
        # 验证消息被发送
        self.mock_channel.send.assert_called_once()
        
        # 获取发送的嵌入消息
        call_args = self.mock_channel.send.call_args
        embed = call_args[1]['embed']
        
        # 验证嵌入消息内容
        self.assertEqual(embed.title, "🎲 抽卡歌曲已添加到队列")
        self.assertEqual(embed.color, discord.Color.purple())
        self.assertIn("测试歌曲", str(embed.fields))
        self.assertIn("第 3 位", str(embed.fields))
    
    async def test_song_added_notification_with_song_info(self):
        """测试使用SongInfo对象的公共通知"""
        await self.playback_event.song_added_notification(
            bot=self.mock_bot,
            guild_id=self.guild_id,
            channel_id=self.channel_id,
            song=self.test_song_info,
            position=2,
            source_type="点歌"
        )
        
        # 验证消息被发送
        self.mock_channel.send.assert_called_once()
        
        # 获取发送的嵌入消息
        call_args = self.mock_channel.send.call_args
        embed = call_args[1]['embed']
        
        # 验证点歌人信息正确显示
        self.assertIn("<@12345>", str(embed.fields))
    
    async def test_song_added_notification_channel_not_found(self):
        """测试频道不存在时的处理"""
        # 设置频道不存在
        self.mock_bot.get_channel.return_value = None
        
        await self.playback_event.song_added_notification(
            bot=self.mock_bot,
            guild_id=self.guild_id,
            channel_id=99999,  # 不存在的频道ID
            song=self.test_audio_info,
            position=1,
            source_type="点歌"
        )
        
        # 验证没有发送消息
        self.mock_channel.send.assert_not_called()
    
    async def test_song_added_notification_error_handling(self):
        """测试通知发送时的错误处理"""
        # 设置发送消息时抛出异常
        self.mock_channel.send.side_effect = Exception("发送失败")
        
        # 应该不抛出异常
        await self.playback_event.song_added_notification(
            bot=self.mock_bot,
            guild_id=self.guild_id,
            channel_id=self.channel_id,
            song=self.test_audio_info,
            position=1,
            source_type="点歌"
        )
        
        # 验证尝试发送了消息
        self.mock_channel.send.assert_called_once()
    
    def test_format_duration(self):
        """测试时长格式化功能"""
        # 测试不同时长的格式化
        self.assertEqual(self.playback_event._format_duration(60), "1:00")
        self.assertEqual(self.playback_event._format_duration(125), "2:05")
        self.assertEqual(self.playback_event._format_duration(3661), "61:01")
        self.assertEqual(self.playback_event._format_duration(0), "0:00")


class TestPlaybackEngineNotificationTrigger(unittest.TestCase):
    """播放引擎通知触发测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.mock_bot = Mock()
        self.mock_config = Mock()
        
        # 创建播放引擎
        with patch('similubot.playback.playback_engine.AudioProviderFactory'), \
             patch('similubot.playback.playback_engine.VoiceManager'), \
             patch('similubot.playback.playback_engine.SeekManager'):
            self.playback_engine = PlaybackEngine(
                bot=self.mock_bot,
                temp_dir="./temp",
                config=self.mock_config
            )
        
        # 模拟事件处理器
        self.mock_handler = AsyncMock()
        self.playback_engine.add_event_handler("song_added_notification", self.mock_handler)
        
        # 设置文本频道
        self.guild_id = 67890
        self.channel_id = 11111
        self.playback_engine.set_text_channel(self.guild_id, self.channel_id)
        
        # 创建测试数据
        self.test_audio_info = AudioInfo(
            title="测试歌曲",
            duration=180,
            url="https://youtube.com/watch?v=test",
            uploader="测试艺术家",
            thumbnail_url="https://example.com/thumb.jpg"
        )
    
    async def test_trigger_song_added_notification(self):
        """测试触发歌曲添加通知"""
        test_user = MockMember(12345, "测试用户")

        await self.playback_engine._trigger_song_added_notification(
            self.guild_id, self.test_audio_info, 1, "点歌", test_user
        )

        # 验证事件处理器被调用
        self.mock_handler.assert_called_once()

        # 验证调用参数
        call_kwargs = self.mock_handler.call_args[1]
        self.assertEqual(call_kwargs['guild_id'], self.guild_id)
        self.assertEqual(call_kwargs['channel_id'], self.channel_id)
        self.assertEqual(call_kwargs['song'], self.test_audio_info)
        self.assertEqual(call_kwargs['position'], 1)
        self.assertEqual(call_kwargs['source_type'], "点歌")
        self.assertEqual(call_kwargs['requester'], test_user)
    
    async def test_trigger_notification_no_text_channel(self):
        """测试没有设置文本频道时的处理"""
        # 使用没有设置文本频道的服务器ID
        unknown_guild_id = 99999
        
        await self.playback_engine._trigger_song_added_notification(
            unknown_guild_id, self.test_audio_info, 1, "点歌"
        )
        
        # 验证事件处理器没有被调用
        self.mock_handler.assert_not_called()


class TestCardDrawPublicNotification(unittest.TestCase):
    """抽卡公共通知测试类"""
    
    def setUp(self):
        """测试前准备"""
        # 创建模拟对象
        self.mock_config = Mock()
        self.mock_music_player = Mock()
        self.mock_playback_engine = Mock()
        self.mock_music_player._playback_engine = self.mock_playback_engine
        self.mock_playback_engine._trigger_song_added_notification = AsyncMock()
        
        self.mock_database = Mock()
        self.mock_selector = Mock()
        
        # 创建抽卡命令处理器
        self.card_draw_commands = CardDrawCommands(
            self.mock_config,
            self.mock_music_player,
            self.mock_database,
            self.mock_selector
        )
        
        # 创建测试数据
        self.test_interaction = MockInteraction()
        self.test_audio_info = AudioInfo(
            title="测试歌曲",
            duration=180,
            url="https://youtube.com/watch?v=test",
            uploader="测试艺术家"
        )
    
    async def test_trigger_public_notification_success(self):
        """测试成功触发公共通知"""
        await self.card_draw_commands._trigger_public_notification(
            self.test_interaction, self.test_audio_info, 1, "抽卡"
        )
        
        # 验证播放引擎的通知方法被调用
        self.mock_playback_engine._trigger_song_added_notification.assert_called_once_with(
            self.test_interaction.guild.id, self.test_audio_info, 1, "抽卡"
        )
    
    async def test_trigger_notification_no_guild(self):
        """测试没有服务器信息时的处理"""
        # 设置交互没有服务器信息
        self.test_interaction.guild = None
        
        await self.card_draw_commands._trigger_public_notification(
            self.test_interaction, self.test_audio_info, 1, "抽卡"
        )
        
        # 验证播放引擎的通知方法没有被调用
        self.mock_playback_engine._trigger_song_added_notification.assert_not_called()
    
    async def test_trigger_notification_no_playback_engine(self):
        """测试没有播放引擎时的处理"""
        # 移除播放引擎
        delattr(self.mock_music_player, '_playback_engine')
        
        await self.card_draw_commands._trigger_public_notification(
            self.test_interaction, self.test_audio_info, 1, "抽卡"
        )
        
        # 应该不抛出异常，并且没有调用通知方法


# 异步测试运行器
def run_async_test(coro):
    """运行异步测试"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# 将异步测试方法包装为同步方法
def make_async_test_methods():
    """为异步测试方法创建同步包装器"""
    test_classes = [TestPublicNotifications, TestPlaybackEngineNotificationTrigger, TestCardDrawPublicNotification]
    
    for test_class in test_classes:
        async_methods = [name for name in dir(test_class) 
                        if name.startswith('test_') and asyncio.iscoroutinefunction(getattr(test_class, name))]
        
        for method_name in async_methods:
            async_method = getattr(test_class, method_name)
            
            def make_sync_wrapper(async_func):
                def sync_wrapper(self):
                    return run_async_test(async_func(self))
                return sync_wrapper
            
            setattr(test_class, method_name, make_sync_wrapper(async_method))


# 应用异步测试包装器
make_async_test_methods()


if __name__ == '__main__':
    unittest.main()
