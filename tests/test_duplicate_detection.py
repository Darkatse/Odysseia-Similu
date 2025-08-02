"""
重复检测系统的综合测试

测试重复检测器的所有功能，包括歌曲识别、用户跟踪、队列集成等。
"""

import unittest
import asyncio
import sys
import os
from unittest.mock import MagicMock, AsyncMock, patch

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from similubot.queue.duplicate_detector import DuplicateDetector, SongIdentifier
from similubot.queue.queue_manager import QueueManager, DuplicateSongError
from similubot.core.interfaces import AudioInfo
import discord


class TestSongIdentifier(unittest.TestCase):
    """测试歌曲标识符功能"""
    
    def test_song_identifier_equality(self):
        """测试歌曲标识符相等性"""
        id1 = SongIdentifier("test song", 180, "abc123")
        id2 = SongIdentifier("test song", 180, "abc123")
        id3 = SongIdentifier("different song", 180, "abc123")
        
        self.assertEqual(id1, id2)
        self.assertNotEqual(id1, id3)
    
    def test_song_identifier_hash(self):
        """测试歌曲标识符哈希功能"""
        id1 = SongIdentifier("test song", 180, "abc123")
        id2 = SongIdentifier("test song", 180, "abc123")
        
        # 相同的标识符应该有相同的哈希值
        self.assertEqual(hash(id1), hash(id2))
        
        # 可以用作字典键和集合元素
        test_set = {id1, id2}
        self.assertEqual(len(test_set), 1)


