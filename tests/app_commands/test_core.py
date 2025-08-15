"""
App Commands核心组件测试

测试核心基础设施的功能：
- 依赖注入容器
- 基础命令类
- 错误处理系统
- 日志记录系统
"""

import pytest
import asyncio
import logging
from unittest.mock import Mock, AsyncMock, patch
import discord
from discord.ext import commands

from similubot.app_commands.core import (
    DependencyContainer,
    ServiceProvider,
    BaseSlashCommand,
    AppCommandsLogger,
    AppCommandsErrorHandler,
    AppCommandError,
    MusicCommandError,
    QueueFairnessError,
    ErrorCategory
)
from similubot.utils.config_manager import ConfigManager


class TestDependencyContainer:
    """测试依赖注入容器"""

    def setup_method(self):
        """设置测试环境"""
        self.container = DependencyContainer()

    def test_register_singleton(self):
        """测试单例注册"""
        service = Mock()
        self.container.register_singleton(Mock, service)

        assert self.container.is_registered(Mock)
        assert self.container.resolve(Mock) is service

    def test_register_factory(self):
        """测试工厂方法注册"""
        service = Mock()
        factory = Mock(return_value=service)

        self.container.register_factory(Mock, factory)

        assert self.container.is_registered(Mock)
        result = self.container.resolve(Mock)
        assert result is service
        factory.assert_called_once()

    def test_register_transient(self):
        """测试瞬态服务注册"""
        implementation = Mock
        self.container.register_transient(Mock, implementation)

        assert self.container.is_registered(Mock)
        # 注意：这里需要实际的类，不是Mock

    def test_resolve_unregistered_service(self):
        """测试解析未注册的服务"""
        with pytest.raises(ValueError, match="服务未注册"):
            self.container.resolve(Mock)

    def test_try_resolve(self):
        """测试尝试解析服务"""
        # 未注册的服务
        result = self.container.try_resolve(Mock)
        assert result is None

        # 已注册的服务
        service = Mock()
        self.container.register_singleton(Mock, service)
        result = self.container.try_resolve(Mock)
        assert result is service

    def test_clear(self):
        """测试清空容器"""
        service = Mock()
        self.container.register_singleton(Mock, service)

        assert self.container.is_registered(Mock)

        self.container.clear()

        assert not self.container.is_registered(Mock)


class TestServiceProvider:
    """测试服务提供者"""

    def setup_method(self):
        """设置测试环境"""
        self.config = Mock(spec=ConfigManager)
        self.music_player = Mock()
        self.service_provider = ServiceProvider(self.config, self.music_player)

    def test_initialization(self):
        """测试初始化"""
        container = self.service_provider.get_container()

        # 检查核心服务是否已注册
        assert container.is_registered(ConfigManager)
        assert container.resolve(ConfigManager) is self.config

    def test_get_container(self):
        """测试获取容器"""
        container = self.service_provider.get_container()
        assert isinstance(container, DependencyContainer)


class TestBaseSlashCommand:
    """测试基础Slash命令类"""

    def setup_method(self):
        """设置测试环境"""
        self.config = Mock(spec=ConfigManager)
        self.config.get.return_value = True  # 音乐功能启用
        self.music_player = Mock()

        # 创建具体的命令实现用于测试
        class TestCommand(BaseSlashCommand):
            async def execute(self, interaction, **kwargs):
                return "test_result"

        self.command = TestCommand(self.config, self.music_player)

    def test_initialization(self):
        """测试初始化"""
        assert self.command.config is self.config
        assert self.command.music_player is self.music_player
        assert self.command.is_available()

    def test_is_available_disabled(self):
        """测试功能禁用时的可用性"""
        self.config.get.return_value = False
        command = type(self.command)(self.config, self.music_player)
        assert not command.is_available()

    @pytest.mark.asyncio
    async def test_check_prerequisites_no_guild(self):
        """测试前置条件检查 - 无服务器"""
        interaction = Mock(spec=discord.Interaction)
        interaction.guild = None
        interaction.response.send_message = AsyncMock()

        result = await self.command.check_prerequisites(interaction)

        assert not result
        interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_prerequisites_disabled(self):
        """测试前置条件检查 - 功能禁用"""
        self.config.get.return_value = False
        command = type(self.command)(self.config, self.music_player)

        interaction = Mock(spec=discord.Interaction)
        interaction.guild = Mock()
        interaction.response.send_message = AsyncMock()

        result = await command.check_prerequisites(interaction)

        assert not result
        interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_voice_channel_not_in_voice(self):
        """测试语音频道检查 - 用户不在语音频道"""
        interaction = Mock(spec=discord.Interaction)
        interaction.user.voice = None
        interaction.response.send_message = AsyncMock()

        result = await self.command.check_voice_channel(interaction)

        assert not result
        interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_voice_channel_in_voice(self):
        """测试语音频道检查 - 用户在语音频道"""
        interaction = Mock(spec=discord.Interaction)
        interaction.user.voice = Mock()
        interaction.user.voice.channel = Mock()

        result = await self.command.check_voice_channel(interaction)

        assert result

    @pytest.mark.asyncio
    async def test_send_error_response(self):
        """测试发送错误响应"""
        interaction = Mock(spec=discord.Interaction)
        interaction.response.is_done.return_value = False
        interaction.response.send_message = AsyncMock()

        await self.command.send_error_response(interaction, "测试错误")

        interaction.response.send_message.assert_called_once()
        args, kwargs = interaction.response.send_message.call_args
        assert kwargs['ephemeral'] is True
        assert "测试错误" in kwargs['embed'].description

    @pytest.mark.asyncio
    async def test_send_success_response(self):
        """测试发送成功响应"""
        interaction = Mock(spec=discord.Interaction)
        interaction.response.is_done.return_value = False
        interaction.response.send_message = AsyncMock()

        await self.command.send_success_response(interaction, "成功", "测试成功")

        interaction.response.send_message.assert_called_once()
        args, kwargs = interaction.response.send_message.call_args
        assert kwargs['ephemeral'] is False
        assert "测试成功" in kwargs['embed'].description


