"""
抽卡命令测试

测试抽卡命令的核心功能：
- 命令执行
- 用户交互
- 错误处理
- 配置管理
"""

import unittest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from similubot.app_commands.card_draw.card_draw_commands import CardDrawCommands, CardDrawView
from similubot.app_commands.card_draw.source_settings_commands import SourceSettingsCommands
from similubot.app_commands.card_draw.random_selector import CardDrawConfig, CardDrawSource
from similubot.app_commands.card_draw.database import SongHistoryEntry
from similubot.utils.config_manager import ConfigManager


class MockInteraction:
    """模拟Discord交互对象"""
    
    def __init__(self, user_id=12345, guild_id=67890):
        self.user = Mock()
        self.user.id = user_id
        self.user.display_name = "测试用户"
        
        self.guild = Mock()
        self.guild.id = guild_id
        
        self.channel = Mock()
        self.channel.id = 11111
        
        self.response = Mock()
        self.response.is_done.return_value = False
        self.response.send_message = AsyncMock()
        
        self.edit_original_response = AsyncMock()


class MockDatabase:
    """模拟歌曲历史数据库"""
    
    def __init__(self):
        self.songs = []
        self.user_counts = {}
        self.total_counts = {}
    
    async def get_random_songs(self, guild_id: int, user_id=None, limit=100):
        if user_id:
            return [song for song in self.songs 
                   if song.guild_id == guild_id and song.user_id == user_id][:limit]
        else:
            return [song for song in self.songs 
                   if song.guild_id == guild_id][:limit]
    
    async def get_user_song_count(self, guild_id: int, user_id: int):
        return self.user_counts.get((guild_id, user_id), 0)
    
    async def get_total_song_count(self, guild_id: int):
        return self.total_counts.get(guild_id, 0)
    
    def add_test_song(self, song_entry: SongHistoryEntry):
        self.songs.append(song_entry)
        key = (song_entry.guild_id, song_entry.user_id)
        self.user_counts[key] = self.user_counts.get(key, 0) + 1
        self.total_counts[song_entry.guild_id] = self.total_counts.get(song_entry.guild_id, 0) + 1


class MockSelector:
    """模拟随机选择器"""
    
    def __init__(self, database):
        self.database = database
        self.test_song = SongHistoryEntry(
            id=1,
            title="测试歌曲",
            artist="测试艺术家",
            url="https://example.com/test.mp3",
            user_id=12345,
            user_name="测试用户",
            guild_id=67890,
            timestamp=datetime.now(),
            source_platform="YouTube",
            duration=180,
            thumbnail_url="https://example.com/thumb.jpg"
        )
    
    async def get_candidates_for_user(self, guild_id, user_id, config):
        return [self.test_song]
    
    async def _get_candidates(self, guild_id, config):
        return [self.test_song]
    
    def _weighted_random_selection(self, candidates):
        return candidates[0] if candidates else None
    
    async def get_source_statistics(self, guild_id, config):
        return {
            "source": "全局池",
            "total_songs": 1,
            "description": "测试统计"
        }


class MockMusicPlayer:
    """模拟音乐播放器"""
    
    def __init__(self):
        self.connect_to_user_channel = AsyncMock(return_value=(True, None))
        self.add_song_to_queue = AsyncMock(return_value=(True, 1, None))
        self._playback_engine = Mock()
        self._playback_engine.set_text_channel = Mock()


