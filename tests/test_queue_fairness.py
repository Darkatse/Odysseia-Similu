"""
队列公平性系统测试

测试新的队列公平性机制，确保用户不能同时有多首歌曲在队列中等待播放。
"""

import unittest
import asyncio
import sys
import os
from unittest.mock import MagicMock

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from similubot.queue.queue_manager import QueueManager, DuplicateSongError, QueueFairnessError
from similubot.queue.duplicate_detector import DuplicateDetector
from similubot.core.interfaces import AudioInfo
import discord


class TestQueueFairness(unittest.TestCase):
    """测试队列公平性系统"""
    
    def setUp(self):
        """设置测试环境"""
        self.queue_manager = QueueManager(guild_id=12345)
        
        # 创建测试用户
        self.user1 = MagicMock(spec=discord.Member)
        self.user1.id = 1001
        self.user1.display_name = "User1"
        
        self.user2 = MagicMock(spec=discord.Member)
        self.user2.id = 1002
        self.user2.display_name = "User2"
        
        # 创建测试歌曲
        self.song1 = AudioInfo(
            title="Song 1",
            duration=180,
            url="https://www.youtube.com/watch?v=song1",
            uploader="Artist 1"
        )
        
        self.song2 = AudioInfo(
            title="Song 2",
            duration=200,
            url="https://www.youtube.com/watch?v=song2",
            uploader="Artist 2"
        )
        
        self.song3 = AudioInfo(
            title="Song 3",
            duration=220,
            url="https://www.youtube.com/watch?v=song3",
            uploader="Artist 3"
        )
    
    async def test_single_user_one_song_limit(self):
        """测试单用户一首歌曲限制"""
        print("🧪 测试单用户一首歌曲限制")
        
        # 1. 用户添加第一首歌曲（应该成功）
        position1 = await self.queue_manager.add_song(self.song1, self.user1)
        print(f"   ✅ 第一首歌曲添加成功: 位置 {position1}")
        
        # 2. 用户尝试添加第二首不同歌曲（应该被阻止）
        with self.assertRaises(QueueFairnessError) as context:
            await self.queue_manager.add_song(self.song2, self.user1)
        
        error = context.exception
        self.assertIn("已经有", str(error))
        self.assertIn("首歌曲在队列中", str(error))
        print(f"   ✅ 第二首歌曲被阻止: {error}")
        
        # 3. 验证用户状态
        status = self.queue_manager.get_user_queue_status(self.user1)
        self.assertEqual(status['pending_songs'], 1)
        self.assertFalse(status['can_add_song'])
        print(f"   ✅ 用户状态正确: {status['pending_songs']} 首待播放")
    
    async def test_multiple_users_can_add_songs(self):
        """测试多用户可以各自添加歌曲"""
        print("\n🧪 测试多用户可以各自添加歌曲")
        
        # 创建新的队列管理器避免状态污染
        queue_manager = QueueManager(guild_id=12346)
        
        # 1. 用户1添加歌曲
        position1 = await queue_manager.add_song(self.song1, self.user1)
        print(f"   ✅ 用户1添加歌曲: 位置 {position1}")
        
        # 2. 用户2添加歌曲（应该成功）
        position2 = await queue_manager.add_song(self.song2, self.user2)
        print(f"   ✅ 用户2添加歌曲: 位置 {position2}")
        
        # 3. 用户1尝试添加第二首歌曲（应该被阻止）
        with self.assertRaises(QueueFairnessError):
            await queue_manager.add_song(self.song3, self.user1)
        print("   ✅ 用户1第二首歌曲被阻止")
        
        # 4. 用户2尝试添加第二首歌曲（应该被阻止）
        with self.assertRaises(QueueFairnessError):
            await queue_manager.add_song(self.song3, self.user2)
        print("   ✅ 用户2第二首歌曲被阻止")
        
        # 5. 验证队列状态
        queue_info = await queue_manager.get_queue_info()
        self.assertEqual(queue_info['queue_length'], 2)
        print(f"   ✅ 队列长度正确: {queue_info['queue_length']}")
    
    async def test_song_playback_lifecycle(self):
        """测试歌曲播放生命周期"""
        print("\n🧪 测试歌曲播放生命周期")
        
        # 创建新的队列管理器
        queue_manager = QueueManager(guild_id=12347)
        
        # 1. 添加歌曲
        await queue_manager.add_song(self.song1, self.user1)
        print("   ✅ 歌曲添加到队列")
        
        # 2. 验证用户不能添加更多歌曲
        with self.assertRaises(QueueFairnessError):
            await queue_manager.add_song(self.song2, self.user1)
        print("   ✅ 用户不能添加更多歌曲")
        
        # 3. 歌曲开始播放
        song = await queue_manager.get_next_song()
        self.assertIsNotNone(song)
        print(f"   ✅ 歌曲开始播放: {song.title}")
        
        # 4. 播放期间用户仍然不能添加歌曲
        with self.assertRaises(QueueFairnessError) as context:
            await queue_manager.add_song(self.song2, self.user1)
        
        self.assertIn("正在播放中", str(context.exception))
        print("   ✅ 播放期间不能添加歌曲")
        
        # 5. 歌曲播放完成
        queue_manager.notify_song_finished(song)
        print("   ✅ 歌曲播放完成")
        
        # 6. 现在用户可以添加新歌曲
        position = await queue_manager.add_song(self.song2, self.user1)
        print(f"   ✅ 播放完成后可以添加新歌曲: 位置 {position}")
    
    async def test_duplicate_detection_still_works(self):
        """测试重复检测仍然有效"""
        print("\n🧪 测试重复检测仍然有效")
        
        # 创建新的队列管理器
        queue_manager = QueueManager(guild_id=12348)
        
        # 1. 添加歌曲
        await queue_manager.add_song(self.song1, self.user1)
        print("   ✅ 歌曲添加成功")
        
        # 2. 尝试添加相同歌曲（应该被重复检测阻止）
        with self.assertRaises(DuplicateSongError) as context:
            await queue_manager.add_song(self.song1, self.user1)
        
        self.assertIn("已经请求了这首歌曲", str(context.exception))
        print("   ✅ 重复检测仍然有效")
    
    async def test_queue_operations_update_fairness(self):
        """测试队列操作更新公平性状态"""
        print("\n🧪 测试队列操作更新公平性状态")
        
        # 创建新的队列管理器
        queue_manager = QueueManager(guild_id=12349)
        
        # 1. 添加歌曲
        await queue_manager.add_song(self.song1, self.user1)
        print("   ✅ 歌曲添加成功")
        
        # 2. 验证用户不能添加更多歌曲
        with self.assertRaises(QueueFairnessError):
            await queue_manager.add_song(self.song2, self.user1)
        print("   ✅ 用户不能添加更多歌曲")
        
        # 3. 清空队列
        count = await queue_manager.clear_queue()
        print(f"   ✅ 清空队列: {count} 首歌曲")
        
        # 4. 现在用户应该可以添加歌曲
        position = await queue_manager.add_song(self.song2, self.user1)
        print(f"   ✅ 清空后可以添加歌曲: 位置 {position}")
    
    def test_user_queue_status(self):
        """测试用户队列状态查询"""
        print("\n🧪 测试用户队列状态查询")
        
        # 创建检测器
        detector = DuplicateDetector(guild_id=12350)
        
        # 1. 初始状态
        status = detector.get_user_queue_status(self.user1)
        self.assertEqual(status['pending_songs'], 0)
        self.assertTrue(status['can_add_song'])
        self.assertFalse(status['is_currently_playing'])
        print("   ✅ 初始状态正确")
        
        # 2. 添加歌曲后
        detector.add_song_for_user(self.song1, self.user1)
        status = detector.get_user_queue_status(self.user1)
        self.assertEqual(status['pending_songs'], 1)
        self.assertFalse(status['can_add_song'])
        print("   ✅ 添加歌曲后状态正确")
        
        # 3. 歌曲开始播放后
        detector.notify_song_started_playing(self.song1, self.user1)
        status = detector.get_user_queue_status(self.user1)
        self.assertEqual(status['pending_songs'], 0)
        self.assertTrue(status['is_currently_playing'])
        self.assertFalse(status['can_add_song'])
        print("   ✅ 播放中状态正确")
        
        # 4. 歌曲播放完成后
        detector.notify_song_finished_playing(self.song1, self.user1)
        status = detector.get_user_queue_status(self.user1)
        self.assertEqual(status['pending_songs'], 0)
        self.assertFalse(status['is_currently_playing'])
        self.assertTrue(status['can_add_song'])
        print("   ✅ 播放完成后状态正确")
    
    def test_comprehensive_checking(self):
        """测试综合检查功能"""
        print("\n🧪 测试综合检查功能")
        
        # 创建检测器
        detector = DuplicateDetector(guild_id=12351)
        
        # 1. 初始状态可以添加
        can_add, error = detector.can_user_add_song(self.song1, self.user1)
        self.assertTrue(can_add)
        self.assertEqual(error, "")
        print("   ✅ 初始状态可以添加")
        
        # 2. 添加歌曲后不能添加更多
        detector.add_song_for_user(self.song1, self.user1)
        can_add, error = detector.can_user_add_song(self.song2, self.user1)
        self.assertFalse(can_add)
        self.assertIn("已经有", error)
        print(f"   ✅ 有待播放歌曲时被阻止: {error}")
        
        # 3. 重复歌曲检测
        can_add, error = detector.can_user_add_song(self.song1, self.user1)
        self.assertFalse(can_add)
        self.assertIn("已经请求了这首歌曲", error)
        print(f"   ✅ 重复歌曲被阻止: {error}")
        
        # 4. 播放中不能添加
        detector.notify_song_started_playing(self.song1, self.user1)
        can_add, error = detector.can_user_add_song(self.song2, self.user1)
        self.assertFalse(can_add)
        self.assertIn("正在播放中", error)
        print(f"   ✅ 播放中被阻止: {error}")
        
        # 5. 播放完成后可以添加
        detector.notify_song_finished_playing(self.song1, self.user1)
        can_add, error = detector.can_user_add_song(self.song2, self.user1)
        self.assertTrue(can_add)
        self.assertEqual(error, "")
        print("   ✅ 播放完成后可以添加")


