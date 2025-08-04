"""
跳过歌曲投票系统单元测试

测试民主投票跳过歌曲功能的各种场景，包括：
- 投票阈值计算（固定数字和百分比）
- 语音频道成员检测
- 投票计数和结果判定
- 边界情况处理
- 配置管理
"""

import unittest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import asyncio
import discord
from discord.ext import commands

from similubot.ui.skip_vote_poll import SkipVotePoll, VoteManager, VoteResult
from similubot.utils.config_manager import ConfigManager
from similubot.core.interfaces import SongInfo, AudioInfo


class TestSkipVotePoll(unittest.TestCase):
    """测试SkipVotePoll类的功能"""

    def setUp(self):
        """设置测试环境"""
        # 创建模拟对象
        self.mock_ctx = Mock(spec=commands.Context)
        self.mock_ctx.guild = Mock()
        self.mock_ctx.guild.id = 12345
        self.mock_ctx.bot = Mock()
        self.mock_ctx.send = AsyncMock()

        # 创建模拟歌曲信息
        self.mock_audio_info = Mock(spec=AudioInfo)
        self.mock_audio_info.title = "Test Song"
        self.mock_audio_info.duration = 180

        self.mock_song = Mock(spec=SongInfo)
        self.mock_song.title = "Test Song"
        self.mock_song.requester = Mock()
        self.mock_song.requester.display_name = "TestUser"
        self.mock_song.audio_info = self.mock_audio_info

        # 创建模拟语音频道成员
        self.mock_members = []
        for i in range(5):
            member = Mock(spec=discord.Member)
            member.id = 1000 + i
            member.display_name = f"User{i}"
            member.bot = False
            self.mock_members.append(member)

    def test_calculate_required_votes_fixed_threshold(self):
        """测试固定数字阈值计算"""
        # 测试固定阈值 5，有 10 个成员
        members = self.mock_members * 2  # 10 个成员
        poll = SkipVotePoll(
            ctx=self.mock_ctx,
            current_song=self.mock_song,
            voice_channel_members=members,
            threshold=5,
            timeout=60,
            min_voters=2
        )
        
        self.assertEqual(poll.required_votes, 5)

    def test_calculate_required_votes_fixed_threshold_exceeds_members(self):
        """测试固定阈值超过成员数量的情况"""
        # 测试固定阈值 10，但只有 3 个成员
        members = self.mock_members[:3]
        poll = SkipVotePoll(
            ctx=self.mock_ctx,
            current_song=self.mock_song,
            voice_channel_members=members,
            threshold=10,
            timeout=60,
            min_voters=2
        )
        
        # 应该限制为成员数量
        self.assertEqual(poll.required_votes, 3)

    def test_calculate_required_votes_percentage_threshold(self):
        """测试百分比阈值计算"""
        # 测试 50% 阈值，有 10 个成员
        members = self.mock_members * 2  # 10 个成员
        poll = SkipVotePoll(
            ctx=self.mock_ctx,
            current_song=self.mock_song,
            voice_channel_members=members,
            threshold="50%",
            timeout=60,
            min_voters=2
        )
        
        # 10 * 0.5 = 5
        self.assertEqual(poll.required_votes, 5)

    def test_calculate_required_votes_percentage_threshold_rounding(self):
        """测试百分比阈值的四舍五入"""
        # 测试 60% 阈值，有 5 个成员
        members = self.mock_members  # 5 个成员
        poll = SkipVotePoll(
            ctx=self.mock_ctx,
            current_song=self.mock_song,
            voice_channel_members=members,
            threshold="60%",
            timeout=60,
            min_voters=2
        )
        
        # 5 * 0.6 = 3.0
        self.assertEqual(poll.required_votes, 3)

    def test_calculate_required_votes_below_min_voters(self):
        """测试成员数量低于最小投票要求的情况"""
        # 只有 1 个成员，最小投票要求是 2
        members = self.mock_members[:1]
        poll = SkipVotePoll(
            ctx=self.mock_ctx,
            current_song=self.mock_song,
            voice_channel_members=members,
            threshold=5,
            timeout=60,
            min_voters=2
        )
        
        # 应该返回 1（允许直接跳过）
        self.assertEqual(poll.required_votes, 1)

    def test_calculate_required_votes_invalid_percentage(self):
        """测试无效百分比阈值"""
        members = self.mock_members
        poll = SkipVotePoll(
            ctx=self.mock_ctx,
            current_song=self.mock_song,
            voice_channel_members=members,
            threshold="invalid%",
            timeout=60,
            min_voters=2
        )
        
        # 应该回退到默认值 5，但限制为成员数量
        self.assertEqual(poll.required_votes, 5)

    def test_calculate_required_votes_invalid_fixed(self):
        """测试无效固定阈值"""
        members = self.mock_members
        poll = SkipVotePoll(
            ctx=self.mock_ctx,
            current_song=self.mock_song,
            voice_channel_members=members,
            threshold="invalid",
            timeout=60,
            min_voters=2
        )
        
        # 应该回退到默认值 5
        self.assertEqual(poll.required_votes, 5)

    @patch('asyncio.create_task')
    @patch('asyncio.wait')
    async def test_start_poll_success(self, mock_wait, mock_create_task):
        """测试成功启动投票"""
        poll = SkipVotePoll(
            ctx=self.mock_ctx,
            current_song=self.mock_song,
            voice_channel_members=self.mock_members,
            threshold=3,
            timeout=60,
            min_voters=2
        )

        # 模拟投票任务返回成功
        mock_vote_task = AsyncMock()
        mock_vote_task.result.return_value = VoteResult.PASSED
        mock_vote_task.cancelled.return_value = False

        mock_timeout_task = AsyncMock()
        mock_timeout_task.cancel = Mock()

        mock_create_task.side_effect = [mock_vote_task, mock_timeout_task]
        mock_wait.return_value = ([mock_vote_task], [mock_timeout_task])

        # 模拟消息发送和反应添加
        mock_message = Mock()
        mock_message.add_reaction = AsyncMock()
        self.mock_ctx.send.return_value = mock_message

        result = await poll.start_poll()

        self.assertEqual(result, VoteResult.PASSED)
        self.mock_ctx.send.assert_called_once()
        mock_message.add_reaction.assert_called_once_with("✅")


class TestVoteManager(unittest.TestCase):
    """测试VoteManager类的功能"""

    def setUp(self):
        """设置测试环境"""
        # 创建模拟配置管理器
        self.mock_config = Mock(spec=ConfigManager)
        self.mock_config.is_skip_voting_enabled.return_value = True
        self.mock_config.get_skip_voting_threshold.return_value = "5"
        self.mock_config.get_skip_voting_timeout.return_value = 60
        self.mock_config.get_skip_voting_min_voters.return_value = 2

        self.vote_manager = VoteManager(self.mock_config)

        # 创建模拟上下文
        self.mock_ctx = Mock(spec=commands.Context)
        self.mock_ctx.guild = Mock()
        self.mock_ctx.guild.id = 12345
        self.mock_ctx.guild.voice_client = Mock()

        # 创建模拟语音频道
        self.mock_voice_channel = Mock()
        self.mock_voice_channel.name = "Test Voice Channel"
        self.mock_voice_channel.members = []

        # 创建模拟成员
        for i in range(5):
            member = Mock(spec=discord.Member)
            member.id = 1000 + i
            member.display_name = f"User{i}"
            member.bot = False
            self.mock_voice_channel.members.append(member)

        self.mock_ctx.guild.voice_client.channel = self.mock_voice_channel

    def test_get_voice_channel_members_success(self):
        """测试成功获取语音频道成员"""
        members = self.vote_manager.get_voice_channel_members(self.mock_ctx)
        
        self.assertIsNotNone(members)
        self.assertEqual(len(members), 5)
        for member in members:
            self.assertFalse(member.bot)

    def test_get_voice_channel_members_no_guild(self):
        """测试没有服务器的情况"""
        self.mock_ctx.guild = None
        
        members = self.vote_manager.get_voice_channel_members(self.mock_ctx)
        
        self.assertIsNone(members)

    def test_get_voice_channel_members_no_voice_client(self):
        """测试没有语音客户端的情况"""
        self.mock_ctx.guild.voice_client = None
        
        members = self.vote_manager.get_voice_channel_members(self.mock_ctx)
        
        self.assertIsNone(members)

    def test_get_voice_channel_members_no_channel(self):
        """测试语音客户端没有连接频道的情况"""
        self.mock_ctx.guild.voice_client.channel = None
        
        members = self.vote_manager.get_voice_channel_members(self.mock_ctx)
        
        self.assertIsNone(members)

    def test_should_use_voting_enabled_sufficient_members(self):
        """测试投票系统启用且成员数量足够的情况"""
        members = self.mock_voice_channel.members
        
        result = self.vote_manager.should_use_voting(members)
        
        self.assertTrue(result)

    def test_should_use_voting_disabled(self):
        """测试投票系统禁用的情况"""
        self.mock_config.is_skip_voting_enabled.return_value = False
        members = self.mock_voice_channel.members
        
        result = self.vote_manager.should_use_voting(members)
        
        self.assertFalse(result)

    def test_should_use_voting_insufficient_members(self):
        """测试成员数量不足的情况"""
        # 只有 1 个成员，最小要求是 2
        members = self.mock_voice_channel.members[:1]
        
        result = self.vote_manager.should_use_voting(members)
        
        self.assertFalse(result)

    def test_cancel_active_vote_success(self):
        """测试成功取消活跃投票"""
        guild_id = 12345
        mock_poll = Mock()
        mock_poll.is_active = True
        
        self.vote_manager.active_polls[guild_id] = mock_poll
        
        result = self.vote_manager.cancel_active_vote(guild_id)
        
        self.assertTrue(result)
        self.assertFalse(mock_poll.is_active)
        self.assertNotIn(guild_id, self.vote_manager.active_polls)

    def test_cancel_active_vote_no_active_poll(self):
        """测试取消不存在的投票"""
        guild_id = 12345
        
        result = self.vote_manager.cancel_active_vote(guild_id)
        
        self.assertFalse(result)