class TestCardDrawCommands(unittest.TestCase):
    """抽卡命令测试类"""
    
    def setUp(self):
        """测试前准备"""
        # 创建模拟对象
        self.mock_config = Mock(spec=ConfigManager)
        self.mock_config.get.return_value = {
            'max_redraws': 3,
            'timeout_seconds': 60
        }
        
        self.mock_music_player = MockMusicPlayer()
        self.mock_database = MockDatabase()
        self.mock_selector = MockSelector(self.mock_database)
        
        # 创建命令处理器
        self.card_draw_commands = CardDrawCommands(
            self.mock_config,
            self.mock_music_player,
            self.mock_database,
            self.mock_selector
        )
        
        # 模拟前置条件检查
        self.card_draw_commands.check_prerequisites = AsyncMock(return_value=True)
        self.card_draw_commands.check_voice_channel = AsyncMock(return_value=True)
        self.card_draw_commands.send_error_response = AsyncMock()
    
    async def test_execute_command_success(self):
        """测试成功执行抽卡命令"""
        interaction = MockInteraction()
        
        # 执行命令
        await self.card_draw_commands.execute(interaction)
        
        # 验证前置条件检查被调用
        self.card_draw_commands.check_prerequisites.assert_called_once_with(interaction)
    
    async def test_execute_command_prerequisites_fail(self):
        """测试前置条件检查失败"""
        interaction = MockInteraction()
        self.card_draw_commands.check_prerequisites.return_value = False
        
        # 执行命令
        await self.card_draw_commands.execute(interaction)
        
        # 验证前置条件检查被调用，但后续流程不执行
        self.card_draw_commands.check_prerequisites.assert_called_once_with(interaction)
    
    def test_create_card_draw_embed(self):
        """测试创建抽卡结果嵌入消息"""
        song_entry = SongHistoryEntry(
            id=1,
            title="测试歌曲",
            artist="测试艺术家",
            url="https://example.com/test.mp3",
            user_id=12345,
            user_name="测试用户",
            guild_id=67890,
            timestamp=datetime.now(),
            source_platform="YouTube",
            duration=180,
            thumbnail_url="https://example.com/thumb.jpg"
        )
        
        embed = self.card_draw_commands._create_card_draw_embed(song_entry, 2)
        
        # 验证嵌入消息内容
        self.assertEqual(embed.title, "🎲 随机抽卡结果")
        self.assertIn("测试歌曲", str(embed.fields))
        self.assertIn("测试艺术家", str(embed.fields))
        self.assertIn("剩余 2 次", str(embed.fields))
    
    async def test_send_no_songs_message(self):
        """测试发送没有歌曲的消息"""
        interaction = MockInteraction()
        config = CardDrawConfig(source=CardDrawSource.GLOBAL)
        
        await self.card_draw_commands._send_no_songs_message(interaction, config)
        
        # 验证响应被发送
        interaction.response.send_message.assert_called_once()
        
        # 获取发送的嵌入消息
        call_args = interaction.response.send_message.call_args
        embed = call_args[1]['embed']
        self.assertEqual(embed.title, "❌ 抽卡失败")
    
    def test_format_duration(self):
        """测试时长格式化"""
        # 测试不同时长
        self.assertEqual(self.card_draw_commands._format_duration(60), "1:00")
        self.assertEqual(self.card_draw_commands._format_duration(125), "2:05")
        self.assertEqual(self.card_draw_commands._format_duration(3661), "61:01")
    
    async def test_get_user_card_draw_config(self):
        """测试获取用户抽卡配置"""
        config = await self.card_draw_commands._get_user_card_draw_config(12345)
        
        self.assertEqual(config.source, CardDrawSource.GLOBAL)
        self.assertEqual(config.max_redraws, 3)
        self.assertEqual(config.timeout_seconds, 60)