class TestAppCommandsErrorHandler:
    """测试错误处理器"""

    def setup_method(self):
        """设置测试环境"""
        self.error_handler = AppCommandsErrorHandler()

    def test_categorize_custom_error(self):
        """测试自定义错误分类"""
        error = MusicCommandError("音乐错误")
        category = self.error_handler._categorize_error(error)
        assert category == ErrorCategory.MUSIC_ERROR

    def test_categorize_discord_forbidden(self):
        """测试Discord权限错误分类"""
        error = discord.Forbidden(Mock(), "权限不足")
        category = self.error_handler._categorize_error(error)
        assert category == ErrorCategory.PERMISSION_ERROR

    def test_categorize_timeout_error(self):
        """测试超时错误分类"""
        error = Exception("Connection timed out")
        category = self.error_handler._categorize_error(error)
        assert category == ErrorCategory.TIMEOUT_ERROR

    def test_categorize_music_error(self):
        """测试音乐相关错误分类"""
        error = Exception("YouTube audio extraction failed")
        category = self.error_handler._categorize_error(error)
        assert category == ErrorCategory.MUSIC_ERROR

    def test_categorize_queue_error(self):
        """测试队列相关错误分类"""
        error = Exception("Queue fairness violation")
        category = self.error_handler._categorize_error(error)
        assert category == ErrorCategory.QUEUE_ERROR

    def test_categorize_unknown_error(self):
        """测试未知错误分类"""
        error = Exception("Unknown error")
        category = self.error_handler._categorize_error(error)
        assert category == ErrorCategory.SYSTEM_ERROR

    @pytest.mark.asyncio
    async def test_handle_user_error(self):
        """测试处理用户错误"""
        interaction = Mock(spec=discord.Interaction)
        interaction.response.is_done.return_value = False
        interaction.response.send_message = AsyncMock()

        error = AppCommandError("用户错误", ErrorCategory.USER_ERROR, "用户友好消息")

        await self.error_handler._handle_user_error(interaction, error)

        interaction.response.send_message.assert_called_once()
        args, kwargs = interaction.response.send_message.call_args
        assert kwargs['ephemeral'] is True

    @pytest.mark.asyncio
    async def test_handle_queue_fairness_error(self):
        """测试处理队列公平性错误"""
        interaction = Mock(spec=discord.Interaction)
        interaction.response.is_done.return_value = False
        interaction.response.send_message = AsyncMock()

        error = QueueFairnessError("队列公平性错误", "您已有歌曲在队列中")

        await self.error_handler._handle_queue_error(interaction, error)

        interaction.response.send_message.assert_called_once()
        args, kwargs = interaction.response.send_message.call_args
        embed = kwargs['embed']
        assert "队列公平性限制" in embed.title

    @pytest.mark.asyncio
    async def test_handle_error_with_stats(self):
        """测试错误处理和统计"""
        interaction = Mock(spec=discord.Interaction)
        interaction.user.display_name = "TestUser"
        interaction.response.is_done.return_value = False
        interaction.response.send_message = AsyncMock()

        error = ValueError("测试错误")

        result = await self.error_handler.handle_error(interaction, error, "test_command")

        assert result is True
        assert self.error_handler._error_stats["ValueError"] == 1

    def test_get_error_stats(self):
        """测试获取错误统计"""
        # 模拟一些错误统计
        self.error_handler._error_stats["ValueError"] = 5
        self.error_handler._error_stats["TypeError"] = 3

        stats = self.error_handler.get_error_stats()

        assert stats["ValueError"] == 5
        assert stats["TypeError"] == 3
        # 确保返回的是副本
        stats["ValueError"] = 10
        assert self.error_handler._error_stats["ValueError"] == 5

    def test_reset_error_stats(self):
        """测试重置错误统计"""
        self.error_handler._error_stats["ValueError"] = 5

        self.error_handler.reset_error_stats()

        assert len(self.error_handler._error_stats) == 0


