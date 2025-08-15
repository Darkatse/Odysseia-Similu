"""
用户去重功能测试

测试歌曲历史数据库的按用户去重功能：
- 同一用户添加相同歌曲时更新时间戳
- 不同用户可以添加相同歌曲
- 去重逻辑的正确性
- 数据库一致性
"""

import unittest
import asyncio
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock

from similubot.app_commands.card_draw.database import SongHistoryDatabase
from similubot.core.interfaces import AudioInfo


class MockMember:
    """模拟Discord成员对象"""
    
    def __init__(self, user_id: int, display_name: str):
        self.id = user_id
        self.display_name = display_name


class TestUserDeduplication(unittest.TestCase):
    """用户去重功能测试类"""
    
    def setUp(self):
        """测试前准备"""
        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp()
        self.database = SongHistoryDatabase(self.temp_dir)
        
        # 创建测试数据
        self.test_audio_info = AudioInfo(
            title="测试歌曲",
            duration=180,
            url="https://youtube.com/watch?v=test123",
            uploader="测试艺术家",
            thumbnail_url="https://example.com/thumb.jpg",
            file_format="mp4"
        )
        
        self.test_audio_info_2 = AudioInfo(
            title="另一首歌曲",
            duration=240,
            url="https://youtube.com/watch?v=test456",
            uploader="另一个艺术家",
            thumbnail_url="https://example.com/thumb2.jpg",
            file_format="mp3"
        )
        
        self.user1 = MockMember(111, "用户1")
        self.user2 = MockMember(222, "用户2")
        self.guild_id = 67890
    
    def tearDown(self):
        """测试后清理"""
        # 删除临时目录
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    async def test_first_time_add_song(self):
        """测试首次添加歌曲"""
        # 初始化数据库
        await self.database.initialize()
        
        # 添加歌曲记录
        success = await self.database.add_song_record(
            self.test_audio_info, self.user1, self.guild_id, "YouTube"
        )
        
        self.assertTrue(success)
        
        # 验证记录被添加
        total_count = await self.database.get_total_song_count(self.guild_id)
        self.assertEqual(total_count, 1)
        
        user_count = await self.database.get_user_song_count(self.guild_id, self.user1.id)
        self.assertEqual(user_count, 1)
    
    async def test_same_user_same_song_deduplication(self):
        """测试同一用户添加相同歌曲时的去重"""
        # 初始化数据库
        await self.database.initialize()
        
        # 第一次添加歌曲
        success1 = await self.database.add_song_record(
            self.test_audio_info, self.user1, self.guild_id, "YouTube"
        )
        self.assertTrue(success1)
        
        # 获取第一次添加的时间戳
        songs_before = await self.database.get_random_songs(self.guild_id, self.user1.id)
        self.assertEqual(len(songs_before), 1)
        first_timestamp = songs_before[0].timestamp
        
        # 等待一小段时间确保时间戳不同
        await asyncio.sleep(0.1)
        
        # 第二次添加相同歌曲（应该更新而不是插入）
        success2 = await self.database.add_song_record(
            self.test_audio_info, self.user1, self.guild_id, "YouTube"
        )
        self.assertTrue(success2)
        
        # 验证总数量仍为1（去重成功）
        total_count = await self.database.get_total_song_count(self.guild_id)
        self.assertEqual(total_count, 1)
        
        user_count = await self.database.get_user_song_count(self.guild_id, self.user1.id)
        self.assertEqual(user_count, 1)
        
        # 验证时间戳被更新
        songs_after = await self.database.get_random_songs(self.guild_id, self.user1.id)
        self.assertEqual(len(songs_after), 1)
        second_timestamp = songs_after[0].timestamp
        
        # 第二次的时间戳应该更新
        self.assertGreater(second_timestamp, first_timestamp)
    
    async def test_different_users_same_song_no_deduplication(self):
        """测试不同用户添加相同歌曲时不去重"""
        # 初始化数据库
        await self.database.initialize()
        
        # 用户1添加歌曲
        success1 = await self.database.add_song_record(
            self.test_audio_info, self.user1, self.guild_id, "YouTube"
        )
        self.assertTrue(success1)
        
        # 用户2添加相同歌曲
        success2 = await self.database.add_song_record(
            self.test_audio_info, self.user2, self.guild_id, "YouTube"
        )
        self.assertTrue(success2)
        
        # 验证总数量为2（不同用户不去重）
        total_count = await self.database.get_total_song_count(self.guild_id)
        self.assertEqual(total_count, 2)
        
        # 验证每个用户都有1首歌
        user1_count = await self.database.get_user_song_count(self.guild_id, self.user1.id)
        self.assertEqual(user1_count, 1)
        
        user2_count = await self.database.get_user_song_count(self.guild_id, self.user2.id)
        self.assertEqual(user2_count, 1)
        
        # 验证两个用户的歌曲记录都存在
        user1_songs = await self.database.get_random_songs(self.guild_id, self.user1.id)
        user2_songs = await self.database.get_random_songs(self.guild_id, self.user2.id)
        
        self.assertEqual(len(user1_songs), 1)
        self.assertEqual(len(user2_songs), 1)
        self.assertEqual(user1_songs[0].user_id, self.user1.id)
        self.assertEqual(user2_songs[0].user_id, self.user2.id)
    
    async def test_same_user_different_songs_no_deduplication(self):
        """测试同一用户添加不同歌曲时不去重"""
        # 初始化数据库
        await self.database.initialize()
        
        # 添加第一首歌
        success1 = await self.database.add_song_record(
            self.test_audio_info, self.user1, self.guild_id, "YouTube"
        )
        self.assertTrue(success1)
        
        # 添加第二首歌
        success2 = await self.database.add_song_record(
            self.test_audio_info_2, self.user1, self.guild_id, "NetEase"
        )
        self.assertTrue(success2)
        
        # 验证总数量为2
        total_count = await self.database.get_total_song_count(self.guild_id)
        self.assertEqual(total_count, 2)
        
        # 验证用户有2首歌
        user_count = await self.database.get_user_song_count(self.guild_id, self.user1.id)
        self.assertEqual(user_count, 2)
        
        # 验证两首歌都存在
        user_songs = await self.database.get_random_songs(self.guild_id, self.user1.id)
        self.assertEqual(len(user_songs), 2)
        
        # 验证歌曲URL不同
        urls = [song.url for song in user_songs]
        self.assertIn(self.test_audio_info.url, urls)
        self.assertIn(self.test_audio_info_2.url, urls)
    
    async def test_deduplication_updates_metadata(self):
        """测试去重时更新歌曲元数据"""
        # 初始化数据库
        await self.database.initialize()
        
        # 第一次添加歌曲
        await self.database.add_song_record(
            self.test_audio_info, self.user1, self.guild_id, "YouTube"
        )
        
        # 创建相同URL但不同元数据的歌曲
        updated_audio_info = AudioInfo(
            title="更新后的标题",
            duration=200,  # 不同的时长
            url=self.test_audio_info.url,  # 相同的URL
            uploader="更新后的艺术家",
            thumbnail_url="https://example.com/new_thumb.jpg",
            file_format="mp3"
        )
        
        # 第二次添加（应该更新元数据）
        await self.database.add_song_record(
            updated_audio_info, self.user1, self.guild_id, "NetEase"
        )
        
        # 验证记录被更新
        user_songs = await self.database.get_random_songs(self.guild_id, self.user1.id)
        self.assertEqual(len(user_songs), 1)
        
        updated_song = user_songs[0]
        self.assertEqual(updated_song.title, "更新后的标题")
        self.assertEqual(updated_song.artist, "更新后的艺术家")
        self.assertEqual(updated_song.duration, 200)
        self.assertEqual(updated_song.source_platform, "NetEase")
        self.assertEqual(updated_song.thumbnail_url, "https://example.com/new_thumb.jpg")
        self.assertEqual(updated_song.file_format, "mp3")
    
    async def test_deduplication_across_guilds(self):
        """测试跨服务器的去重行为"""
        # 初始化数据库
        await self.database.initialize()
        
        guild1 = 1001
        guild2 = 1002
        
        # 在服务器1添加歌曲
        success1 = await self.database.add_song_record(
            self.test_audio_info, self.user1, guild1, "YouTube"
        )
        self.assertTrue(success1)
        
        # 在服务器2添加相同歌曲（应该不去重，因为是不同服务器）
        success2 = await self.database.add_song_record(
            self.test_audio_info, self.user1, guild2, "YouTube"
        )
        self.assertTrue(success2)
        
        # 验证两个服务器都有记录
        guild1_count = await self.database.get_total_song_count(guild1)
        guild2_count = await self.database.get_total_song_count(guild2)
        
        self.assertEqual(guild1_count, 1)
        self.assertEqual(guild2_count, 1)
        
        # 验证用户在两个服务器都有歌曲
        user1_guild1_count = await self.database.get_user_song_count(guild1, self.user1.id)
        user1_guild2_count = await self.database.get_user_song_count(guild2, self.user1.id)
        
        self.assertEqual(user1_guild1_count, 1)
        self.assertEqual(user1_guild2_count, 1)
    
    async def test_deduplication_with_user_name_update(self):
        """测试去重时更新用户名"""
        # 初始化数据库
        await self.database.initialize()
        
        # 第一次添加歌曲
        await self.database.add_song_record(
            self.test_audio_info, self.user1, self.guild_id, "YouTube"
        )
        
        # 创建相同用户但不同显示名的对象
        updated_user = MockMember(self.user1.id, "新的用户名")
        
        # 第二次添加相同歌曲（应该更新用户名）
        await self.database.add_song_record(
            self.test_audio_info, updated_user, self.guild_id, "YouTube"
        )
        
        # 验证用户名被更新
        user_songs = await self.database.get_random_songs(self.guild_id, self.user1.id)
        self.assertEqual(len(user_songs), 1)
        self.assertEqual(user_songs[0].user_name, "新的用户名")
    
    async def test_complex_deduplication_scenario(self):
        """测试复杂的去重场景"""
        # 初始化数据库
        await self.database.initialize()
        
        # 场景：多个用户，多首歌曲，多次添加
        
        # 用户1添加歌曲A
        await self.database.add_song_record(
            self.test_audio_info, self.user1, self.guild_id, "YouTube"
        )
        
        # 用户2添加歌曲A（不同用户，不去重）
        await self.database.add_song_record(
            self.test_audio_info, self.user2, self.guild_id, "YouTube"
        )
        
        # 用户1添加歌曲B
        await self.database.add_song_record(
            self.test_audio_info_2, self.user1, self.guild_id, "NetEase"
        )
        
        # 用户1再次添加歌曲A（相同用户，去重）
        await self.database.add_song_record(
            self.test_audio_info, self.user1, self.guild_id, "YouTube"
        )
        
        # 用户2再次添加歌曲A（相同用户，去重）
        await self.database.add_song_record(
            self.test_audio_info, self.user2, self.guild_id, "YouTube"
        )
        
        # 验证最终状态
        total_count = await self.database.get_total_song_count(self.guild_id)
        self.assertEqual(total_count, 3)  # 用户1的歌曲A和B，用户2的歌曲A
        
        user1_count = await self.database.get_user_song_count(self.guild_id, self.user1.id)
        user2_count = await self.database.get_user_song_count(self.guild_id, self.user2.id)
        
        self.assertEqual(user1_count, 2)  # 歌曲A和B
        self.assertEqual(user2_count, 1)  # 歌曲A
        
        # 验证歌曲内容
        user1_songs = await self.database.get_random_songs(self.guild_id, self.user1.id)
        user2_songs = await self.database.get_random_songs(self.guild_id, self.user2.id)
        
        user1_urls = [song.url for song in user1_songs]
        user2_urls = [song.url for song in user2_songs]
        
        self.assertIn(self.test_audio_info.url, user1_urls)
        self.assertIn(self.test_audio_info_2.url, user1_urls)
        self.assertIn(self.test_audio_info.url, user2_urls)


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
    async_methods = [name for name in dir(TestUserDeduplication) 
                    if name.startswith('test_') and asyncio.iscoroutinefunction(getattr(TestUserDeduplication, name))]
    
    for method_name in async_methods:
        async_method = getattr(TestUserDeduplication, method_name)
        
        def make_sync_wrapper(async_func):
            def sync_wrapper(self):
                return run_async_test(async_func(self))
            return sync_wrapper
        
        setattr(TestUserDeduplication, method_name, make_sync_wrapper(async_method))


# 应用异步测试包装器
make_async_test_methods()


if __name__ == '__main__':
    unittest.main()