class TestSourceSettingsCommands(unittest.TestCase):
    """抽卡来源设置命令测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.mock_config = Mock(spec=ConfigManager)
        self.mock_music_player = MockMusicPlayer()
        self.mock_database = MockDatabase()
        self.mock_selector = MockSelector(self.mock_database)
        
        # 添加测试数据
        self.mock_database.total_counts[67890] = 5
        self.mock_database.user_counts[(67890, 12345)] = 2
        
        self.source_settings_commands = SourceSettingsCommands(
            self.mock_config,
            self.mock_music_player,
            self.mock_database,
            self.mock_selector
        )
    
    async def test_execute_global_source(self):
        """测试设置全局来源"""
        interaction = MockInteraction()
        
        await self.source_settings_commands.execute(
            interaction, 
            source='global', 
            target_user=None
        )
        
        # 验证响应被发送
        interaction.response.send_message.assert_called_once()
    
    async def test_execute_specific_user_source(self):
        """测试设置指定用户来源"""
        interaction = MockInteraction()
        target_user = Mock()
        target_user.id = 12345
        target_user.display_name = "目标用户"
        
        await self.source_settings_commands.execute(
            interaction,
            source='specific_user',
            target_user=target_user
        )
        
        # 验证响应被发送
        interaction.response.send_message.assert_called_once()
    
    async def test_execute_specific_user_without_target(self):
        """测试设置指定用户来源但未提供目标用户"""
        interaction = MockInteraction()
        
        await self.source_settings_commands.execute(
            interaction,
            source='specific_user',
            target_user=None
        )
        
        # 应该发送错误消息
        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args
        embed = call_args[1]['embed']
        self.assertEqual(embed.title, "❌ 设置失败")
    
    async def test_validate_source_setting_global_valid(self):
        """测试验证全局来源设置（有效）"""
        result = await self.source_settings_commands._validate_source_setting(
            67890, CardDrawSource.GLOBAL, None
        )
        
        self.assertTrue(result['valid'])
        self.assertEqual(result['stats']['total_songs'], 5)
    
    async def test_validate_source_setting_global_empty(self):
        """测试验证全局来源设置（空数据库）"""
        result = await self.source_settings_commands._validate_source_setting(
            99999, CardDrawSource.GLOBAL, None
        )
        
        self.assertFalse(result['valid'])
        self.assertIn("还没有歌曲历史记录", result['message'])
    
    async def test_get_user_setting_default(self):
        """测试获取用户设置（默认值）"""
        config = await self.source_settings_commands.get_user_setting(12345)
        
        self.assertEqual(config.source, CardDrawSource.GLOBAL)
        self.assertIsNone(config.target_user_id)
    
    async def test_save_and_get_user_setting(self):
        """测试保存和获取用户设置"""
        # 保存设置
        await self.source_settings_commands._save_user_setting(
            12345, CardDrawSource.SPECIFIC_USER, 67890
        )
        
        # 获取设置
        config = await self.source_settings_commands.get_user_setting(12345)
        
        self.assertEqual(config.source, CardDrawSource.SPECIFIC_USER)
        self.assertEqual(config.target_user_id, 67890)


class TestCardDrawView(unittest.TestCase):
    """抽卡交互视图测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.mock_command_handler = Mock()
        self.mock_command_handler._add_song_to_queue = AsyncMock(return_value=True)
        self.mock_command_handler._handle_redraw = AsyncMock()
        
        self.test_song = SongHistoryEntry(
            id=1,
            title="测试歌曲",
            artist="测试艺术家",
            url="https://example.com/test.mp3",
            user_id=12345,
            user_name="测试用户",
            guild_id=67890,
            timestamp=datetime.now(),
            source_platform="YouTube",
            duration=180
        )
        
        self.config = CardDrawConfig(source=CardDrawSource.GLOBAL)
        
        self.view = CardDrawView(
            self.mock_command_handler,
            self.test_song,
            12345,
            self.config,
            2
        )
    
    def test_view_initialization(self):
        """测试视图初始化"""
        self.assertEqual(self.view.user_id, 12345)
        self.assertEqual(self.view.remaining_redraws, 2)
        self.assertEqual(self.view.song_entry, self.test_song)
    
    def test_create_confirmed_embed(self):
        """测试创建确认嵌入消息"""
        embed = self.view._create_confirmed_embed()
        
        self.assertEqual(embed.title, "🎵 抽卡完成")
        self.assertIn("测试歌曲", embed.description)
    
    def test_format_duration(self):
        """测试时长格式化"""
        self.assertEqual(self.view._format_duration(180), "3:00")
        self.assertEqual(self.view._format_duration(65), "1:05")


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
    test_classes = [TestCardDrawCommands, TestSourceSettingsCommands]
    
    for test_class in test_classes:
        async_methods = [name for name in dir(test_class) 
                        if name.startswith('test_') and asyncio.iscoroutinefunction(getattr(test_class, name))]
        
        for method_name in async_methods:
            async_method = getattr(test_class, method_name)
            
            def make_sync_wrapper(async_func):
                def sync_wrapper(self):
                    return run_async_test(async_func(self))
                return sync_wrapper
            
            setattr(test_class, method_name, make_sync_wrapper(async_method))


# 应用异步测试包装器
make_async_test_methods()


if __name__ == '__main__':
    unittest.main()