async def run_tests():
    """运行所有测试"""
    print("🎵 队列公平性系统测试")
    print("=" * 60)
    
    test_instance = TestQueueFairness()
    
    # 运行异步测试
    async_tests = [
        test_instance.test_single_user_one_song_limit,
        test_instance.test_multiple_users_can_add_songs,
        test_instance.test_song_playback_lifecycle,
        test_instance.test_duplicate_detection_still_works,
        test_instance.test_queue_operations_update_fairness,
    ]
    
    for test_func in async_tests:
        try:
            test_instance.setUp()  # 重新设置测试环境
            await test_func()
        except Exception as e:
            print(f"❌ {test_func.__name__} 失败: {e}")
            return False
    
    # 运行同步测试
    sync_tests = [
        test_instance.test_user_queue_status,
        test_instance.test_comprehensive_checking,
    ]
    
    for test_func in sync_tests:
        try:
            test_instance.setUp()  # 重新设置测试环境
            test_func()
        except Exception as e:
            print(f"❌ {test_func.__name__} 失败: {e}")
            return False
    
    print("\n🎉 所有测试通过！")
    print("=" * 60)
    print("队列公平性系统验证成功：")
    print("✅ 用户同时只能有一首歌曲在队列中")
    print("✅ 多用户可以独立添加歌曲")
    print("✅ 歌曲播放生命周期正确处理")
    print("✅ 重复检测仍然有效")
    print("✅ 队列操作正确更新公平性状态")
    print("✅ 用户状态查询功能完整")
    print("✅ 综合检查功能正常")
    
    return True


if __name__ == "__main__":
    success = asyncio.run(run_tests())
    if not success:
        exit(1)
