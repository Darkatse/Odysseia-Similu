"""
歌曲历史数据库测试

测试歌曲历史数据库的核心功能：
- 数据库初始化
- 歌曲记录添加
- 随机查询
- 统计功能
"""

import unittest
import asyncio
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, AsyncMock

from similubot.app_commands.card_draw.database import SongHistoryDatabase, SongHistoryEntry
from similubot.core.interfaces import AudioInfo
import discord


class MockMember:
    """模拟Discord成员对象"""
    
    def __init__(self, user_id: int, display_name: str):
        self.id = user_id
        self.display_name = display_name


class TestSongHistoryDatabase(unittest.TestCase):
    """歌曲历史数据库测试类"""
    
    def setUp(self):
        """测试前准备"""
        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp()
        self.database = SongHistoryDatabase(self.temp_dir)
        
        # 创建测试数据
        self.test_audio_info = AudioInfo(
            title="测试歌曲",
            duration=180,
            url="https://example.com/test.mp3",
            uploader="测试艺术家",
            thumbnail_url="https://example.com/thumb.jpg",
            file_format="mp3"
        )
        
        self.test_user = MockMember(12345, "测试用户")
        self.test_guild_id = 67890
    
    def tearDown(self):
        """测试后清理"""
        # 删除临时目录
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_database_initialization(self):
        """测试数据库初始化"""
        # 检查数据库文件路径
        expected_path = Path(self.temp_dir) / "song_history.db"
        self.assertEqual(self.database.db_path, expected_path)
        
        # 检查数据目录创建
        self.assertTrue(self.database.data_dir.exists())
    
    async def test_create_tables(self):
        """测试表结构创建"""
        # 初始化数据库
        success = await self.database.initialize()
        self.assertTrue(success)
        
        # 检查数据库文件是否创建
        self.assertTrue(self.database.db_path.exists())
    
    async def test_add_song_record(self):
        """测试添加歌曲记录"""
        # 初始化数据库
        await self.database.initialize()
        
        # 添加歌曲记录
        success = await self.database.add_song_record(
            self.test_audio_info,
            self.test_user,
            self.test_guild_id,
            "YouTube"
        )
        
        self.assertTrue(success)
    
    async def test_get_random_songs_empty_database(self):
        """测试从空数据库获取随机歌曲"""
        # 初始化数据库
        await self.database.initialize()
        
        # 查询随机歌曲
        songs = await self.database.get_random_songs(self.test_guild_id)
        
        self.assertEqual(len(songs), 0)
    
    async def test_get_random_songs_with_data(self):
        """测试从有数据的数据库获取随机歌曲"""
        # 初始化数据库
        await self.database.initialize()
        
        # 添加测试数据
        await self.database.add_song_record(
            self.test_audio_info,
            self.test_user,
            self.test_guild_id,
            "YouTube"
        )
        
        # 查询随机歌曲
        songs = await self.database.get_random_songs(self.test_guild_id, limit=5)
        
        self.assertEqual(len(songs), 1)
        self.assertEqual(songs[0].title, "测试歌曲")
        self.assertEqual(songs[0].user_id, 12345)
        self.assertEqual(songs[0].guild_id, 67890)
    
    async def test_get_user_song_count(self):
        """测试获取用户歌曲数量"""
        # 初始化数据库
        await self.database.initialize()
        
        # 初始数量应为0
        count = await self.database.get_user_song_count(self.test_guild_id, self.test_user.id)
        self.assertEqual(count, 0)
        
        # 添加歌曲记录
        await self.database.add_song_record(
            self.test_audio_info,
            self.test_user,
            self.test_guild_id,
            "YouTube"
        )
        
        # 数量应为1
        count = await self.database.get_user_song_count(self.test_guild_id, self.test_user.id)
        self.assertEqual(count, 1)
    
    async def test_get_total_song_count(self):
        """测试获取总歌曲数量"""
        # 初始化数据库
        await self.database.initialize()
        
        # 初始数量应为0
        count = await self.database.get_total_song_count(self.test_guild_id)
        self.assertEqual(count, 0)
        
        # 添加歌曲记录
        await self.database.add_song_record(
            self.test_audio_info,
            self.test_user,
            self.test_guild_id,
            "YouTube"
        )
        
        # 数量应为1
        count = await self.database.get_total_song_count(self.test_guild_id)
        self.assertEqual(count, 1)
    
    async def test_multiple_users_and_guilds(self):
        """测试多用户多服务器场景"""
        # 初始化数据库
        await self.database.initialize()
        
        # 创建多个用户和服务器
        user1 = MockMember(111, "用户1")
        user2 = MockMember(222, "用户2")
        guild1 = 1001
        guild2 = 1002
        
        # 添加不同用户和服务器的歌曲
        await self.database.add_song_record(self.test_audio_info, user1, guild1, "YouTube")
        await self.database.add_song_record(self.test_audio_info, user2, guild1, "NetEase")
        await self.database.add_song_record(self.test_audio_info, user1, guild2, "Bilibili")
        
        # 测试服务器1的总数量
        count_guild1 = await self.database.get_total_song_count(guild1)
        self.assertEqual(count_guild1, 2)
        
        # 测试服务器2的总数量
        count_guild2 = await self.database.get_total_song_count(guild2)
        self.assertEqual(count_guild2, 1)
        
        # 测试用户1在服务器1的数量
        count_user1_guild1 = await self.database.get_user_song_count(guild1, user1.id)
        self.assertEqual(count_user1_guild1, 1)
        
        # 测试用户2在服务器1的数量
        count_user2_guild1 = await self.database.get_user_song_count(guild1, user2.id)
        self.assertEqual(count_user2_guild1, 1)
    
    def test_row_to_entry_conversion(self):
        """测试数据库行到条目对象的转换"""
        # 模拟数据库行数据
        test_row = (
            1,  # id
            "测试歌曲",  # title
            "测试艺术家",  # artist
            "https://example.com/test.mp3",  # url
            12345,  # user_id
            "测试用户",  # user_name
            67890,  # guild_id
            "2023-01-01T12:00:00",  # timestamp
            "YouTube",  # source_platform
            180,  # duration
            "https://example.com/thumb.jpg",  # thumbnail_url
            "mp3"  # file_format
        )
        
        # 转换为条目对象
        entry = self.database._row_to_entry(test_row)
        
        # 验证转换结果
        self.assertEqual(entry.id, 1)
        self.assertEqual(entry.title, "测试歌曲")
        self.assertEqual(entry.artist, "测试艺术家")
        self.assertEqual(entry.url, "https://example.com/test.mp3")
        self.assertEqual(entry.user_id, 12345)
        self.assertEqual(entry.user_name, "测试用户")
        self.assertEqual(entry.guild_id, 67890)
        self.assertEqual(entry.source_platform, "YouTube")
        self.assertEqual(entry.duration, 180)
        self.assertEqual(entry.thumbnail_url, "https://example.com/thumb.jpg")
        self.assertEqual(entry.file_format, "mp3")
        self.assertIsInstance(entry.timestamp, datetime)


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
    async_methods = [
        'test_create_tables',
        'test_add_song_record',
        'test_get_random_songs_empty_database',
        'test_get_random_songs_with_data',
        'test_get_user_song_count',
        'test_get_total_song_count',
        'test_multiple_users_and_guilds'
    ]
    
    for method_name in async_methods:
        async_method = getattr(TestSongHistoryDatabase, method_name)
        
        def make_sync_wrapper(async_func):
            def sync_wrapper(self):
                return run_async_test(async_func(self))
            return sync_wrapper
        
        setattr(TestSongHistoryDatabase, method_name, make_sync_wrapper(async_method))


# 应用异步测试包装器
make_async_test_methods()


if __name__ == '__main__':
    unittest.main()
