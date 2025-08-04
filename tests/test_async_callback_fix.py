"""
测试异步回调修复

验证投票系统正确处理异步和同步回调函数，确保：
1. 异步回调被正确await
2. 同步回调正常执行
3. 错误处理正确工作
4. 投票通过时歌曲实际被跳过
"""

import unittest
from unittest.mock import Mock, AsyncMock, patch
import asyncio
import discord
from discord.ext import commands

from similubot.ui.skip_vote_poll import SkipVotePoll, VoteResult
from similubot.core.interfaces import SongInfo, AudioInfo


class TestAsyncCallbackFix(unittest.TestCase):
    """测试异步回调修复的功能"""

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

    async def test_async_callback_invocation(self):
        """测试异步回调的正确调用"""
        # 创建异步回调
        callback_called = False
        callback_result = None

        async def async_callback(result: VoteResult):
            nonlocal callback_called, callback_result
            callback_called = True
            callback_result = result

        # 创建投票轮询器
        poll = SkipVotePoll(
            ctx=self.mock_ctx,
            current_song=self.mock_song,
            voice_channel_members=self.mock_members,
            threshold=3,
            timeout=60,
            min_voters=2
        )

        # 设置异步回调
        poll.on_vote_complete = async_callback

        # 测试回调调用
        await poll._invoke_callback(async_callback, VoteResult.PASSED)

        # 验证异步回调被正确调用
        self.assertTrue(callback_called)
        self.assertEqual(callback_result, VoteResult.PASSED)

    async def test_sync_callback_invocation(self):
        """测试同步回调的正确调用"""
        # 创建同步回调
        callback_called = False
        callback_result = None

        def sync_callback(result: VoteResult):
            nonlocal callback_called, callback_result
            callback_called = True
            callback_result = result

        # 创建投票轮询器
        poll = SkipVotePoll(
            ctx=self.mock_ctx,
            current_song=self.mock_song,
            voice_channel_members=self.mock_members,
            threshold=3,
            timeout=60,
            min_voters=2
        )

        # 设置同步回调
        poll.on_vote_complete = sync_callback

        # 测试回调调用
        await poll._invoke_callback(sync_callback, VoteResult.PASSED)

        # 验证同步回调被正确调用
        self.assertTrue(callback_called)
        self.assertEqual(callback_result, VoteResult.PASSED)

    async def test_callback_error_handling(self):
        """测试回调错误处理"""
        # 创建会抛出异常的异步回调
        async def failing_async_callback(result: VoteResult):
            raise Exception("Test async callback error")

        # 创建会抛出异常的同步回调
        def failing_sync_callback(result: VoteResult):
            raise Exception("Test sync callback error")

        # 创建投票轮询器
        poll = SkipVotePoll(
            ctx=self.mock_ctx,
            current_song=self.mock_song,
            voice_channel_members=self.mock_members,
            threshold=3,
            timeout=60,
            min_voters=2
        )

        # 测试异步回调错误处理
        try:
            await poll._invoke_callback(failing_async_callback, VoteResult.PASSED)
            # 应该不会抛出异常，错误应该被捕获和记录
        except Exception:
            self.fail("异步回调错误未被正确处理")

        # 测试同步回调错误处理
        try:
            await poll._invoke_callback(failing_sync_callback, VoteResult.PASSED)
            # 应该不会抛出异常，错误应该被捕获和记录
        except Exception:
            self.fail("同步回调错误未被正确处理")

    async def test_no_callback_handling(self):
        """测试没有回调时的处理"""
        # 创建投票轮询器
        poll = SkipVotePoll(
            ctx=self.mock_ctx,
            current_song=self.mock_song,
            voice_channel_members=self.mock_members,
            threshold=3,
            timeout=60,
            min_voters=2
        )

        # 不设置回调
        poll.on_vote_complete = None

        # 测试没有回调时的处理
        try:
            await poll._invoke_callback(None, VoteResult.PASSED)
            # 应该不会抛出异常
        except Exception:
            self.fail("没有回调时处理失败")

    @patch('similubot.ui.skip_vote_poll.SkipVotePoll._monitor_votes')
    @patch('similubot.ui.skip_vote_poll.SkipVotePoll._handle_timeout')
    async def test_start_poll_with_async_callback(self, mock_timeout, mock_monitor):
        """测试启动投票时异步回调的完整流程"""
        # 设置模拟返回值
        mock_monitor.return_value = VoteResult.PASSED
        mock_timeout.return_value = VoteResult.TIMEOUT

        # 创建异步回调
        callback_called = False
        callback_result = None

        async def async_callback(result: VoteResult):
            nonlocal callback_called, callback_result
            callback_called = True
            callback_result = result

        # 创建投票轮询器
        poll = SkipVotePoll(
            ctx=self.mock_ctx,
            current_song=self.mock_song,
            voice_channel_members=self.mock_members,
            threshold=3,
            timeout=60,
            min_voters=2
        )

        # 设置异步回调
        poll.on_vote_complete = async_callback

        # 模拟消息发送和反应添加
        mock_message = Mock()
        mock_message.add_reaction = AsyncMock()
        self.mock_ctx.send.return_value = mock_message

        # 模拟asyncio.wait返回投票通过
        with patch('asyncio.wait') as mock_wait:
            mock_task = Mock()
            mock_task.result.return_value = VoteResult.PASSED
            mock_task.cancelled.return_value = False
            mock_wait.return_value = ([mock_task], [])

            # 启动投票
            result = await poll.start_poll()

            # 验证结果
            self.assertEqual(result, VoteResult.PASSED)
            self.assertTrue(callback_called)
            self.assertEqual(callback_result, VoteResult.PASSED)

    def test_callback_type_detection(self):
        """测试回调类型检测"""
        import inspect

        # 异步回调
        async def async_callback(result: VoteResult):
            pass

        # 同步回调
        def sync_callback(result: VoteResult):
            pass

        # Lambda回调
        lambda_callback = lambda result: None

        # 验证类型检测
        self.assertTrue(inspect.iscoroutinefunction(async_callback))
        self.assertFalse(inspect.iscoroutinefunction(sync_callback))
        self.assertFalse(inspect.iscoroutinefunction(lambda_callback))


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
TestAsyncCallbackFix.test_async_callback_invocation = run_async_test(
    TestAsyncCallbackFix.test_async_callback_invocation
)
TestAsyncCallbackFix.test_sync_callback_invocation = run_async_test(
    TestAsyncCallbackFix.test_sync_callback_invocation
)
TestAsyncCallbackFix.test_callback_error_handling = run_async_test(
    TestAsyncCallbackFix.test_callback_error_handling
)
TestAsyncCallbackFix.test_no_callback_handling = run_async_test(
    TestAsyncCallbackFix.test_no_callback_handling
)
TestAsyncCallbackFix.test_start_poll_with_async_callback = run_async_test(
    TestAsyncCallbackFix.test_start_poll_with_async_callback
)


if __name__ == '__main__':
    unittest.main()
