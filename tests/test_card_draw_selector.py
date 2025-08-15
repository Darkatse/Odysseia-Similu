"""
随机歌曲选择器测试

测试随机选择算法的核心功能：
- 权重计算
- 随机选择
- 来源配置
- 统计信息
"""

import unittest
import asyncio
from unittest.mock import Mock, AsyncMock
from datetime import datetime

from similubot.app_commands.card_draw.random_selector import (
    RandomSongSelector, CardDrawConfig, CardDrawSource
)
from similubot.app_commands.card_draw.database import SongHistoryEntry


class MockDatabase:
    """模拟歌曲历史数据库"""
    
    def __init__(self):
        self.songs = []
        self.user_counts = {}
        self.total_counts = {}
    
    async def get_random_songs(self, guild_id: int, user_id=None, limit=100):
        """模拟获取随机歌曲"""
        if user_id:
            return [song for song in self.songs 
                   if song.guild_id == guild_id and song.user_id == user_id][:limit]
        else:
            return [song for song in self.songs 
                   if song.guild_id == guild_id][:limit]
    
    async def get_user_song_count(self, guild_id: int, user_id: int):
        """模拟获取用户歌曲数量"""
        return self.user_counts.get((guild_id, user_id), 0)
    
    async def get_total_song_count(self, guild_id: int):
        """模拟获取总歌曲数量"""
        return self.total_counts.get(guild_id, 0)
    
    def add_test_song(self, song_entry: SongHistoryEntry):
        """添加测试歌曲"""
        self.songs.append(song_entry)
        
        # 更新计数
        key = (song_entry.guild_id, song_entry.user_id)
        self.user_counts[key] = self.user_counts.get(key, 0) + 1
        self.total_counts[song_entry.guild_id] = self.total_counts.get(song_entry.guild_id, 0) + 1


