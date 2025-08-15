"""
App Commands测试配置

提供测试所需的fixtures和配置
"""

import pytest
import asyncio
import logging
from unittest.mock import Mock, AsyncMock
import discord
from discord.ext import commands

from similubot.utils.config_manager import ConfigManager


@pytest.fixture
def event_loop():
    """创建事件循环fixture"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_config():
    """创建模拟配置管理器"""
    config = Mock(spec=ConfigManager)
    config.get.return_value = True  # 默认启用所有功能
    return config


@pytest.fixture
def mock_music_player():
    """创建模拟音乐播放器"""
    player = Mock()
    player.connect_to_user_channel = AsyncMock(return_value=(True, None))
    player.is_supported_url = Mock(return_value=False)
    player.detect_audio_source_type = Mock(return_value=None)
    player.add_song_to_queue = AsyncMock(return_value=(True, 1, None))
    player.get_queue_info = AsyncMock(return_value={
        "is_empty": True,
        "current_song": None,
        "queue_length": 0,
        "total_duration": 0,
        "connected": False,
        "playing": False,
        "paused": False
    })
    player.skip_current_song = AsyncMock(return_value=(True, "Test Song", None))
    player.get_queue_manager = Mock()
    return player


@pytest.fixture
def mock_interaction():
    """创建模拟Discord交互对象"""
    interaction = Mock(spec=discord.Interaction)
    interaction.guild = Mock()
    interaction.guild.id = 12345
    interaction.guild.name = "Test Guild"
    interaction.user = Mock()
    interaction.user.id = 67890
    interaction.user.display_name = "TestUser"
    interaction.user.voice = Mock()
    interaction.user.voice.channel = Mock()
    interaction.channel = Mock()
    interaction.channel.id = 11111
    interaction.client = Mock()
    interaction.response = Mock()
    interaction.response.is_done = Mock(return_value=False)
    interaction.response.send_message = AsyncMock()
    interaction.followup = Mock()
    interaction.followup.send = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    interaction.original_response = AsyncMock()
    return interaction


@pytest.fixture
def mock_bot():
    """创建模拟Discord机器人"""
    bot = Mock(spec=commands.Bot)
    bot.tree = Mock()
    bot.tree.add_command = Mock()
    bot.tree.sync = AsyncMock()
    bot.tree.clear_commands = Mock()
    bot.get_guild = Mock()
    return bot


@pytest.fixture(autouse=True)
def setup_logging():
    """设置测试日志"""
    # 禁用日志输出以保持测试输出清洁
    logging.getLogger("similubot.app_commands").setLevel(logging.CRITICAL)
    yield
    # 测试后恢复日志级别
    logging.getLogger("similubot.app_commands").setLevel(logging.DEBUG)


@pytest.fixture
def mock_audio_info():
    """创建模拟音频信息"""
    from similubot.core.interfaces import AudioInfo
    return AudioInfo(
        title="Test Song",
        duration=180,
        url="https://example.com/test.mp3",
        uploader="Test Channel"
    )


@pytest.fixture
def mock_netease_search_result():
    """创建模拟NetEase搜索结果"""
    from similubot.core.interfaces import NetEaseSearchResult
    result = Mock(spec=NetEaseSearchResult)
    result.song_id = "12345"
    result.title = "Test Song"
    result.artist = "Test Artist"
    result.album = "Test Album"
    result.duration = 180
    result.cover_url = "https://example.com/cover.jpg"
    result.get_display_name.return_value = "Test Song - Test Artist"
    result.format_duration.return_value = "3:00"
    return result


# 测试标记
pytest_plugins = []

# 自定义标记
def pytest_configure(config):
    """配置pytest标记"""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as unit test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )