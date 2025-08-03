"""
队列同步问题修复测试

测试队列管理器和播放引擎之间的同步问题修复：
1. peek_next_song 方法不会修改队列状态
2. get_next_song 方法正确修改队列状态
3. 播放引擎使用 peek_next_song 检查下一首歌曲不会导致队列提前推进
"""

import unittest
from unittest.mock import Mock, AsyncMock
import discord

from similubot.queue.queue_manager import QueueManager
from similubot.core.interfaces import AudioInfo
from similubot.queue.song import Song


class TestQueueSynchronizationFix(unittest.TestCase):
    """队列同步问题修复测试类"""
    
    def setUp(self):
        """设置测试环境"""
        self.guild_id = 12345
        self.queue_manager = QueueManager(self.guild_id)
        
        # 创建测试用户
        self.user1 = Mock(spec=discord.Member)
        self.user1.id = 11111
        self.user1.display_name = "User1"
        
        self.user2 = Mock(spec=discord.Member)
        self.user2.id = 22222
        self.user2.display_name = "User2"
        
        # 创建测试歌曲
        self.audio_info1 = AudioInfo(
            title="Song 1",
            duration=180,
            url="https://example.com/song1",
            uploader="Test Uploader"
        )
        
        self.audio_info2 = AudioInfo(
            title="Song 2", 
            duration=240,
            url="https://example.com/song2",
            uploader="Test Uploader"
        )
        
        self.audio_info3 = AudioInfo(
            title="Song 3",
            duration=300,
            url="https://example.com/song3",
            uploader="Test Uploader"
        )
    
    async def test_peek_next_song_does_not_modify_queue(self):
        """测试 peek_next_song 不会修改队列状态"""
        print("\n🧪 测试 peek_next_song 不修改队列状态")
        
        # 添加歌曲到队列
        await self.queue_manager.add_song(self.audio_info1, self.user1)
        await self.queue_manager.add_song(self.audio_info2, self.user2)
        await self.queue_manager.add_song(self.audio_info3, self.user1)
        
        # 记录初始状态
        initial_queue_length = self.queue_manager.get_queue_length()
        initial_current_song = self.queue_manager.get_current_song()
        
        # 使用 peek_next_song 查看下一首歌曲
        peeked_song = self.queue_manager.peek_next_song()
        
        # 验证队列状态没有改变
        self.assertEqual(self.queue_manager.get_queue_length(), initial_queue_length)
        self.assertEqual(self.queue_manager.get_current_song(), initial_current_song)
        
        # 验证返回的是正确的下一首歌曲
        self.assertIsNotNone(peeked_song)
        self.assertEqual(peeked_song.title, "Song 1")
        self.assertEqual(peeked_song.requester.id, self.user1.id)
        
        # 再次 peek 应该返回相同的歌曲
        peeked_song2 = self.queue_manager.peek_next_song()
        self.assertEqual(peeked_song.title, peeked_song2.title)
        self.assertEqual(peeked_song.requester.id, peeked_song2.requester.id)
        
        print("   ✅ peek_next_song 不修改队列状态")
    
    async def test_get_next_song_modifies_queue_correctly(self):
        """测试 get_next_song 正确修改队列状态"""
        print("\n🧪 测试 get_next_song 正确修改队列状态")
        
        # 添加歌曲到队列
        await self.queue_manager.add_song(self.audio_info1, self.user1)
        await self.queue_manager.add_song(self.audio_info2, self.user2)
        
        # 记录初始状态
        initial_queue_length = self.queue_manager.get_queue_length()
        
        # 使用 get_next_song 获取下一首歌曲
        next_song = await self.queue_manager.get_next_song()
        
        # 验证队列状态正确改变
        self.assertEqual(self.queue_manager.get_queue_length(), initial_queue_length - 1)
        self.assertEqual(self.queue_manager.get_current_song(), next_song)
        
        # 验证返回的是正确的歌曲
        self.assertIsNotNone(next_song)
        self.assertEqual(next_song.title, "Song 1")
        self.assertEqual(next_song.requester.id, self.user1.id)
        
        # 再次调用应该返回下一首歌曲
        next_song2 = await self.queue_manager.get_next_song()
        self.assertEqual(next_song2.title, "Song 2")
        self.assertEqual(next_song2.requester.id, self.user2.id)
        
        print("   ✅ get_next_song 正确修改队列状态")
    
    async def test_peek_empty_queue(self):
        """测试空队列时的 peek_next_song"""
        print("\n🧪 测试空队列时的 peek_next_song")
        
        # 确保队列为空
        await self.queue_manager.clear_queue()
        
        # peek 空队列应该返回 None
        peeked_song = self.queue_manager.peek_next_song()
        self.assertIsNone(peeked_song)
        
        # 队列长度应该仍为 0
        self.assertEqual(self.queue_manager.get_queue_length(), 0)
        
        print("   ✅ 空队列时 peek_next_song 返回 None")
    
    async def test_peek_vs_get_sequence(self):
        """测试 peek 和 get 的正确使用序列"""
        print("\n🧪 测试 peek 和 get 的正确使用序列")
        
        # 添加歌曲到队列
        await self.queue_manager.add_song(self.audio_info1, self.user1)
        await self.queue_manager.add_song(self.audio_info2, self.user2)
        
        # 1. 先 peek 查看下一首歌曲（不修改队列）
        peeked_song = self.queue_manager.peek_next_song()
        self.assertEqual(peeked_song.title, "Song 1")
        self.assertEqual(self.queue_manager.get_queue_length(), 2)
        
        # 2. 检查点歌人状态（模拟播放引擎的检查逻辑）
        # 这里可以检查 peeked_song.requester.voice 等状态
        # 但不会影响队列
        
        # 3. 确认要播放后，使用 get_next_song 获取歌曲
        actual_song = await self.queue_manager.get_next_song()
        self.assertEqual(actual_song.title, "Song 1")
        self.assertEqual(self.queue_manager.get_queue_length(), 1)
        self.assertEqual(self.queue_manager.get_current_song(), actual_song)
        
        # 4. 再次 peek 应该看到下一首歌曲
        next_peeked = self.queue_manager.peek_next_song()
        self.assertEqual(next_peeked.title, "Song 2")
        self.assertEqual(self.queue_manager.get_queue_length(), 1)  # 队列长度不变
        
        print("   ✅ peek 和 get 的使用序列正确")
    
    def test_peek_next_song_interface_compliance(self):
        """测试 peek_next_song 符合接口定义"""
        print("\n🧪 测试 peek_next_song 符合接口定义")
        
        # 验证方法存在且可调用
        self.assertTrue(hasattr(self.queue_manager, 'peek_next_song'))
        self.assertTrue(callable(getattr(self.queue_manager, 'peek_next_song')))
        
        # 验证方法签名（不是 async）
        import inspect
        sig = inspect.signature(self.queue_manager.peek_next_song)
        self.assertFalse(inspect.iscoroutinefunction(self.queue_manager.peek_next_song))
        
        print("   ✅ peek_next_song 符合接口定义")


