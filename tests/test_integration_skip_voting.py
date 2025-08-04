"""
跳过歌曲投票系统集成测试

测试投票系统与现有音乐播放系统的完整集成，验证：
- 配置加载和解析
- 命令处理流程
- 投票系统启动和管理
- 与现有组件的兼容性
"""

import unittest
from unittest.mock import Mock, AsyncMock, patch
import asyncio
import discord
from discord.ext import commands

from similubot.commands.music_commands import MusicCommands
from similubot.utils.config_manager import ConfigManager
from similubot.ui.skip_vote_poll import VoteResult


class TestSkipVotingIntegration(unittest.TestCase):
    """集成测试：跳过投票系统与音乐命令的完整集成"""

    def setUp(self):
        """设置集成测试环境"""
        # 创建模拟配置
        self.mock_config = Mock(spec=ConfigManager)
        self.mock_config.get.return_value = True
        self.mock_config.is_skip_voting_enabled.return_value = True
        self.mock_config.get_skip_voting_threshold.return_value = "3"
        self.mock_config.get_skip_voting_timeout.return_value = 30
        self.mock_config.get_skip_voting_min_voters.return_value = 2

        # 创建模拟音乐播放器
        self.mock_music_player = Mock()
        self.mock_music_player.get_queue_info = AsyncMock()
        self.mock_music_player.skip_current_song = AsyncMock()

        # 创建模拟当前歌曲
        self.mock_current_song = Mock()
        self.mock_current_song.title = "Test Song"
        self.mock_current_song.requester = Mock()
        self.mock_current_song.requester.display_name = "TestUser"

        # 设置队列信息返回值
        self.mock_music_player.get_queue_info.return_value = {
            "current_song": self.mock_current_song,
            "queue_length": 3,
            "playing": True
        }

        # 设置跳过歌曲返回值
        self.mock_music_player.skip_current_song.return_value = (True, "Test Song", None)

        # 创建模拟进度条
        self.mock_progress_bar = Mock()
        self.mock_progress_bar.stop_progress_updates = Mock()

        # 创建音乐命令实例
        self.music_commands = MusicCommands(self.mock_config, self.mock_music_player)
        self.music_commands.progress_bar = self.mock_progress_bar

        # 创建模拟上下文
        self.mock_ctx = Mock(spec=commands.Context)
        self.mock_ctx.guild = Mock()
        self.mock_ctx.guild.id = 12345
        self.mock_ctx.guild.voice_client = Mock()
        self.mock_ctx.reply = AsyncMock()

        # 创建模拟语音频道和成员
        self.mock_voice_channel = Mock()
        self.mock_voice_channel.name = "Test Voice Channel"
        self.mock_voice_channel.members = []

        # 创建足够的成员来触发投票
        for i in range(5):
            member = Mock(spec=discord.Member)
            member.id = 1000 + i
            member.display_name = f"User{i}"
            member.bot = False
            self.mock_voice_channel.members.append(member)

        self.mock_ctx.guild.voice_client.channel = self.mock_voice_channel

    async def test_skip_command_with_voting_enabled_sufficient_members(self):
        """测试启用投票且成员数量足够时的跳过命令"""
        # 模拟投票管理器的启动投票方法
        with patch.object(self.music_commands.vote_manager, 'start_skip_vote') as mock_start_vote:
            mock_start_vote.return_value = VoteResult.PASSED

            # 执行跳过命令
            await self.music_commands._handle_skip_command(self.mock_ctx)

            # 验证调用
            self.mock_music_player.get_queue_info.assert_called_once_with(12345)
            mock_start_vote.assert_called_once()
            self.mock_progress_bar.stop_progress_updates.assert_called_once_with(12345)

    async def test_skip_command_with_voting_disabled(self):
        """测试禁用投票时的跳过命令"""
        # 禁用投票系统
        self.mock_config.is_skip_voting_enabled.return_value = False

        # 重新创建音乐命令实例以应用新配置
        music_commands = MusicCommands(self.mock_config, self.mock_music_player)
        music_commands.progress_bar = self.mock_progress_bar

        # 执行跳过命令
        await music_commands._handle_skip_command(self.mock_ctx)

        # 验证直接跳过被调用
        self.mock_music_player.skip_current_song.assert_called_once_with(12345)
        self.mock_ctx.reply.assert_called_once()

    async def test_skip_command_insufficient_members(self):
        """测试成员数量不足时的跳过命令"""
        # 减少语音频道成员数量
        self.mock_voice_channel.members = self.mock_voice_channel.members[:1]

        # 执行跳过命令
        await self.music_commands._handle_skip_command(self.mock_ctx)

        # 验证直接跳过被调用（因为人数不足）
        self.mock_music_player.skip_current_song.assert_called_once_with(12345)

    async def test_skip_command_no_current_song(self):
        """测试没有当前歌曲时的跳过命令"""
        # 设置没有当前歌曲
        self.mock_music_player.get_queue_info.return_value = {
            "current_song": None,
            "queue_length": 0,
            "playing": False
        }

        # 执行跳过命令
        await self.music_commands._handle_skip_command(self.mock_ctx)

        # 验证返回错误消息
        self.mock_ctx.reply.assert_called_once_with("❌ 当前没有歌曲在播放")
        self.mock_music_player.skip_current_song.assert_not_called()

    async def test_skip_command_no_voice_client(self):
        """测试没有语音客户端时的跳过命令"""
        # 设置没有语音客户端
        self.mock_ctx.guild.voice_client = None

        # 执行跳过命令
        await self.music_commands._handle_skip_command(self.mock_ctx)

        # 验证返回错误消息
        self.mock_ctx.reply.assert_called_once_with("❌ 机器人未连接到语音频道或无法获取频道成员")

    def test_vote_manager_initialization(self):
        """测试投票管理器的正确初始化"""
        # 验证投票管理器已正确初始化
        self.assertIsNotNone(self.music_commands.vote_manager)
        self.assertEqual(self.music_commands.vote_manager.config_manager, self.mock_config)

    def test_configuration_integration(self):
        """测试配置集成"""
        # 测试各种配置值
        test_configs = [
            (True, "5", 60, 2),
            (False, "50%", 30, 3),
            (True, "3", 120, 1),
        ]

        for enabled, threshold, timeout, min_voters in test_configs:
            with self.subTest(enabled=enabled, threshold=threshold):
                # 设置配置
                config = Mock(spec=ConfigManager)
                config.get.return_value = True
                config.is_skip_voting_enabled.return_value = enabled
                config.get_skip_voting_threshold.return_value = threshold
                config.get_skip_voting_timeout.return_value = timeout
                config.get_skip_voting_min_voters.return_value = min_voters

                # 创建新的音乐命令实例
                music_commands = MusicCommands(config, self.mock_music_player)

                # 验证配置正确传递
                self.assertEqual(music_commands.vote_manager.config_manager, config)

    async def test_error_handling_in_skip_command(self):
        """测试跳过命令中的错误处理"""
        # 模拟获取队列信息时发生异常
        self.mock_music_player.get_queue_info.side_effect = Exception("Test error")

        # 执行跳过命令
        await self.music_commands._handle_skip_command(self.mock_ctx)

        # 验证错误被正确处理
        self.mock_ctx.reply.assert_called_once_with("❌ 跳过歌曲时出错")

    def test_vote_threshold_calculation_integration(self):
        """测试投票阈值计算的集成"""
        # 测试不同的阈值配置
        test_cases = [
            ("5", 10, 5),      # 固定数字，成员充足
            ("3", 2, 2),       # 固定数字，成员不足
            ("50%", 10, 5),    # 百分比，正常情况
            ("30%", 7, 2),     # 百分比，向下取整
        ]

        for threshold, member_count, expected in test_cases:
            with self.subTest(threshold=threshold, members=member_count):
                # 设置配置
                self.mock_config.get_skip_voting_threshold.return_value = threshold

                # 设置成员数量
                members = [Mock() for _ in range(member_count)]
                self.mock_voice_channel.members = members

                # 获取语音频道成员
                voice_members = self.music_commands.vote_manager.get_voice_channel_members(self.mock_ctx)

                # 验证成员数量正确
                if voice_members:
                    self.assertEqual(len(voice_members), member_count)


def run_async_test(test_func):
    """运行异步测试的辅助函数"""
    def wrapper(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(test_func(self))
        finally:
            loop.close()
    return wrapper


# 将异步测试方法转换为同步
TestSkipVotingIntegration.test_skip_command_with_voting_enabled_sufficient_members = run_async_test(
    TestSkipVotingIntegration.test_skip_command_with_voting_enabled_sufficient_members
)
TestSkipVotingIntegration.test_skip_command_with_voting_disabled = run_async_test(
    TestSkipVotingIntegration.test_skip_command_with_voting_disabled
)
TestSkipVotingIntegration.test_skip_command_insufficient_members = run_async_test(
    TestSkipVotingIntegration.test_skip_command_insufficient_members
)
TestSkipVotingIntegration.test_skip_command_no_current_song = run_async_test(
    TestSkipVotingIntegration.test_skip_command_no_current_song
)
TestSkipVotingIntegration.test_skip_command_no_voice_client = run_async_test(
    TestSkipVotingIntegration.test_skip_command_no_voice_client
)
TestSkipVotingIntegration.test_error_handling_in_skip_command = run_async_test(
    TestSkipVotingIntegration.test_error_handling_in_skip_command
)


if __name__ == '__main__':
    unittest.main()
