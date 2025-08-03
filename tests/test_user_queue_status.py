"""
用户队列状态服务测试

测试用户队列状态查询功能，包括：
1. 队列位置计算准确性
2. 时间估算功能
3. 各种边界情况处理
4. 用户队列信息格式化
"""

import unittest
from unittest.mock import Mock, AsyncMock, MagicMock
import discord
from datetime import datetime

from similubot.queue.user_queue_status import UserQueueStatusService, UserQueueInfo
from similubot.core.interfaces import AudioInfo, SongInfo
from similubot.queue.song import Song


class TestUserQueueStatusService(unittest.TestCase):
    """用户队列状态服务测试类"""
    
    def setUp(self):
        """设置测试环境"""
        # 创建模拟的播放引擎
        self.mock_playback_engine = Mock()
        self.mock_queue_manager = Mock()
        self.mock_playback_engine.get_queue_manager.return_value = self.mock_queue_manager
        
        # 创建服务实例
        self.service = UserQueueStatusService(self.mock_playback_engine)
        
        # 创建测试用户
        self.user1 = Mock(spec=discord.Member)
        self.user1.id = 12345
        self.user1.display_name = "TestUser1"
        
        self.user2 = Mock(spec=discord.Member)
        self.user2.id = 67890
        self.user2.display_name = "TestUser2"
        
        # 创建测试歌曲
        self.audio_info1 = AudioInfo(
            title="Test Song 1",
            duration=180,  # 3分钟
            url="https://example.com/song1",
            uploader="Test Uploader"
        )
        
        self.audio_info2 = AudioInfo(
            title="Test Song 2", 
            duration=240,  # 4分钟
            url="https://example.com/song2",
            uploader="Test Uploader"
        )
        
        self.audio_info3 = AudioInfo(
            title="Test Song 3",
            duration=300,  # 5分钟
            url="https://example.com/song3", 
            uploader="Test Uploader"
        )
        
        self.song1 = Song(audio_info=self.audio_info1, requester=self.user1)
        self.song2 = Song(audio_info=self.audio_info2, requester=self.user2)
        self.song3 = Song(audio_info=self.audio_info3, requester=self.user1)
        
        self.guild_id = 98765
    
    def test_user_queue_info_format_estimated_time(self):
        """测试预计时间格式化功能"""
        print("\n🧪 测试预计时间格式化功能")
        
        # 测试不同时间长度的格式化
        test_cases = [
            (30, "30秒"),
            (60, "1分钟"),
            (90, "1分30秒"),
            (3600, "1小时"),
            (3660, "1小时1分钟"),
            (7200, "2小时"),
            (7320, "2小时2分钟"),
            (None, "未知")
        ]
        
        for seconds, expected in test_cases:
            user_info = UserQueueInfo(
                user_id=12345,
                user_name="TestUser",
                has_queued_song=True,
                estimated_play_time_seconds=seconds
            )
            result = user_info.format_estimated_time()
            self.assertEqual(result, expected)
            print(f"   ✅ {seconds}秒 -> '{result}'")
    
    def test_get_user_queue_info_no_song(self):
        """测试用户没有歌曲在队列中的情况"""
        print("\n🧪 测试用户没有歌曲在队列中的情况")
        
        # 设置模拟：没有当前播放歌曲，队列为空
        self.mock_queue_manager.get_current_song.return_value = None
        self.mock_queue_manager.get_queue_songs.return_value = []
        
        # 获取用户队列信息
        user_info = self.service.get_user_queue_info(self.user1, self.guild_id)
        
        # 验证结果
        self.assertFalse(user_info.has_queued_song)
        self.assertEqual(user_info.user_id, self.user1.id)
        self.assertEqual(user_info.user_name, self.user1.display_name)
        self.assertIsNone(user_info.queued_song_title)
        self.assertIsNone(user_info.queue_position)
        self.assertIsNone(user_info.estimated_play_time_seconds)
        self.assertFalse(user_info.is_currently_playing)
        
        print("   ✅ 用户没有歌曲时返回正确状态")
    
    def test_get_user_queue_info_currently_playing(self):
        """测试用户歌曲正在播放的情况"""
        print("\n🧪 测试用户歌曲正在播放的情况")
        
        # 设置模拟：用户歌曲正在播放
        self.mock_queue_manager.get_current_song.return_value = self.song1
        
        # 获取用户队列信息
        user_info = self.service.get_user_queue_info(self.user1, self.guild_id)
        
        # 验证结果
        self.assertTrue(user_info.has_queued_song)
        self.assertTrue(user_info.is_currently_playing)
        self.assertEqual(user_info.queued_song_title, "Test Song 1")
        self.assertEqual(user_info.queue_position, 0)  # 正在播放，位置为0
        self.assertEqual(user_info.estimated_play_time_seconds, 0)  # 正在播放，无需等待
        
        print("   ✅ 用户歌曲正在播放时返回正确状态")
    
    def test_get_user_queue_info_in_queue(self):
        """测试用户歌曲在队列中等待的情况"""
        print("\n🧪 测试用户歌曲在队列中等待的情况")
        
        # 设置模拟：有其他歌曲正在播放，用户歌曲在队列第2位
        current_song = self.song2  # 其他用户的歌曲正在播放
        self.mock_queue_manager.get_current_song.return_value = current_song
        self.mock_queue_manager.get_queue_songs.return_value = [self.song1, self.song3]  # 用户歌曲在第1位
        
        # 设置播放位置模拟（当前歌曲播放了60秒）
        self.mock_playback_engine.get_current_playback_position.return_value = 60.0
        
        # 获取用户队列信息
        user_info = self.service.get_user_queue_info(self.user1, self.guild_id)
        
        # 验证结果
        self.assertTrue(user_info.has_queued_song)
        self.assertFalse(user_info.is_currently_playing)
        self.assertEqual(user_info.queued_song_title, "Test Song 1")
        self.assertEqual(user_info.queue_position, 1)  # 队列第1位
        
        # 验证时间计算：当前歌曲剩余时间(240-60=180秒) = 180秒
        expected_time = 180  # 当前歌曲剩余时间
        self.assertEqual(user_info.estimated_play_time_seconds, expected_time)
        
        print(f"   ✅ 用户歌曲在队列中时返回正确状态，预计等待时间: {expected_time}秒")
    
    def test_calculate_estimated_play_time_complex(self):
        """测试复杂场景下的时间估算"""
        print("\n🧪 测试复杂场景下的时间估算")
        
        # 设置模拟：当前播放歌曲 + 队列中有多首歌曲
        current_song = Song(
            audio_info=AudioInfo(title="Current Song", duration=300, url="test", uploader="test"),
            requester=self.user2
        )
        self.mock_queue_manager.get_current_song.return_value = current_song
        
        # 队列：[song1(180s), song2(240s), user1_song(300s)]，用户歌曲在第3位
        queue_songs = [self.song1, self.song2, self.song3]
        # 模拟 get_queue_songs 方法，根据 limit 参数返回相应数量的歌曲
        def mock_get_queue_songs(start=0, limit=1000):
            return queue_songs[start:start+limit]
        self.mock_queue_manager.get_queue_songs.side_effect = mock_get_queue_songs
        
        # 当前歌曲播放了120秒
        self.mock_playback_engine.get_current_playback_position.return_value = 120.0
        
        # 计算第3位歌曲的预计播放时间
        estimated_time = self.service._calculate_estimated_play_time(3, self.mock_queue_manager, self.guild_id)
        
        # 预期时间 = 当前歌曲剩余时间(300-120=180) + song1(180) + song2(240) = 600秒
        expected_time = 180 + 180 + 240
        self.assertEqual(estimated_time, expected_time)
        
        print(f"   ✅ 复杂场景时间计算正确: {estimated_time}秒 (预期: {expected_time}秒)")
    
    def test_format_queue_status_message(self):
        """测试队列状态消息格式化"""
        print("\n🧪 测试队列状态消息格式化")
        
        # 测试没有歌曲的情况
        user_info_no_song = UserQueueInfo(
            user_id=12345,
            user_name="TestUser",
            has_queued_song=False
        )
        message = self.service.format_queue_status_message(user_info_no_song)
        self.assertIn("没有歌曲在队列中", message)
        print("   ✅ 无歌曲状态消息格式正确")
        
        # 测试正在播放的情况
        user_info_playing = UserQueueInfo(
            user_id=12345,
            user_name="TestUser",
            has_queued_song=True,
            queued_song_title="Test Song",
            is_currently_playing=True
        )
        message = self.service.format_queue_status_message(user_info_playing)
        self.assertIn("正在播放中", message)
        self.assertIn("Test Song", message)
        print("   ✅ 正在播放状态消息格式正确")
        
        # 测试排队等待的情况
        user_info_queued = UserQueueInfo(
            user_id=12345,
            user_name="TestUser",
            has_queued_song=True,
            queued_song_title="Test Song",
            queue_position=2,
            estimated_play_time_seconds=300,
            is_currently_playing=False
        )
        message = self.service.format_queue_status_message(user_info_queued)
        self.assertIn("第2位", message)
        self.assertIn("5分钟", message)
        self.assertIn("Test Song", message)
        print("   ✅ 排队等待状态消息格式正确")
    
    def test_error_handling(self):
        """测试错误处理"""
        print("\n🧪 测试错误处理")
        
        # 模拟获取队列管理器时出错
        self.mock_playback_engine.get_queue_manager.side_effect = Exception("Test error")
        
        # 获取用户队列信息
        user_info = self.service.get_user_queue_info(self.user1, self.guild_id)
        
        # 应该返回默认状态而不是崩溃
        self.assertFalse(user_info.has_queued_song)
        self.assertEqual(user_info.user_id, self.user1.id)
        
        print("   ✅ 错误情况下返回默认状态，不会崩溃")


    def test_edge_cases(self):
        """测试边界情况"""
        print("\n🧪 测试边界情况")

        # 测试队列位置为0的情况
        self.mock_queue_manager.get_current_song.return_value = None
        self.mock_queue_manager.get_queue_songs.return_value = []

        estimated_time = self.service._calculate_estimated_play_time(0, self.mock_queue_manager, self.guild_id)
        self.assertEqual(estimated_time, 0)
        print("   ✅ 队列位置为0时返回0等待时间")

        # 测试无法获取当前播放位置的情况
        self.mock_queue_manager.get_current_song.return_value = self.song1
        self.mock_playback_engine.get_current_playback_position.return_value = None

        estimated_time = self.service._calculate_estimated_play_time(1, self.mock_queue_manager, self.guild_id)
        # 应该使用完整歌曲时长
        self.assertEqual(estimated_time, self.song1.duration)
        print("   ✅ 无法获取播放位置时使用完整歌曲时长")

        # 测试播放位置超过歌曲时长的情况
        self.mock_playback_engine.get_current_playback_position.return_value = 500.0  # 超过180秒

        estimated_time = self.service._calculate_estimated_play_time(1, self.mock_queue_manager, self.guild_id)
        # 剩余时间应该为0（不会是负数）
        self.assertEqual(estimated_time, 0)
        print("   ✅ 播放位置超过歌曲时长时正确处理")


if __name__ == '__main__':
    print("🚀 开始用户队列状态服务测试")
    unittest.main(verbosity=2)