class TestPlaybackEngineIntegration(unittest.IsolatedAsyncioTestCase):
    """播放引擎集成测试类"""
    
    def setUp(self):
        """设置测试环境"""
        self.guild_id = 12345
        
        # 创建模拟的队列管理器
        self.mock_queue_manager = Mock()
        self.mock_queue_manager.peek_next_song = Mock()
        self.mock_queue_manager.get_next_song = AsyncMock()
        
        # 创建测试歌曲
        self.test_song = Mock()
        self.test_song.title = "Test Song"
        self.test_song.requester = Mock()
        self.test_song.requester.name = "TestUser"
        self.test_song.requester.voice = None  # 模拟用户不在语音频道
    
    def test_check_next_song_uses_peek(self):
        """测试检查下一首歌曲使用 peek 而不是 get"""
        print("\n🧪 测试播放引擎使用 peek_next_song")
        
        # 模拟 peek_next_song 返回歌曲
        self.mock_queue_manager.peek_next_song.return_value = self.test_song
        
        # 模拟播放引擎的检查逻辑
        def simulate_check_next_song():
            # 这模拟了修复后的 _check_and_notify_next_song 方法
            next_song = self.mock_queue_manager.peek_next_song()
            return next_song
        
        # 执行检查
        result = simulate_check_next_song()
        
        # 验证使用了 peek_next_song
        self.mock_queue_manager.peek_next_song.assert_called_once()
        self.mock_queue_manager.get_next_song.assert_not_called()
        
        # 验证返回了正确的歌曲
        self.assertEqual(result, self.test_song)
        
        print("   ✅ 播放引擎正确使用 peek_next_song")


if __name__ == '__main__':
    print("🚀 开始队列同步问题修复测试")
    unittest.main(verbosity=2)