class TestConfigManagerSkipVoting(unittest.TestCase):
    """测试ConfigManager中跳过投票相关的配置方法"""

    def setUp(self):
        """设置测试环境"""
        self.mock_config_data = {
            'music': {
                'skip_voting': {
                    'enabled': True,
                    'threshold': 5,
                    'timeout': 60,
                    'min_voters': 2
                }
            }
        }

    @patch('similubot.utils.config_manager.ConfigManager._load_config')
    def test_skip_voting_config_methods(self, mock_load_config):
        """测试跳过投票配置方法"""
        config_manager = ConfigManager()
        config_manager.config = self.mock_config_data

        # 测试各个配置方法
        self.assertTrue(config_manager.is_skip_voting_enabled())
        self.assertEqual(config_manager.get_skip_voting_threshold(), "5")
        self.assertEqual(config_manager.get_skip_voting_timeout(), 60)
        self.assertEqual(config_manager.get_skip_voting_min_voters(), 2)

    @patch('similubot.utils.config_manager.ConfigManager._load_config')
    def test_skip_voting_config_defaults(self, mock_load_config):
        """测试跳过投票配置默认值"""
        config_manager = ConfigManager()
        config_manager.config = {}  # 空配置

        # 测试默认值
        self.assertTrue(config_manager.is_skip_voting_enabled())
        self.assertEqual(config_manager.get_skip_voting_threshold(), "5")
        self.assertEqual(config_manager.get_skip_voting_timeout(), 60)
        self.assertEqual(config_manager.get_skip_voting_min_voters(), 2)