class TestAppCommandsLogger:
    """测试日志记录器"""

    def setup_method(self):
        """设置测试环境"""
        self.logger = AppCommandsLogger("test")

    def test_initialization(self):
        """测试初始化"""
        assert self.logger.logger.name == "similubot.app_commands.test"

    def test_log_command_start(self):
        """测试记录命令开始"""
        interaction = Mock(spec=discord.Interaction)
        interaction.user.id = 12345
        interaction.user.display_name = "TestUser"
        interaction.guild.id = 67890
        interaction.guild.name = "TestGuild"
        interaction.channel.id = 11111

        with patch.object(self.logger.logger, 'info') as mock_info:
            self.logger.log_command_start(interaction, "test_command")

            mock_info.assert_called_once()
            args, kwargs = mock_info.call_args
            assert "命令开始 - test_command" in args[0]
            assert "TestUser" in args[0]

    def test_log_command_success(self):
        """测试记录命令成功"""
        interaction = Mock(spec=discord.Interaction)
        interaction.user.id = 12345
        interaction.user.display_name = "TestUser"
        interaction.guild.id = 67890

        with patch.object(self.logger.logger, 'info') as mock_info:
            self.logger.log_command_success(interaction, "test_command", 1.5)

            mock_info.assert_called_once()
            args, kwargs = mock_info.call_args
            assert "命令成功 - test_command" in args[0]
            assert "1.50s" in args[0]

    def test_log_command_error(self):
        """测试记录命令错误"""
        interaction = Mock(spec=discord.Interaction)
        interaction.user.id = 12345
        interaction.user.display_name = "TestUser"
        interaction.guild.id = 67890

        error = ValueError("测试错误")

        with patch.object(self.logger.logger, 'error') as mock_error:
            self.logger.log_command_error(interaction, "test_command", error, 2.0)

            mock_error.assert_called_once()
            args, kwargs = mock_error.call_args
            assert "命令错误 - test_command" in args[0]
            assert "ValueError" in args[0]

    def test_log_performance_warning(self):
        """测试记录性能警告"""
        with patch.object(self.logger.logger, 'warning') as mock_warning:
            self.logger.log_performance_warning("slow_operation", 6.0, 5.0)

            mock_warning.assert_called_once()
            args, kwargs = mock_warning.call_args
            assert "性能警告 - slow_operation" in args[0]
            assert "6.00s" in args[0]

    def test_log_performance_no_warning(self):
        """测试不触发性能警告"""
        with patch.object(self.logger.logger, 'warning') as mock_warning:
            self.logger.log_performance_warning("fast_operation", 3.0, 5.0)

            mock_warning.assert_not_called()


class TestCustomExceptions:
    """测试自定义异常"""

    def test_app_command_error(self):
        """测试基础App Command错误"""
        error = AppCommandError(
            "系统错误",
            ErrorCategory.SYSTEM_ERROR,
            "用户友好消息",
            recoverable=True,
            extra_info="额外信息"
        )

        assert str(error) == "系统错误"
        assert error.category == ErrorCategory.SYSTEM_ERROR
        assert error.user_message == "用户友好消息"
        assert error.recoverable is True
        assert error.context["extra_info"] == "额外信息"

    def test_music_command_error(self):
        """测试音乐命令错误"""
        error = MusicCommandError("音乐播放失败", "无法播放此歌曲")

        assert error.category == ErrorCategory.MUSIC_ERROR
        assert error.user_message == "无法播放此歌曲"
        assert error.recoverable is True

    def test_queue_fairness_error(self):
        """测试队列公平性错误"""
        error = QueueFairnessError("队列限制", "您已有歌曲在队列中")

        assert error.category == ErrorCategory.QUEUE_ERROR
        assert error.user_message == "您已有歌曲在队列中"
        assert error.recoverable is True

    def test_network_timeout_error(self):
        """测试网络超时错误"""
        error = NetworkTimeoutError("网络超时")

        assert error.category == ErrorCategory.TIMEOUT_ERROR
        assert "网络请求超时" in error.user_message
        assert error.recoverable is True