class TestDuplicateDetector(unittest.TestCase):
    """测试重复检测器功能"""
    
    def setUp(self):
        """设置测试环境"""
        self.detector = DuplicateDetector(guild_id=12345)
        
        # 创建测试用的音频信息
        self.audio_info1 = AudioInfo(
            title="Test Song",
            duration=180,
            url="https://www.youtube.com/watch?v=test123",
            uploader="Test Channel"
        )
        
        self.audio_info2 = AudioInfo(
            title="Another Song",
            duration=240,
            url="https://www.youtube.com/watch?v=test456",
            uploader="Another Channel"
        )
        
        # 创建模拟用户
        self.user1 = MagicMock(spec=discord.Member)
        self.user1.id = 1001
        self.user1.display_name = "User1"
        
        self.user2 = MagicMock(spec=discord.Member)
        self.user2.id = 1002
        self.user2.display_name = "User2"
    
    def test_normalize_title(self):
        """测试标题标准化"""
        test_cases = [
            ("Test Song", "test song"),
            ("Test Song (Official Video)", "test song"),
            ("Test Song [Official Audio]", "test song"),
            ("Test Song (Lyrics)", "test song"),
            ("Test Song - Official Video", "test song"),
            ("Test Song | Official Audio", "test song"),
            ("Test Song (HD)", "test song"),
            ("Test Song [4K]", "test song"),
            ("Test Song (Remastered)", "test song"),
            ("Test!@#$%^&*()Song", "test song"),
            ("   Test   Song   ", "test song"),
            ("", ""),
        ]
        
        for input_title, expected in test_cases:
            with self.subTest(input_title=input_title):
                result = self.detector._normalize_title(input_title)
                self.assertEqual(result, expected)
    
    def test_extract_url_key_youtube(self):
        """测试YouTube URL关键字提取"""
        test_cases = [
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dqw4w9wgxcq"),
            ("https://youtu.be/dQw4w9WgXcQ", "dqw4w9wgxcq"),
            ("http://youtube.com/watch?v=test123", "test123"),
            ("www.youtube.com/watch?v=abc456", "abc456"),
        ]

        for url, expected in test_cases:
            with self.subTest(url=url):
                result = self.detector._extract_url_key(url)
                self.assertEqual(result, expected)
    
    def test_extract_url_key_catbox(self):
        """测试Catbox URL关键字提取"""
        test_cases = [
            ("https://files.catbox.moe/abc123.mp3", "abc123.mp3"),
            ("https://catbox.moe/c/def456.wav", "def456.wav"),
        ]
        
        for url, expected in test_cases:
            with self.subTest(url=url):
                result = self.detector._extract_url_key(url)
                self.assertEqual(result, expected)
    
    def test_extract_url_key_other(self):
        """测试其他URL关键字提取"""
        url = "https://example.com/audio.mp3"
        result = self.detector._extract_url_key(url)
        self.assertEqual(result, url.lower())
    
    def test_is_duplicate_for_user_empty(self):
        """测试空检测器的重复检查"""
        result = self.detector.is_duplicate_for_user(self.audio_info1, self.user1)
        self.assertFalse(result)
    
    def test_add_and_check_duplicate(self):
        """测试添加歌曲和重复检查"""
        # 添加歌曲
        self.detector.add_song_for_user(self.audio_info1, self.user1)
        
        # 检查重复
        result = self.detector.is_duplicate_for_user(self.audio_info1, self.user1)
        self.assertTrue(result)
        
        # 不同用户不应该被检测为重复
        result = self.detector.is_duplicate_for_user(self.audio_info1, self.user2)
        self.assertFalse(result)
        
        # 不同歌曲不应该被检测为重复
        result = self.detector.is_duplicate_for_user(self.audio_info2, self.user1)
        self.assertFalse(result)
    
    def test_remove_song_for_user(self):
        """测试移除用户歌曲"""
        # 添加歌曲
        self.detector.add_song_for_user(self.audio_info1, self.user1)
        self.assertTrue(self.detector.is_duplicate_for_user(self.audio_info1, self.user1))
        
        # 移除歌曲
        self.detector.remove_song_for_user(self.audio_info1, self.user1)
        self.assertFalse(self.detector.is_duplicate_for_user(self.audio_info1, self.user1))
    
    def test_clear_user_songs(self):
        """测试清空用户歌曲"""
        # 添加多首歌曲
        self.detector.add_song_for_user(self.audio_info1, self.user1)
        self.detector.add_song_for_user(self.audio_info2, self.user1)
        
        # 清空用户歌曲
        count = self.detector.clear_user_songs(self.user1)
        self.assertEqual(count, 2)
        
        # 检查歌曲已被清空
        self.assertFalse(self.detector.is_duplicate_for_user(self.audio_info1, self.user1))
        self.assertFalse(self.detector.is_duplicate_for_user(self.audio_info2, self.user1))
    
    def test_clear_all(self):
        """测试清空所有数据"""
        # 添加多个用户的歌曲
        self.detector.add_song_for_user(self.audio_info1, self.user1)
        self.detector.add_song_for_user(self.audio_info2, self.user2)
        
        # 清空所有数据
        count = self.detector.clear_all()
        self.assertEqual(count, 2)
        
        # 检查所有数据已被清空
        self.assertFalse(self.detector.is_duplicate_for_user(self.audio_info1, self.user1))
        self.assertFalse(self.detector.is_duplicate_for_user(self.audio_info2, self.user2))
    
    def test_get_user_song_count(self):
        """测试获取用户歌曲数量"""
        # 初始为0
        self.assertEqual(self.detector.get_user_song_count(self.user1), 0)
        
        # 添加歌曲
        self.detector.add_song_for_user(self.audio_info1, self.user1)
        self.assertEqual(self.detector.get_user_song_count(self.user1), 1)
        
        self.detector.add_song_for_user(self.audio_info2, self.user1)
        self.assertEqual(self.detector.get_user_song_count(self.user1), 2)
    
    def test_get_total_tracked_songs(self):
        """测试获取总跟踪歌曲数量"""
        # 初始为0
        self.assertEqual(self.detector.get_total_tracked_songs(), 0)
        
        # 添加歌曲
        self.detector.add_song_for_user(self.audio_info1, self.user1)
        self.assertEqual(self.detector.get_total_tracked_songs(), 1)
        
        # 同一首歌被不同用户添加，总数不变
        self.detector.add_song_for_user(self.audio_info1, self.user2)
        self.assertEqual(self.detector.get_total_tracked_songs(), 1)
        
        # 添加不同歌曲
        self.detector.add_song_for_user(self.audio_info2, self.user1)
        self.assertEqual(self.detector.get_total_tracked_songs(), 2)
    
    def test_get_duplicate_info(self):
        """测试获取重复信息"""
        # 未跟踪的歌曲
        result = self.detector.get_duplicate_info(self.audio_info1)
        self.assertIsNone(result)
        
        # 添加歌曲
        self.detector.add_song_for_user(self.audio_info1, self.user1)
        self.detector.add_song_for_user(self.audio_info1, self.user2)
        
        # 获取重复信息
        result = self.detector.get_duplicate_info(self.audio_info1)
        self.assertIsNotNone(result)
        
        song_id, user_ids = result
        self.assertIsInstance(song_id, SongIdentifier)
        self.assertEqual(user_ids, {self.user1.id, self.user2.id})
    
    def test_title_variations(self):
        """测试标题变化的处理"""
        # 创建标题略有不同的音频信息
        audio_original = AudioInfo(
            title="Test Song",
            duration=180,
            url="https://www.youtube.com/watch?v=test123",
            uploader="Test Channel"
        )
        
        audio_with_suffix = AudioInfo(
            title="Test Song (Official Video)",
            duration=180,
            url="https://www.youtube.com/watch?v=test123",
            uploader="Test Channel"
        )
        
        # 添加原始歌曲
        self.detector.add_song_for_user(audio_original, self.user1)
        
        # 带后缀的版本应该被识别为重复
        result = self.detector.is_duplicate_for_user(audio_with_suffix, self.user1)
        self.assertTrue(result)


