"""
改进功能集成测试

测试公共通知和用户去重功能的集成：
- 验证两个功能可以正常协作
- 测试完整的歌曲添加流程
- 确保向后兼容性
"""

import unittest
import asyncio
import tempfile
import shutil
from unittest.mock import Mock, AsyncMock, patch

from similubot.app_commands.card_draw.database import SongHistoryDatabase
from similubot.playback.playback_event import PlaybackEvent
from similubot.core.interfaces import AudioInfo


class MockMember:
    """模拟Discord成员对象"""
    
    def __init__(self, user_id: int, display_name: str):
        self.id = user_id
        self.display_name = display_name
        self.mention = f"<@{user_id}>"


class MockBot:
    """模拟Discord机器人"""
    
    def __init__(self):
        self.get_channel = Mock()


class MockChannel:
    """模拟Discord频道"""
    
    def __init__(self):
        self.send = AsyncMock()


class TestImprovementsIntegration(unittest.TestCase):
    """改进功能集成测试类"""
    
    def setUp(self):
        """测试前准备"""
        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp()
        self.database = SongHistoryDatabase(self.temp_dir)
        
        # 创建播放事件处理器
        self.mock_bot = MockBot()
        self.mock_channel = MockChannel()
        self.mock_bot.get_channel.return_value = self.mock_channel
        self.playback_event = PlaybackEvent()
        
        # 创建测试数据
        self.test_audio_info = AudioInfo(
            title="测试歌曲",
            duration=180,
            url="https://youtube.com/watch?v=test123",
            uploader="测试艺术家",
            thumbnail_url="https://example.com/thumb.jpg",
            file_format="mp4"
        )
        
        self.user1 = MockMember(111, "用户1")
        self.user2 = MockMember(222, "用户2")
        self.guild_id = 67890
        self.channel_id = 11111
    
    def tearDown(self):
        """测试后清理"""
        # 删除临时目录
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    async def test_complete_song_addition_workflow(self):
        """测试完整的歌曲添加工作流程"""
        # 1. 初始化数据库
        await self.database.initialize()
        
        # 2. 第一次添加歌曲（新记录）
        success = await self.database.add_song_record(
            self.test_audio_info, self.user1, self.guild_id, "YouTube"
        )
        self.assertTrue(success)
        
        # 3. 发送公共通知
        await self.playback_event.song_added_notification(
            bot=self.mock_bot,
            guild_id=self.guild_id,
            channel_id=self.channel_id,
            song=self.test_audio_info,
            position=1,
            source_type="点歌"
        )
        
        # 验证通知被发送
        self.mock_channel.send.assert_called_once()
        
        # 4. 验证数据库状态
        total_count = await self.database.get_total_song_count(self.guild_id)
        self.assertEqual(total_count, 1)
        
        # 5. 同一用户再次添加相同歌曲（应该去重）
        self.mock_channel.send.reset_mock()  # 重置mock
        
        success2 = await self.database.add_song_record(
            self.test_audio_info, self.user1, self.guild_id, "YouTube"
        )
        self.assertTrue(success2)
        
        # 6. 再次发送公共通知
        await self.playback_event.song_added_notification(
            bot=self.mock_bot,
            guild_id=self.guild_id,
            channel_id=self.channel_id,
            song=self.test_audio_info,
            position=1,
            source_type="点歌"
        )
        
        # 验证通知被发送
        self.mock_channel.send.assert_called_once()
        
        # 7. 验证去重生效（总数仍为1）
        total_count_after = await self.database.get_total_song_count(self.guild_id)
        self.assertEqual(total_count_after, 1)
    
    async def test_different_users_same_song_with_notifications(self):
        """测试不同用户添加相同歌曲时的通知和数据库行为"""
        # 初始化数据库
        await self.database.initialize()
        
        # 用户1添加歌曲
        await self.database.add_song_record(
            self.test_audio_info, self.user1, self.guild_id, "YouTube"
        )
        
        # 发送用户1的通知
        await self.playback_event.song_added_notification(
            bot=self.mock_bot,
            guild_id=self.guild_id,
            channel_id=self.channel_id,
            song=self.test_audio_info,
            position=1,
            source_type="点歌"
        )
        
        # 用户2添加相同歌曲
        await self.database.add_song_record(
            self.test_audio_info, self.user2, self.guild_id, "YouTube"
        )
        
        # 发送用户2的通知
        await self.playback_event.song_added_notification(
            bot=self.mock_bot,
            guild_id=self.guild_id,
            channel_id=self.channel_id,
            song=self.test_audio_info,
            position=2,
            source_type="点歌"
        )
        
        # 验证两次通知都被发送
        self.assertEqual(self.mock_channel.send.call_count, 2)
        
        # 验证数据库中有两条记录（不同用户不去重）
        total_count = await self.database.get_total_song_count(self.guild_id)
        self.assertEqual(total_count, 2)
        
        user1_count = await self.database.get_user_song_count(self.guild_id, self.user1.id)
        user2_count = await self.database.get_user_song_count(self.guild_id, self.user2.id)
        
        self.assertEqual(user1_count, 1)
        self.assertEqual(user2_count, 1)
    
    async def test_card_draw_notification_with_deduplication(self):
        """测试抽卡通知与去重功能的集成"""
        # 初始化数据库
        await self.database.initialize()
        
        # 先通过正常点歌添加歌曲
        await self.database.add_song_record(
            self.test_audio_info, self.user1, self.guild_id, "YouTube"
        )
        
        # 发送正常点歌通知
        await self.playback_event.song_added_notification(
            bot=self.mock_bot,
            guild_id=self.guild_id,
            channel_id=self.channel_id,
            song=self.test_audio_info,
            position=1,
            source_type="点歌"
        )
        
        # 重置mock
        self.mock_channel.send.reset_mock()
        
        # 同一用户通过抽卡再次添加相同歌曲（应该去重）
        await self.database.add_song_record(
            self.test_audio_info, self.user1, self.guild_id, "YouTube"
        )
        
        # 发送抽卡通知
        await self.playback_event.song_added_notification(
            bot=self.mock_bot,
            guild_id=self.guild_id,
            channel_id=self.channel_id,
            song=self.test_audio_info,
            position=1,
            source_type="抽卡"
        )
        
        # 验证抽卡通知被发送
        self.mock_channel.send.assert_called_once()
        
        # 获取发送的嵌入消息
        call_args = self.mock_channel.send.call_args
        embed = call_args[1]['embed']
        
        # 验证是抽卡通知
        self.assertEqual(embed.title, "🎲 抽卡歌曲已添加到队列")
        
        # 验证去重生效（总数仍为1）
        total_count = await self.database.get_total_song_count(self.guild_id)
        self.assertEqual(total_count, 1)
    
    async def test_notification_error_handling_with_database_operations(self):
        """测试通知错误处理与数据库操作的独立性"""
        # 初始化数据库
        await self.database.initialize()
        
        # 设置通知发送失败
        self.mock_channel.send.side_effect = Exception("通知发送失败")
        
        # 添加歌曲记录（应该成功，不受通知失败影响）
        success = await self.database.add_song_record(
            self.test_audio_info, self.user1, self.guild_id, "YouTube"
        )
        self.assertTrue(success)
        
        # 尝试发送通知（应该不抛出异常）
        await self.playback_event.song_added_notification(
            bot=self.mock_bot,
            guild_id=self.guild_id,
            channel_id=self.channel_id,
            song=self.test_audio_info,
            position=1,
            source_type="点歌"
        )
        
        # 验证数据库操作成功
        total_count = await self.database.get_total_song_count(self.guild_id)
        self.assertEqual(total_count, 1)
        
        # 验证尝试发送了通知
        self.mock_channel.send.assert_called_once()
    
    async def test_backward_compatibility(self):
        """测试向后兼容性"""
        # 初始化数据库
        await self.database.initialize()
        
        # 测试数据库的基本功能仍然正常工作
        success = await self.database.add_song_record(
            self.test_audio_info, self.user1, self.guild_id, "YouTube"
        )
        self.assertTrue(success)
        
        # 测试查询功能
        songs = await self.database.get_random_songs(self.guild_id)
        self.assertEqual(len(songs), 1)
        self.assertEqual(songs[0].title, "测试歌曲")
        
        # 测试统计功能
        total_count = await self.database.get_total_song_count(self.guild_id)
        user_count = await self.database.get_user_song_count(self.guild_id, self.user1.id)
        
        self.assertEqual(total_count, 1)
        self.assertEqual(user_count, 1)
        
        # 测试通知功能不影响现有流程
        await self.playback_event.song_added_notification(
            bot=self.mock_bot,
            guild_id=self.guild_id,
            channel_id=self.channel_id,
            song=self.test_audio_info,
            position=1,
            source_type="点歌"
        )
        
        # 验证通知发送成功
        self.mock_channel.send.assert_called_once()


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
    async_methods = [name for name in dir(TestImprovementsIntegration) 
                    if name.startswith('test_') and asyncio.iscoroutinefunction(getattr(TestImprovementsIntegration, name))]
    
    for method_name in async_methods:
        async_method = getattr(TestImprovementsIntegration, method_name)
        
        def make_sync_wrapper(async_func):
            def sync_wrapper(self):
                return run_async_test(async_func(self))
            return sync_wrapper
        
        setattr(TestImprovementsIntegration, method_name, make_sync_wrapper(async_method))


# 应用异步测试包装器
make_async_test_methods()


if __name__ == '__main__':
    unittest.main()
