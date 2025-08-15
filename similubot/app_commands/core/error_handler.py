"""
App Commands错误处理系统

提供统一的错误处理和恢复机制：
- 分类错误处理
- 用户友好的错误消息
- 错误恢复策略
- 错误统计和监控
"""

import logging
import traceback
from enum import Enum
from typing import Optional, Dict, Any, Callable
import discord
from discord import app_commands

from .logging_config import AppCommandsLogger
from ..ui import EmbedBuilder, MessageVisibility, MessageType


class ErrorCategory(Enum):
    """错误分类枚举"""
    USER_ERROR = "user_error"          # 用户输入错误
    PERMISSION_ERROR = "permission"    # 权限错误
    SYSTEM_ERROR = "system"           # 系统错误
    NETWORK_ERROR = "network"         # 网络错误
    TIMEOUT_ERROR = "timeout"         # 超时错误
    RATE_LIMIT_ERROR = "rate_limit"   # 频率限制错误
    MUSIC_ERROR = "music"             # 音乐相关错误
    QUEUE_ERROR = "queue"             # 队列相关错误


class AppCommandError(Exception):
    """App Command自定义异常基类"""

    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.SYSTEM_ERROR,
        user_message: Optional[str] = None,
        recoverable: bool = False,
        **context
    ):
        """
        初始化自定义异常

        Args:
            message: 错误消息
            category: 错误分类
            user_message: 用户友好的错误消息
            recoverable: 是否可恢复
            **context: 额外的上下文信息
        """
        super().__init__(message)
        self.category = category
        self.user_message = user_message or message
        self.recoverable = recoverable
        self.context = context


class MusicCommandError(AppCommandError):
    """音乐命令错误"""

    def __init__(self, message: str, user_message: str = None, **context):
        super().__init__(
            message,
            ErrorCategory.MUSIC_ERROR,
            user_message,
            recoverable=True,
            **context
        )


class QueueFairnessError(AppCommandError):
    """队列公平性错误"""

    def __init__(self, message: str, user_message: str = None, **context):
        super().__init__(
            message,
            ErrorCategory.QUEUE_ERROR,
            user_message,
            recoverable=True,
            **context
        )


class NetworkTimeoutError(AppCommandError):
    """网络超时错误"""

    def __init__(self, message: str, user_message: str = None, **context):
        super().__init__(
            message,
            ErrorCategory.TIMEOUT_ERROR,
            user_message or "网络请求超时，请稍后重试",
            recoverable=True,
            **context
        )