class TestQueueManagerDuplicateIntegration(unittest.TestCase):
    """测试队列管理器的重复检测集成"""
    
    def setUp(self):
        """设置测试环境"""
        self.queue_manager = QueueManager(guild_id=12345)
        
        # 创建测试音频信息
        self.audio_info = AudioInfo(
            title="Test Song",
            duration=180,
            url="https://www.youtube.com/watch?v=test123",
            uploader="Test Channel"
        )
        
        # 创建模拟用户
        self.user = MagicMock(spec=discord.Member)
        self.user.id = 1001
        self.user.display_name = "TestUser"
    
    async def test_add_song_success(self):
        """测试成功添加歌曲"""
        position = await self.queue_manager.add_song(self.audio_info, self.user)
        self.assertEqual(position, 1)
    
    async def test_add_duplicate_song_raises_error(self):
        """测试添加重复歌曲抛出异常"""
        # 首次添加成功
        await self.queue_manager.add_song(self.audio_info, self.user)
        
        # 再次添加应该抛出异常
        with self.assertRaises(DuplicateSongError) as context:
            await self.queue_manager.add_song(self.audio_info, self.user)
        
        self.assertIn("已经请求了这首歌曲", str(context.exception))
    
    async def test_different_users_can_add_same_song(self):
        """测试不同用户可以添加相同歌曲"""
        user2 = MagicMock(spec=discord.Member)
        user2.id = 1002
        user2.display_name = "User2"
        
        # 用户1添加歌曲
        position1 = await self.queue_manager.add_song(self.audio_info, self.user)
        self.assertEqual(position1, 1)
        
        # 用户2添加相同歌曲应该成功
        position2 = await self.queue_manager.add_song(self.audio_info, user2)
        self.assertEqual(position2, 2)
    
    async def test_song_removal_allows_re_adding(self):
        """测试歌曲移除后允许重新添加"""
        # 添加歌曲
        await self.queue_manager.add_song(self.audio_info, self.user)
        
        # 获取下一首歌曲（模拟播放）
        song = await self.queue_manager.get_next_song()
        self.assertIsNotNone(song)
        
        # 现在用户应该可以再次添加相同歌曲
        position = await self.queue_manager.add_song(self.audio_info, self.user)
        self.assertEqual(position, 1)
    
    async def test_clear_queue_removes_duplicates(self):
        """测试清空队列移除重复跟踪"""
        # 添加歌曲
        await self.queue_manager.add_song(self.audio_info, self.user)
        
        # 清空队列
        count = await self.queue_manager.clear_queue()
        self.assertEqual(count, 1)
        
        # 用户应该可以再次添加歌曲
        position = await self.queue_manager.add_song(self.audio_info, self.user)
        self.assertEqual(position, 1)
    
    def test_check_duplicate_for_user(self):
        """测试检查用户重复功能"""
        # 初始不重复
        result = self.queue_manager.check_duplicate_for_user(self.audio_info, self.user)
        self.assertFalse(result)
    
    def test_get_user_song_count(self):
        """测试获取用户歌曲数量"""
        # 初始为0
        count = self.queue_manager.get_user_song_count(self.user)
        self.assertEqual(count, 0)
    
    def test_get_duplicate_detection_stats(self):
        """测试获取重复检测统计"""
        stats = self.queue_manager.get_duplicate_detection_stats()
        self.assertIn('total_tracked_songs', stats)
        self.assertIn('total_users_with_songs', stats)
        self.assertEqual(stats['total_tracked_songs'], 0)
        self.assertEqual(stats['total_users_with_songs'], 0)


if __name__ == '__main__':
    # 运行异步测试
    async def run_async_tests():
        """运行所有异步测试"""
        test_classes = [
            TestSongIdentifier,
            TestDuplicateDetector,
            TestQueueManagerDuplicateIntegration
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
