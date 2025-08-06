"""
队列歌曲替换功能测试

测试新的队列歌曲替换功能，包括：
1. 正常替换流程
2. 安全约束检查
3. 边界情况处理
4. 错误处理和日志记录
"""

import unittest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
import discord

from similubot.queue.queue_manager import QueueManager
from similubot.queue.song import Song
from similubot.core.interfaces import AudioInfo


class TestQueueSongReplacement(unittest.IsolatedAsyncioTestCase):
    """队列歌曲替换功能测试类"""
    
    def setUp(self):
        """设置测试环境"""
        # 创建模拟的配置管理器
        self.mock_config_manager = Mock()
        # 设置较长的歌曲时长限制（10分钟）
        def mock_get(key, default=None):
            if key == "music.max_song_duration":
                return 600  # 10分钟
            return True
        self.mock_config_manager.get.side_effect = mock_get
        
        # 创建队列管理器
        self.queue_manager = QueueManager(
            guild_id=12345,
            config_manager=self.mock_config_manager
        )
        
        # 创建模拟用户
        self.mock_user = Mock(spec=discord.Member)
        self.mock_user.id = 67890
        self.mock_user.display_name = "TestUser"
        
        # 创建测试音频信息（使用较短的时长以通过默认限制）
        self.old_audio_info = AudioInfo(
            title="Old Song",
            uploader="Old Artist",
            duration=30,  # 30秒，在默认限制内
            url="http://example.com/old.mp3"
        )

        self.new_audio_info = AudioInfo(
            title="New Song",
            uploader="New Artist",
            duration=40,  # 40秒，在默认限制内
            url="http://example.com/new.mp3"
        )
        
        # 创建测试歌曲
        self.old_song = Song(audio_info=self.old_audio_info, requester=self.mock_user)
        
    async def test_successful_song_replacement(self):
        """测试成功的歌曲替换"""
        print("\n🧪 测试成功的歌曲替换")

        # 创建另一个用户和歌曲，确保用户歌曲不在第一位
        other_user = Mock(spec=discord.Member)
        other_user.id = 11111
        other_user.display_name = "OtherUser"

        other_audio_info = AudioInfo(
            title="Other Song",
            uploader="Other Artist",
            duration=25,
            url="http://example.com/other.mp3"
        )

        # 添加其他用户的歌曲到队列第一位
        await self.queue_manager.add_song(other_audio_info, other_user)

        # 添加测试用户的歌曲到队列第二位
        await self.queue_manager.add_song(self.old_audio_info, self.mock_user)

        # 验证歌曲已添加
        self.assertEqual(self.queue_manager.get_queue_length(), 2)

        # 执行替换
        success, position, error = await self.queue_manager.replace_user_song(
            self.mock_user, self.new_audio_info
        )

        # 验证替换成功
        if not success:
            print(f"   ❌ 替换失败: {error}")
        self.assertTrue(success, f"替换失败: {error}")
        self.assertEqual(position, 2)  # 第二位
        self.assertIsNone(error)

        # 验证队列中的歌曲已被替换
        queue_songs = self.queue_manager.get_queue_songs(start=0, limit=10)
        self.assertEqual(len(queue_songs), 2)
        self.assertEqual(queue_songs[0].title, "Other Song")  # 第一位未变
        self.assertEqual(queue_songs[1].title, "New Song")    # 第二位被替换

        print("   ✅ 歌曲替换成功")
    
    async def test_replace_currently_playing_song_blocked(self):
        """测试阻止替换正在播放的歌曲"""
        print("\n🧪 测试阻止替换正在播放的歌曲")

        # 添加歌曲并设置为当前播放
        await self.queue_manager.add_song(self.old_audio_info, self.mock_user)
        current_song = await self.queue_manager.get_next_song()

        # 验证歌曲确实在播放
        self.assertIsNotNone(current_song)
        self.assertEqual(current_song.title, "Old Song")

        # 尝试替换正在播放的歌曲
        success, position, error = await self.queue_manager.replace_user_song(
            self.mock_user, self.new_audio_info
        )

        # 验证替换被阻止
        self.assertFalse(success)
        self.assertIsNone(position)
        self.assertIn("无法替换正在播放的歌曲", error)

        print("   ✅ 正在播放的歌曲替换被正确阻止")
    
    async def test_replace_next_song_blocked(self):
        """测试阻止替换即将播放的歌曲（队列第一位）"""
        print("\n🧪 测试阻止替换即将播放的歌曲")

        # 添加用户歌曲到队列第一位
        await self.queue_manager.add_song(self.old_audio_info, self.mock_user)

        # 验证歌曲在队列第一位
        queue_songs = self.queue_manager.get_queue_songs(start=0, limit=1)
        self.assertEqual(len(queue_songs), 1)
        self.assertEqual(queue_songs[0].title, "Old Song")

        # 尝试替换队列第一位的歌曲
        success, position, error = await self.queue_manager.replace_user_song(
            self.mock_user, self.new_audio_info
        )

        # 验证替换被阻止
        self.assertFalse(success)
        self.assertIsNone(position)
        self.assertIn("无法替换即将播放的歌曲", error)

        print("   ✅ 即将播放的歌曲替换被正确阻止")
    
    async def test_replace_song_duration_limit(self):
        """测试歌曲时长限制检查"""
        print("\n🧪 测试歌曲时长限制检查")
        
        # 添加歌曲到队列
        await self.queue_manager.add_song(self.old_audio_info, self.mock_user)
        
        # 创建超长歌曲
        long_audio_info = AudioInfo(
            title="Very Long Song",
            uploader="Artist",
            duration=7200,  # 2小时，超过默认限制
            url="http://example.com/long.mp3"
        )
        
        # 尝试替换为超长歌曲
        success, position, error = await self.queue_manager.replace_user_song(
            self.mock_user, long_audio_info
        )
        
        # 验证替换被阻止
        self.assertFalse(success)
        self.assertIsNone(position)
        self.assertIn("超过了最大限制", error)
        
        print("   ✅ 歌曲时长限制检查正常工作")
    
    async def test_replace_nonexistent_user_song(self):
        """测试替换不存在的用户歌曲"""
        print("\n🧪 测试替换不存在的用户歌曲")
        
        # 不添加任何歌曲到队列
        
        # 尝试替换不存在的歌曲
        success, position, error = await self.queue_manager.replace_user_song(
            self.mock_user, self.new_audio_info
        )
        
        # 验证替换失败
        self.assertFalse(success)
        self.assertIsNone(position)
        self.assertIn("没有歌曲可以替换", error)
        
        print("   ✅ 不存在用户歌曲时正确处理")
    
    async def test_replace_with_multiple_user_songs(self):
        """测试用户有多首歌曲时只替换第一首"""
        print("\n🧪 测试用户有多首歌曲时只替换第一首")
        
        # 创建另一个用户
        other_user = Mock(spec=discord.Member)
        other_user.id = 11111
        other_user.display_name = "OtherUser"
        
        # 创建另一首歌曲
        other_audio_info = AudioInfo(
            title="Other Song",
            uploader="Other Artist",
            duration=25,  # 25秒，在默认限制内
            url="http://example.com/other.mp3"
        )
        
        # 添加歌曲：其他用户 -> 测试用户 -> 测试用户
        await self.queue_manager.add_song(other_audio_info, other_user)
        await self.queue_manager.add_song(self.old_audio_info, self.mock_user)
        
        # 创建第二首用户歌曲
        second_audio_info = AudioInfo(
            title="Second User Song",
            uploader="Artist",
            duration=35,  # 35秒，在默认限制内
            url="http://example.com/second.mp3"
        )
        
        # 模拟绕过队列公平性限制添加第二首歌曲
        second_song = Song(audio_info=second_audio_info, requester=self.mock_user)
        self.queue_manager._queue.append(second_song)
        
        # 执行替换
        success, position, error = await self.queue_manager.replace_user_song(
            self.mock_user, self.new_audio_info
        )
        
        # 验证替换成功
        self.assertTrue(success)
        self.assertEqual(position, 2)  # 第二位（第一位是其他用户的歌曲）
        
        # 验证只有第一首用户歌曲被替换
        queue_songs = self.queue_manager.get_queue_songs(start=0, limit=10)
        self.assertEqual(len(queue_songs), 3)
        self.assertEqual(queue_songs[0].title, "Other Song")  # 其他用户的歌曲
        self.assertEqual(queue_songs[1].title, "New Song")    # 被替换的歌曲
        self.assertEqual(queue_songs[2].title, "Second User Song")  # 第二首用户歌曲未被替换
        
        print("   ✅ 只替换用户的第一首歌曲")


if __name__ == '__main__':
    unittest.main()
