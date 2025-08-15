"""
请求者信息修复测试

测试公共通知中正确显示请求者信息的功能：
- AudioInfo对象通过requester参数传递请求者信息
- SongInfo对象使用内置的requester属性
- 向后兼容性测试
- 错误处理测试
"""

import unittest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from similubot.playback.playback_event import PlaybackEvent
from similubot.playback.playback_engine import PlaybackEngine
from similubot.core.interfaces import AudioInfo, SongInfo
from similubot.app_commands.card_draw.card_draw_commands import CardDrawCommands
import discord


class MockMember:
    """模拟Discord成员对象"""
    
    def __init__(self, user_id: int, display_name: str):
        self.id = user_id
        self.display_name = display_name
        self.mention = f"<@{user_id}>"
        self.guild = Mock()
        self.guild.id = 67890


class MockBot:
    """模拟Discord机器人"""
    
    def __init__(self):
        self.get_channel = Mock()


class MockChannel:
    """模拟Discord频道"""
    
    def __init__(self):
        self.send = AsyncMock()


class MockInteraction:
    """模拟Discord交互"""
    
    def __init__(self, user_id=12345, guild_id=67890):
        self.user = MockMember(user_id, "测试用户")
        self.guild = Mock()
        self.guild.id = guild_id
        self.channel = Mock()
        self.channel.id = 11111