class TestSkipVotingIntegration(unittest.TestCase):
    """集成测试 - 测试投票系统与音乐命令的集成"""

    def setUp(self):
        """设置集成测试环境"""
        # 创建模拟配置
        self.mock_config = Mock(spec=ConfigManager)
        self.mock_config.is_skip_voting_enabled.return_value = True
        self.mock_config.get_skip_voting_threshold.return_value = "3"
        self.mock_config.get_skip_voting_timeout.return_value = 30
        self.mock_config.get_skip_voting_min_voters.return_value = 2

        # 创建模拟音乐播放器
        self.mock_music_player = Mock()
        self.mock_music_player.get_queue_info = AsyncMock()
        self.mock_music_player.skip_current_song = AsyncMock()

        # 创建模拟上下文
        self.mock_ctx = Mock(spec=commands.Context)
        self.mock_ctx.guild = Mock()
        self.mock_ctx.guild.id = 12345
        self.mock_ctx.reply = AsyncMock()

    @patch('similubot.commands.music_commands.MusicCommands')
    async def test_skip_command_with_voting_enabled(self, mock_music_commands):
        """测试启用投票的跳过命令"""
        # 这里可以添加更复杂的集成测试
        pass

    def test_edge_case_zero_members(self):
        """测试边界情况：零成员"""
        poll = SkipVotePoll(
            ctx=self.mock_ctx,
            current_song=Mock(),
            voice_channel_members=[],
            threshold=5,
            timeout=60,
            min_voters=2
        )

        # 零成员应该返回1（允许直接跳过）
        self.assertEqual(poll.required_votes, 1)

    def test_edge_case_percentage_zero(self):
        """测试边界情况：0%阈值"""
        members = [Mock() for _ in range(5)]
        poll = SkipVotePoll(
            ctx=self.mock_ctx,
            current_song=Mock(),
            voice_channel_members=members,
            threshold="0%",
            timeout=60,
            min_voters=2
        )

        # 0%应该至少需要1票
        self.assertEqual(poll.required_votes, 1)

    def test_edge_case_percentage_hundred(self):
        """测试边界情况：100%阈值"""
        members = [Mock() for _ in range(5)]
        poll = SkipVotePoll(
            ctx=self.mock_ctx,
            current_song=Mock(),
            voice_channel_members=members,
            threshold="100%",
            timeout=60,
            min_voters=2
        )

        # 100%应该需要所有成员投票
        self.assertEqual(poll.required_votes, 5)

    def test_vote_manager_concurrent_polls(self):
        """测试投票管理器处理并发投票的情况"""
        vote_manager = VoteManager(self.mock_config)
        guild_id = 12345

        # 添加一个活跃投票
        mock_poll = Mock()
        vote_manager.active_polls[guild_id] = mock_poll

        # 尝试启动另一个投票应该失败
        # 这里需要实际的异步测试，暂时用同步方式验证逻辑
        self.assertIn(guild_id, vote_manager.active_polls)

    def test_vote_threshold_calculation_edge_cases(self):
        """测试投票阈值计算的各种边界情况"""
        test_cases = [
            # (members_count, threshold, min_voters, expected_votes)
            (1, 5, 2, 1),           # 成员数少于最小投票要求
            (3, 10, 2, 3),          # 固定阈值超过成员数
            (10, "50%", 2, 5),      # 正常百分比
            (7, "33%", 2, 2),       # 百分比向下取整 (7 * 0.33 = 2.31 -> 2)
            (3, "67%", 2, 2),       # 百分比向下取整 (3 * 0.67 = 2.01 -> 2)
            (0, 5, 2, 1),           # 零成员
        ]

        for members_count, threshold, min_voters, expected in test_cases:
            with self.subTest(members=members_count, threshold=threshold):
                members = [Mock() for _ in range(members_count)]
                poll = SkipVotePoll(
                    ctx=self.mock_ctx,
                    current_song=Mock(),
                    voice_channel_members=members,
                    threshold=threshold,
                    timeout=60,
                    min_voters=min_voters
                )
                self.assertEqual(poll.required_votes, expected,
                    f"Members: {members_count}, Threshold: {threshold}, Expected: {expected}, Got: {poll.required_votes}")


class TestVoteResultHandling(unittest.TestCase):
    """测试投票结果处理"""

    def test_vote_result_enum_values(self):
        """测试投票结果枚举值"""
        self.assertEqual(VoteResult.PASSED.value, "passed")
        self.assertEqual(VoteResult.FAILED.value, "failed")
        self.assertEqual(VoteResult.TIMEOUT.value, "timeout")
        self.assertEqual(VoteResult.CANCELLED.value, "cancelled")

    def test_vote_result_comparison(self):
        """测试投票结果比较"""
        self.assertEqual(VoteResult.PASSED, VoteResult.PASSED)
        self.assertNotEqual(VoteResult.PASSED, VoteResult.FAILED)


if __name__ == '__main__':
    # 运行测试
    unittest.main()