class TestRandomSongSelector(unittest.TestCase):
    """随机歌曲选择器测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.mock_database = MockDatabase()
        self.selector = RandomSongSelector(self.mock_database)
        
        # 创建测试歌曲数据
        self.test_songs = [
            SongHistoryEntry(
                id=1,
                title="歌曲1",
                artist="艺术家1",
                url="https://example.com/song1.mp3",
                user_id=111,
                user_name="用户1",
                guild_id=1001,
                timestamp=datetime.now(),
                source_platform="YouTube",
                duration=180
            ),
            SongHistoryEntry(
                id=2,
                title="歌曲2",
                artist="艺术家2",
                url="https://example.com/song2.mp3",
                user_id=222,
                user_name="用户2",
                guild_id=1001,
                timestamp=datetime.now(),
                source_platform="NetEase",
                duration=240
            ),
            SongHistoryEntry(
                id=3,
                title="歌曲3",
                artist="艺术家3",
                url="https://example.com/song3.mp3",
                user_id=111,
                user_name="用户1",
                guild_id=1001,
                timestamp=datetime.now(),
                source_platform="Bilibili",
                duration=200
            )
        ]
        
        # 添加测试数据到模拟数据库
        for song in self.test_songs:
            self.mock_database.add_test_song(song)
    
    def test_selector_initialization(self):
        """测试选择器初始化"""
        self.assertIsNotNone(self.selector.database)
        self.assertIsNotNone(self.selector.weight_config)
        self.assertIn("recent_bonus", self.selector.weight_config)
        self.assertIn("frequency_penalty", self.selector.weight_config)
        self.assertIn("user_diversity_bonus", self.selector.weight_config)
    
    async def test_select_random_song_global_source(self):
        """测试全局来源随机选择"""
        config = CardDrawConfig(source=CardDrawSource.GLOBAL)
        
        selected_song = await self.selector.select_random_song(1001, config)
        
        self.assertIsNotNone(selected_song)
        self.assertIn(selected_song, self.test_songs)
        self.assertEqual(selected_song.guild_id, 1001)
    
    async def test_select_random_song_specific_user(self):
        """测试指定用户来源随机选择"""
        config = CardDrawConfig(
            source=CardDrawSource.SPECIFIC_USER,
            target_user_id=111
        )
        
        selected_song = await self.selector.select_random_song(1001, config)
        
        self.assertIsNotNone(selected_song)
        self.assertEqual(selected_song.user_id, 111)
        self.assertEqual(selected_song.guild_id, 1001)
    
    async def test_select_random_song_no_candidates(self):
        """测试没有候选歌曲的情况"""
        config = CardDrawConfig(source=CardDrawSource.GLOBAL)
        
        # 使用不存在的服务器ID
        selected_song = await self.selector.select_random_song(9999, config)
        
        self.assertIsNone(selected_song)
    
    async def test_get_candidates_for_user_personal(self):
        """测试获取个人池候选歌曲"""
        config = CardDrawConfig(source=CardDrawSource.PERSONAL)
        
        candidates = await self.selector.get_candidates_for_user(1001, 111, config)
        
        # 应该只返回用户111的歌曲
        self.assertEqual(len(candidates), 2)  # 用户111有2首歌
        for song in candidates:
            self.assertEqual(song.user_id, 111)
    
    async def test_get_candidates_for_user_global(self):
        """测试获取全局池候选歌曲"""
        config = CardDrawConfig(source=CardDrawSource.GLOBAL)
        
        candidates = await self.selector.get_candidates_for_user(1001, 111, config)
        
        # 应该返回所有歌曲
        self.assertEqual(len(candidates), 3)
    
    def test_weighted_random_selection_single_song(self):
        """测试单首歌曲的权重选择"""
        candidates = [self.test_songs[0]]
        
        selected = self.selector._weighted_random_selection(candidates)
        
        self.assertEqual(selected, self.test_songs[0])
    
    def test_weighted_random_selection_multiple_songs(self):
        """测试多首歌曲的权重选择"""
        candidates = self.test_songs
        
        # 多次选择以验证随机性
        selections = []
        for _ in range(10):
            selected = self.selector._weighted_random_selection(candidates)
            selections.append(selected)
        
        # 验证所有选择都在候选列表中
        for selection in selections:
            self.assertIn(selection, candidates)
    
    def test_weighted_random_selection_empty_list(self):
        """测试空候选列表的权重选择"""
        with self.assertRaises(ValueError):
            self.selector._weighted_random_selection([])
    
    def test_calculate_song_weight(self):
        """测试歌曲权重计算"""
        candidates = self.test_songs
        
        # 计算第一首歌的权重
        weight = self.selector._calculate_song_weight(self.test_songs[0], candidates)
        
        self.assertIsInstance(weight, float)
        self.assertGreater(weight, 0)
    
    def test_calculate_song_weight_user_diversity(self):
        """测试用户多样性对权重的影响"""
        candidates = self.test_songs
        
        # 用户111有2首歌，用户222有1首歌
        weight_user111 = self.selector._calculate_song_weight(self.test_songs[0], candidates)  # 用户111
        weight_user222 = self.selector._calculate_song_weight(self.test_songs[1], candidates)  # 用户222
        
        # 用户222的歌曲权重应该更高（因为歌曲数量少，多样性更好）
        self.assertGreater(weight_user222, weight_user111)
    
    async def test_get_source_statistics_global(self):
        """测试获取全局池统计信息"""
        config = CardDrawConfig(source=CardDrawSource.GLOBAL)
        
        stats = await self.selector.get_source_statistics(1001, config)
        
        self.assertEqual(stats["source"], "全局池")
        self.assertEqual(stats["total_songs"], 3)
        self.assertIn("description", stats)
    
    async def test_get_source_statistics_specific_user(self):
        """测试获取指定用户池统计信息"""
        config = CardDrawConfig(
            source=CardDrawSource.SPECIFIC_USER,
            target_user_id=111
        )
        
        stats = await self.selector.get_source_statistics(1001, config)
        
        self.assertEqual(stats["source"], "指定用户池")
        self.assertEqual(stats["total_songs"], 2)
        self.assertEqual(stats["target_user_id"], 111)
        self.assertIn("description", stats)
    
    async def test_get_source_statistics_unknown_source(self):
        """测试未知来源的统计信息"""
        config = CardDrawConfig(source=CardDrawSource.PERSONAL)  # 这个需要特殊处理
        
        stats = await self.selector.get_source_statistics(1001, config)
        
        self.assertEqual(stats["source"], "未知")
        self.assertEqual(stats["total_songs"], 0)


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
        'test_select_random_song_global_source',
        'test_select_random_song_specific_user',
        'test_select_random_song_no_candidates',
        'test_get_candidates_for_user_personal',
        'test_get_candidates_for_user_global',
        'test_get_source_statistics_global',
        'test_get_source_statistics_specific_user',
        'test_get_source_statistics_unknown_source'
    ]
    
    for method_name in async_methods:
        async_method = getattr(TestRandomSongSelector, method_name)
        
        def make_sync_wrapper(async_func):
            def sync_wrapper(self):
                return run_async_test(async_func(self))
            return sync_wrapper
        
        setattr(TestRandomSongSelector, method_name, make_sync_wrapper(async_method))


# 应用异步测试包装器
make_async_test_methods()


if __name__ == '__main__':
    unittest.main()