class TestRequesterFix(unittest.TestCase):
    """请求者信息修复测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.mock_bot = MockBot()
        self.mock_channel = MockChannel()
        self.mock_bot.get_channel.return_value = self.mock_channel
        
        # 创建播放事件处理器
        self.playback_event = PlaybackEvent()
        
        # 创建测试用户
        self.test_user = MockMember(12345, "测试用户")
        self.another_user = MockMember(67890, "另一个用户")
        
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
            requester=self.test_user,
            uploader="测试艺术家",
            thumbnail_url="https://example.com/thumb.jpg"
        )
        
        self.guild_id = 67890
        self.channel_id = 11111
    
    async def test_audio_info_with_requester_parameter(self):
        """测试AudioInfo对象通过requester参数传递请求者信息"""
        await self.playback_event.song_added_notification(
            bot=self.mock_bot,
            guild_id=self.guild_id,
            channel_id=self.channel_id,
            song=self.test_audio_info,
            position=1,
            source_type="点歌",
            requester=self.test_user
        )
        
        # 验证消息被发送
        self.mock_channel.send.assert_called_once()
        
        # 获取发送的嵌入消息
        call_args = self.mock_channel.send.call_args
        embed = call_args[1]['embed']
        
        # 验证请求者信息正确显示
        embed_dict = embed.to_dict()
        requester_field = None
        for field in embed_dict.get('fields', []):
            if field['name'] == '点歌人':
                requester_field = field
                break
        
        self.assertIsNotNone(requester_field, "未找到点歌人字段")
        self.assertEqual(requester_field['value'], "<@12345>", f"请求者信息错误: {requester_field['value']}")
    
    async def test_song_info_with_builtin_requester(self):
        """测试SongInfo对象使用内置的requester属性"""
        await self.playback_event.song_added_notification(
            bot=self.mock_bot,
            guild_id=self.guild_id,
            channel_id=self.channel_id,
            song=self.test_song_info,
            position=1,
            source_type="点歌"
            # 注意：这里没有传递requester参数，应该使用SongInfo内置的requester
        )
        
        # 验证消息被发送
        self.mock_channel.send.assert_called_once()
        
        # 获取发送的嵌入消息
        call_args = self.mock_channel.send.call_args
        embed = call_args[1]['embed']
        
        # 验证请求者信息正确显示
        embed_dict = embed.to_dict()
        requester_field = None
        for field in embed_dict.get('fields', []):
            if field['name'] == '点歌人':
                requester_field = field
                break
        
        self.assertIsNotNone(requester_field, "未找到点歌人字段")
        self.assertEqual(requester_field['value'], "<@12345>", f"请求者信息错误: {requester_field['value']}")
    
    async def test_requester_parameter_overrides_song_requester(self):
        """测试requester参数优先级高于song对象的requester属性"""
        await self.playback_event.song_added_notification(
            bot=self.mock_bot,
            guild_id=self.guild_id,
            channel_id=self.channel_id,
            song=self.test_song_info,  # 内置requester是test_user (12345)
            position=1,
            source_type="点歌",
            requester=self.another_user  # 传入的requester是another_user (67890)
        )
        
        # 验证消息被发送
        self.mock_channel.send.assert_called_once()
        
        # 获取发送的嵌入消息
        call_args = self.mock_channel.send.call_args
        embed = call_args[1]['embed']
        
        # 验证使用的是SongInfo内置的requester（优先级更高）
        embed_dict = embed.to_dict()
        requester_field = None
        for field in embed_dict.get('fields', []):
            if field['name'] == '点歌人':
                requester_field = field
                break
        
        self.assertIsNotNone(requester_field, "未找到点歌人字段")
        self.assertEqual(requester_field['value'], "<@12345>", f"应该使用SongInfo内置的requester: {requester_field['value']}")
    
    async def test_fallback_to_unknown_user(self):
        """测试回退到未知用户的情况"""
        await self.playback_event.song_added_notification(
            bot=self.mock_bot,
            guild_id=self.guild_id,
            channel_id=self.channel_id,
            song=self.test_audio_info,  # AudioInfo没有requester属性
            position=1,
            source_type="点歌"
            # 没有传递requester参数
        )
        
        # 验证消息被发送
        self.mock_channel.send.assert_called_once()
        
        # 获取发送的嵌入消息
        call_args = self.mock_channel.send.call_args
        embed = call_args[1]['embed']
        
        # 验证回退到未知用户
        embed_dict = embed.to_dict()
        requester_field = None
        for field in embed_dict.get('fields', []):
            if field['name'] == '点歌人':
                requester_field = field
                break
        
        self.assertIsNotNone(requester_field, "未找到点歌人字段")
        self.assertEqual(requester_field['value'], "未知用户", f"应该显示未知用户: {requester_field['value']}")
    
    async def test_card_draw_notification_with_requester(self):
        """测试抽卡通知包含正确的请求者信息"""
        await self.playback_event.song_added_notification(
            bot=self.mock_bot,
            guild_id=self.guild_id,
            channel_id=self.channel_id,
            song=self.test_audio_info,
            position=2,
            source_type="抽卡",
            requester=self.test_user
        )
        
        # 验证消息被发送
        self.mock_channel.send.assert_called_once()
        
        # 获取发送的嵌入消息
        call_args = self.mock_channel.send.call_args
        embed = call_args[1]['embed']
        
        # 验证是抽卡通知
        self.assertEqual(embed.title, "🎲 抽卡歌曲已添加到队列")
        
        # 验证请求者信息正确显示
        embed_dict = embed.to_dict()
        requester_field = None
        for field in embed_dict.get('fields', []):
            if field['name'] == '点歌人':
                requester_field = field
                break
        
        self.assertIsNotNone(requester_field, "未找到点歌人字段")
        self.assertEqual(requester_field['value'], "<@12345>", f"请求者信息错误: {requester_field['value']}")


class TestPlaybackEngineRequesterPassing(unittest.TestCase):
    """播放引擎请求者传递测试类"""
    
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
        self.test_user = MockMember(12345, "测试用户")
        self.test_audio_info = AudioInfo(
            title="测试歌曲",
            duration=180,
            url="https://youtube.com/watch?v=test",
            uploader="测试艺术家"
        )
    
    async def test_trigger_notification_with_requester(self):
        """测试触发通知时传递请求者信息"""
        await self.playback_engine._trigger_song_added_notification(
            self.guild_id, self.test_audio_info, 1, "点歌", self.test_user
        )
        
        # 验证事件处理器被调用
        self.mock_handler.assert_called_once()
        
        # 验证调用参数包含requester
        call_kwargs = self.mock_handler.call_args[1]
        self.assertEqual(call_kwargs['guild_id'], self.guild_id)
        self.assertEqual(call_kwargs['channel_id'], self.channel_id)
        self.assertEqual(call_kwargs['song'], self.test_audio_info)
        self.assertEqual(call_kwargs['position'], 1)
        self.assertEqual(call_kwargs['source_type'], "点歌")
        self.assertEqual(call_kwargs['requester'], self.test_user)
    
    async def test_trigger_notification_without_requester(self):
        """测试触发通知时不传递请求者信息（向后兼容）"""
        await self.playback_engine._trigger_song_added_notification(
            self.guild_id, self.test_audio_info, 1, "点歌"
        )
        
        # 验证事件处理器被调用
        self.mock_handler.assert_called_once()
        
        # 验证调用参数包含None的requester
        call_kwargs = self.mock_handler.call_args[1]
        self.assertIsNone(call_kwargs['requester'])


class TestCardDrawRequesterIntegration(unittest.TestCase):
    """抽卡请求者集成测试类"""
    
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
    
    async def test_card_draw_passes_requester(self):
        """测试抽卡命令传递请求者信息"""
        await self.card_draw_commands._trigger_public_notification(
            self.test_interaction, self.test_audio_info, 1, "抽卡"
        )
        
        # 验证播放引擎的通知方法被调用，并且包含请求者信息
        self.mock_playback_engine._trigger_song_added_notification.assert_called_once_with(
            self.test_interaction.guild.id, 
            self.test_audio_info, 
            1, 
            "抽卡", 
            self.test_interaction.user  # 验证传递了请求者
        )


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
    test_classes = [TestRequesterFix, TestPlaybackEngineRequesterPassing, TestCardDrawRequesterIntegration]
    
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
