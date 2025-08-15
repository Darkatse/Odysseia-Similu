"""
抽卡功能集成测试

测试整个抽卡流程的端到端功能：
- 数据库初始化
- 歌曲记录
- 随机抽取
- 命令集成
- 配置管理
"""

import unittest
import asyncio
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, AsyncMock

from similubot.app_commands.card_draw.database import SongHistoryDatabase
from similubot.app_commands.card_draw.random_selector import RandomSongSelector, CardDrawConfig, CardDrawSource
from similubot.app_commands.card_draw.card_draw_commands import CardDrawCommands
from similubot.app_commands.card_draw.source_settings_commands import SourceSettingsCommands
from similubot.core.interfaces import AudioInfo
from similubot.utils.config_manager import ConfigManager


class MockMember:
    """模拟Discord成员对象"""
    
    def __init__(self, user_id: int, display_name: str):
        self.id = user_id
        self.display_name = display_name


class MockInteraction:
    """模拟Discord交互对象"""
    
    def __init__(self, user_id=12345, guild_id=67890):
        self.user = MockMember(user_id, "测试用户")
        
        self.guild = Mock()
        self.guild.id = guild_id
        
        self.channel = Mock()
        self.channel.id = 11111
        
        self.response = Mock()
        self.response.is_done.return_value = False
        self.response.send_message = AsyncMock()
        
        self.edit_original_response = AsyncMock()


class MockMusicPlayer:
    """模拟音乐播放器"""
    
    def __init__(self):
        self.connect_to_user_channel = AsyncMock(return_value=(True, None))
        self.add_song_to_queue = AsyncMock(return_value=(True, 1, None))
        self._playback_engine = Mock()
        self._playback_engine.set_text_channel = Mock()