class AppCommandsErrorHandler:
    """
    App Commands错误处理器

    提供统一的错误处理和用户反馈机制
    """

    def __init__(self):
        """初始化错误处理器"""
        self.logger = AppCommandsLogger("error_handler")
        self.message_visibility = MessageVisibility()

        # 错误统计
        self._error_stats: Dict[str, int] = {}

        # 错误处理策略
        self._error_handlers: Dict[ErrorCategory, Callable] = {
            ErrorCategory.USER_ERROR: self._handle_user_error,
            ErrorCategory.PERMISSION_ERROR: self._handle_permission_error,
            ErrorCategory.SYSTEM_ERROR: self._handle_system_error,
            ErrorCategory.NETWORK_ERROR: self._handle_network_error,
            ErrorCategory.TIMEOUT_ERROR: self._handle_timeout_error,
            ErrorCategory.RATE_LIMIT_ERROR: self._handle_rate_limit_error,
            ErrorCategory.MUSIC_ERROR: self._handle_music_error,
            ErrorCategory.QUEUE_ERROR: self._handle_queue_error,
        }

    async def handle_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        command_name: Optional[str] = None
    ) -> bool:
        """
        处理错误

        Args:
            interaction: Discord交互对象
            error: 异常对象
            command_name: 命令名称

        Returns:
            True if error was handled, False otherwise
        """
        try:
            # 记录错误统计
            error_type = type(error).__name__
            self._error_stats[error_type] = self._error_stats.get(error_type, 0) + 1

            # 确定错误分类
            category = self._categorize_error(error)

            # 记录错误
            self.logger.log_command_error(
                interaction,
                command_name or "unknown",
                error,
                error_category=category.value
            )

            # 获取错误处理器
            handler = self._error_handlers.get(category, self._handle_unknown_error)

            # 处理错误
            await handler(interaction, error, command_name)

            return True

        except Exception as e:
            # 错误处理器本身出错
            self.logger.error(f"错误处理器失败: {e}", error=e)
            await self._handle_fallback_error(interaction, error)
            return False

    def _categorize_error(self, error: Exception) -> ErrorCategory:
        """
        分类错误

        Args:
            error: 异常对象

        Returns:
            错误分类
        """
        # 自定义异常
        if isinstance(error, AppCommandError):
            return error.category

        # Discord异常
        if isinstance(error, discord.Forbidden):
            return ErrorCategory.PERMISSION_ERROR
        elif isinstance(error, discord.HTTPException):
            if "rate limited" in str(error).lower():
                return ErrorCategory.RATE_LIMIT_ERROR
            else:
                return ErrorCategory.NETWORK_ERROR
        elif isinstance(error, discord.NotFound):
            return ErrorCategory.USER_ERROR

        # App Commands异常
        if isinstance(error, app_commands.CommandOnCooldown):
            return ErrorCategory.RATE_LIMIT_ERROR
        elif isinstance(error, app_commands.MissingPermissions):
            return ErrorCategory.PERMISSION_ERROR
        elif isinstance(error, app_commands.BotMissingPermissions):
            return ErrorCategory.PERMISSION_ERROR

        # 网络相关异常
        if "timeout" in str(error).lower() or "timed out" in str(error).lower():
            return ErrorCategory.TIMEOUT_ERROR

        # 音乐相关异常
        if any(keyword in str(error).lower() for keyword in ["audio", "music", "youtube", "netease"]):
            return ErrorCategory.MUSIC_ERROR

        # 队列相关异常
        if any(keyword in str(error).lower() for keyword in ["queue", "fairness", "duplicate"]):
            return ErrorCategory.QUEUE_ERROR

        # 默认为系统错误
        return ErrorCategory.SYSTEM_ERROR

    async def _handle_user_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        command_name: Optional[str] = None
    ) -> None:
        """处理用户错误"""
        embed = EmbedBuilder.create_error_embed(
            "输入错误",
            "请检查您的输入并重试。"
        )

        if isinstance(error, AppCommandError) and error.user_message:
            embed.description = error.user_message

        await self.message_visibility.send_message(
            interaction,
            embed,
            MessageType.ERROR,
            context={'error_type': 'user_input'}
        )

    async def _handle_permission_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        command_name: Optional[str] = None
    ) -> None:
        """处理权限错误"""
        embed = EmbedBuilder.create_error_embed(
            "权限不足",
            "您没有执行此命令的权限，或机器人缺少必要的权限。"
        )

        if isinstance(error, discord.Forbidden):
            embed.add_field(
                name="💡 解决方案",
                value="请联系服务器管理员检查机器人权限设置。",
                inline=False
            )

        await self.message_visibility.send_message(
            interaction,
            embed,
            MessageType.ERROR,
            context={'error_type': 'permission'}
        )

    async def _handle_system_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        command_name: Optional[str] = None
    ) -> None:
        """处理系统错误"""
        embed = EmbedBuilder.create_error_embed(
            "系统错误",
            "系统发生内部错误，请稍后重试。"
        )

        embed.add_field(
            name="🔧 如果问题持续存在",
            value="请联系机器人管理员并提供错误发生的时间。",
            inline=False
        )

        await self.message_visibility.send_message(
            interaction,
            embed,
            MessageType.ERROR,
            context={'error_type': 'system', 'show_to_all': False}
        )

    async def _handle_network_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        command_name: Optional[str] = None
    ) -> None:
        """处理网络错误"""
        embed = EmbedBuilder.create_error_embed(
            "网络错误",
            "网络连接出现问题，请稍后重试。"
        )

        embed.add_field(
            name="🌐 可能的原因",
            value="• 网络连接不稳定\n• 外部服务暂时不可用\n• 服务器负载过高",
            inline=False
        )

        await self.message_visibility.send_message(
            interaction,
            embed,
            MessageType.ERROR,
            context={'error_type': 'network'}
        )

    async def _handle_timeout_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        command_name: Optional[str] = None
    ) -> None:
        """处理超时错误"""
        embed = EmbedBuilder.create_error_embed(
            "请求超时",
            "操作超时，请稍后重试。"
        )

        embed.add_field(
            name="⏱️ 建议",
            value="• 检查网络连接\n• 稍等片刻后重试\n• 尝试使用更简单的搜索关键词",
            inline=False
        )

        await self.message_visibility.send_message(
            interaction,
            embed,
            MessageType.ERROR,
            context={'error_type': 'timeout'}
        )

    async def _handle_rate_limit_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        command_name: Optional[str] = None
    ) -> None:
        """处理频率限制错误"""
        embed = EmbedBuilder.create_error_embed(
            "操作过于频繁",
            "您的操作过于频繁，请稍后重试。"
        )

        if isinstance(error, app_commands.CommandOnCooldown):
            retry_after = int(error.retry_after)
            embed.add_field(
                name="⏰ 冷却时间",
                value=f"请等待 {retry_after} 秒后重试",
                inline=False
            )

        await self.message_visibility.send_message(
            interaction,
            embed,
            MessageType.ERROR,
            context={'error_type': 'rate_limit'}
        )

    async def _handle_music_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        command_name: Optional[str] = None
    ) -> None:
        """处理音乐相关错误"""
        embed = EmbedBuilder.create_error_embed(
            "音乐播放错误",
            "音乐功能出现问题。"
        )

        if isinstance(error, AppCommandError) and error.user_message:
            embed.description = error.user_message
        else:
            embed.description = "音乐播放或搜索时发生错误，请稍后重试。"

        embed.add_field(
            name="🎵 可能的解决方案",
            value="• 检查您是否在语音频道中\n• 尝试使用不同的搜索关键词\n• 确认链接是否有效",
            inline=False
        )

        await self.message_visibility.send_message(
            interaction,
            embed,
            MessageType.ERROR,
            context={'error_type': 'music'}
        )

    async def _handle_queue_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        command_name: Optional[str] = None
    ) -> None:
        """处理队列相关错误"""
        embed = EmbedBuilder.create_error_embed(
            "队列操作错误",
            "队列操作时发生错误。"
        )

        if isinstance(error, AppCommandError) and error.user_message:
            embed.description = error.user_message

        # 特殊处理队列公平性错误
        if isinstance(error, QueueFairnessError):
            embed.title = "⚖️ 队列公平性限制"
            embed.color = discord.Color.orange()
            embed.add_field(
                name="📋 队列规则",
                value="为了保证所有用户的公平使用，每位用户同时只能有一首歌曲在队列中等待播放。",
                inline=False
            )

        await self.message_visibility.send_message(
            interaction,
            embed,
            MessageType.ERROR,
            context={'error_type': 'queue_fairness' if isinstance(error, QueueFairnessError) else 'queue'}
        )

    async def _handle_unknown_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        command_name: Optional[str] = None
    ) -> None:
        """处理未知错误"""
        embed = EmbedBuilder.create_error_embed(
            "未知错误",
            "发生了未预期的错误，请稍后重试。"
        )

        embed.add_field(
            name="🔍 错误信息",
            value=f"错误类型: {type(error).__name__}",
            inline=False
        )

        await self.message_visibility.send_message(
            interaction,
            embed,
            MessageType.ERROR,
            context={'error_type': 'unknown'}
        )

    async def _handle_fallback_error(
        self,
        interaction: discord.Interaction,
        original_error: Exception
    ) -> None:
        """处理回退错误（当错误处理器本身失败时）"""
        try:
            embed = discord.Embed(
                title="❌ 系统错误",
                description="系统发生严重错误，请联系管理员。",
                color=discord.Color.red()
            )

            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception:
            # 如果连回退处理都失败了，只能记录日志
            self.logger.error(f"回退错误处理失败，原始错误: {original_error}")

    def get_error_stats(self) -> Dict[str, int]:
        """
        获取错误统计

        Returns:
            错误统计字典
        """
        return self._error_stats.copy()

    def reset_error_stats(self) -> None:
        """重置错误统计"""
        self._error_stats.clear()
        self.logger.info("错误统计已重置")