class TestCardDrawIntegration(unittest.TestCase):
    """抽卡功能集成测试类"""
    
    def setUp(self):
        """测试前准备"""
        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp()
        
        # 初始化组件
        self.database = SongHistoryDatabase(self.temp_dir)
        self.selector = RandomSongSelector(self.database)
        
        # 创建模拟配置
        self.mock_config = Mock(spec=ConfigManager)
        self.mock_config.get.return_value = {
            'enabled': True,
            'max_redraws': 3,
            'timeout_seconds': 60,
            'database': {
                'auto_record': True
            }
        }
        
        # 创建模拟音乐播放器
        self.mock_music_player = MockMusicPlayer()
        
        # 创建命令处理器
        self.card_draw_commands = CardDrawCommands(
            self.mock_config,
            self.mock_music_player,
            self.database,
            self.selector
        )
        
        self.source_settings_commands = SourceSettingsCommands(
            self.mock_config,
            self.mock_music_player,
            self.database,
            self.selector
        )
        
        # 模拟前置条件检查
        self.card_draw_commands.check_prerequisites = AsyncMock(return_value=True)
        self.card_draw_commands.check_voice_channel = AsyncMock(return_value=True)
        
        # 创建测试数据
        self.test_audio_infos = [
            AudioInfo(
                title="测试歌曲1",
                duration=180,
                url="https://youtube.com/watch?v=test1",
                uploader="艺术家1",
                thumbnail_url="https://example.com/thumb1.jpg",
                file_format="mp4"
            ),
            AudioInfo(
                title="测试歌曲2",
                duration=240,
                url="https://music.163.com/song/test2",
                uploader="艺术家2",
                thumbnail_url="https://example.com/thumb2.jpg",
                file_format="mp3"
            ),
            AudioInfo(
                title="测试歌曲3",
                duration=200,
                url="https://bilibili.com/video/test3",
                uploader="艺术家3",
                thumbnail_url="https://example.com/thumb3.jpg",
                file_format="mp4"
            )
        ]
        
        self.test_users = [
            MockMember(111, "用户1"),
            MockMember(222, "用户2"),
            MockMember(333, "用户3")
        ]
        
        self.test_guild_id = 67890
    
    def tearDown(self):
        """测试后清理"""
        # 删除临时目录
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    async def test_full_card_draw_workflow(self):
        """测试完整的抽卡工作流程"""
        # 1. 初始化数据库
        success = await self.database.initialize()
        self.assertTrue(success)
        
        # 2. 添加歌曲记录到历史数据库
        for i, audio_info in enumerate(self.test_audio_infos):
            user = self.test_users[i % len(self.test_users)]
            success = await self.database.add_song_record(
                audio_info, user, self.test_guild_id, "YouTube"
            )
            self.assertTrue(success)
        
        # 3. 验证数据库中有歌曲记录
        total_count = await self.database.get_total_song_count(self.test_guild_id)
        self.assertEqual(total_count, 3)
        
        # 4. 测试随机选择
        config = CardDrawConfig(source=CardDrawSource.GLOBAL)
        selected_song = await self.selector.select_random_song(self.test_guild_id, config)
        
        self.assertIsNotNone(selected_song)
        self.assertEqual(selected_song.guild_id, self.test_guild_id)
        self.assertIn(selected_song.title, [info.title for info in self.test_audio_infos])
        
        # 5. 测试抽卡命令执行
        interaction = MockInteraction()
        await self.card_draw_commands.execute(interaction)
        
        # 验证前置条件检查被调用
        self.card_draw_commands.check_prerequisites.assert_called_once()
    
    async def test_source_settings_workflow(self):
        """测试抽卡来源设置工作流程"""
        # 1. 初始化数据库并添加测试数据
        await self.database.initialize()
        
        for i, audio_info in enumerate(self.test_audio_infos):
            user = self.test_users[i % len(self.test_users)]
            await self.database.add_song_record(
                audio_info, user, self.test_guild_id, "YouTube"
            )
        
        # 2. 测试设置全局来源
        interaction = MockInteraction()
        await self.source_settings_commands.execute(
            interaction, source='global', target_user=None
        )
        
        # 验证响应被发送
        interaction.response.send_message.assert_called_once()
        
        # 3. 测试设置指定用户来源
        interaction2 = MockInteraction()
        target_user = self.test_users[0]
        
        await self.source_settings_commands.execute(
            interaction2, source='specific_user', target_user=target_user
        )
        
        # 验证响应被发送
        interaction2.response.send_message.assert_called_once()
        
        # 4. 验证用户设置被保存
        config = await self.source_settings_commands.get_user_setting(interaction2.user.id)
        self.assertEqual(config.source, CardDrawSource.SPECIFIC_USER)
        self.assertEqual(config.target_user_id, target_user.id)
    
    async def test_personal_pool_selection(self):
        """测试个人池选择功能"""
        # 1. 初始化数据库
        await self.database.initialize()
        
        # 2. 为不同用户添加歌曲
        user1 = self.test_users[0]
        user2 = self.test_users[1]
        
        # 用户1添加2首歌
        await self.database.add_song_record(
            self.test_audio_infos[0], user1, self.test_guild_id, "YouTube"
        )
        await self.database.add_song_record(
            self.test_audio_infos[1], user1, self.test_guild_id, "NetEase"
        )
        
        # 用户2添加1首歌
        await self.database.add_song_record(
            self.test_audio_infos[2], user2, self.test_guild_id, "Bilibili"
        )
        
        # 3. 测试个人池选择
        config = CardDrawConfig(source=CardDrawSource.PERSONAL)
        
        # 获取用户1的候选歌曲
        candidates_user1 = await self.selector.get_candidates_for_user(
            self.test_guild_id, user1.id, config
        )
        self.assertEqual(len(candidates_user1), 2)
        for song in candidates_user1:
            self.assertEqual(song.user_id, user1.id)
        
        # 获取用户2的候选歌曲
        candidates_user2 = await self.selector.get_candidates_for_user(
            self.test_guild_id, user2.id, config
        )
        self.assertEqual(len(candidates_user2), 1)
        self.assertEqual(candidates_user2[0].user_id, user2.id)
    
    async def test_empty_database_handling(self):
        """测试空数据库的处理"""
        # 1. 初始化空数据库
        await self.database.initialize()
        
        # 2. 测试从空数据库抽卡
        config = CardDrawConfig(source=CardDrawSource.GLOBAL)
        selected_song = await self.selector.select_random_song(self.test_guild_id, config)
        
        self.assertIsNone(selected_song)
        
        # 3. 测试来源验证
        result = await self.source_settings_commands._validate_source_setting(
            self.test_guild_id, CardDrawSource.GLOBAL, None
        )
        
        self.assertFalse(result['valid'])
        self.assertIn("还没有歌曲历史记录", result['message'])
    
    async def test_weight_algorithm_consistency(self):
        """测试权重算法的一致性"""
        # 1. 初始化数据库并添加测试数据
        await self.database.initialize()
        
        # 添加多首歌曲，其中一些用户有更多歌曲
        for i in range(10):
            user = self.test_users[i % 2]  # 只使用前两个用户
            audio_info = AudioInfo(
                title=f"歌曲{i}",
                duration=180,
                url=f"https://example.com/song{i}.mp3",
                uploader=f"艺术家{i}",
                thumbnail_url=f"https://example.com/thumb{i}.jpg"
            )
            await self.database.add_song_record(
                audio_info, user, self.test_guild_id, "YouTube"
            )
        
        # 2. 多次随机选择，验证权重算法的工作
        config = CardDrawConfig(source=CardDrawSource.GLOBAL)
        selections = []
        
        for _ in range(20):
            selected = await self.selector.select_random_song(self.test_guild_id, config)
            if selected:
                selections.append(selected.user_id)
        
        # 验证选择结果包含不同用户的歌曲
        unique_users = set(selections)
        self.assertGreater(len(unique_users), 1, "权重算法应该选择不同用户的歌曲")
    
    async def test_database_persistence(self):
        """测试数据库持久化"""
        # 1. 初始化数据库并添加数据
        await self.database.initialize()
        
        await self.database.add_song_record(
            self.test_audio_infos[0], 
            self.test_users[0], 
            self.test_guild_id, 
            "YouTube"
        )
        
        # 2. 创建新的数据库实例（模拟重启）
        new_database = SongHistoryDatabase(self.temp_dir)
        await new_database.initialize()
        
        # 3. 验证数据仍然存在
        count = await new_database.get_total_song_count(self.test_guild_id)
        self.assertEqual(count, 1)
        
        songs = await new_database.get_random_songs(self.test_guild_id)
        self.assertEqual(len(songs), 1)
        self.assertEqual(songs[0].title, "测试歌曲1")


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
    async_methods = [name for name in dir(TestCardDrawIntegration) 
                    if name.startswith('test_') and asyncio.iscoroutinefunction(getattr(TestCardDrawIntegration, name))]
    
    for method_name in async_methods:
        async_method = getattr(TestCardDrawIntegration, method_name)
        
        def make_sync_wrapper(async_func):
            def sync_wrapper(self):
                return run_async_test(async_func(self))
            return sync_wrapper
        
        setattr(TestCardDrawIntegration, method_name, make_sync_wrapper(async_method))


# 应用异步测试包装器
make_async_test_methods()


if __name__ == '__main__':
    unittest.main()
