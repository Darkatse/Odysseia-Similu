"""
App Commands集成示例

展示如何将新的app_commands模块集成到现有的机器人中
"""

import logging
from typing import Any
import discord
from discord.ext import commands

from .core import CommandRegistry, ServiceProvider
from .ui import EmbedBuilder, MessageVisibility, MessageType


class AppCommandsIntegration:
    """
    App Commands集成器

    负责将新的slash commands集成到现有的Discord机器人中
    """

    def __init__(self, bot: commands.Bot, config: Any, music_player: Any):
        """
        初始化集成器

        Args:
            bot: Discord机器人实例
            config: 配置管理器
            music_player: 音乐播放器实例
        """
        self.bot = bot
        self.config = config
        self.music_player = music_player
        self.logger = logging.getLogger("similubot.app_commands.integration")

        # 初始化服务提供者
        self.service_provider = ServiceProvider(config, music_player)

        # 初始化命令注册器
        self.command_registry = CommandRegistry(bot, self.service_provider)

        # 初始化UI组件
        self.message_visibility = MessageVisibility()

        self.logger.info("App Commands集成器已初始化")

    async def setup(self) -> None:
        """设置App Commands"""
        try:
            self.logger.info("开始设置App Commands...")

            # 注册音乐命令
            self.command_registry.register_music_commands()

            # 注册通用命令
            self.command_registry.register_general_commands()

            # 注册随机抽卡命令
            self.command_registry.register_card_draw_commands()

            # 设置事件处理器
            self._setup_event_handlers()

            self.logger.info("App Commands设置完成")

        except Exception as e:
            self.logger.error(f"设置App Commands失败: {e}", exc_info=True)
            raise

    async def sync_commands(self, guild_id: int = None) -> None:
        """
        同步命令到Discord

        Args:
            guild_id: 可选的服务器ID，如果为None则全局同步
        """
        try:
            if guild_id:
                guild = self.bot.get_guild(guild_id)
                if guild:
                    await self.command_registry.sync_commands(guild)
                    self.logger.info(f"已同步命令到服务器: {guild.name}")
                else:
                    self.logger.error(f"找不到服务器: {guild_id}")
            else:
                await self.command_registry.sync_commands()
                self.logger.info("已全局同步命令")

        except Exception as e:
            self.logger.error(f"同步命令失败: {e}", exc_info=True)
            raise

    def _setup_event_handlers(self) -> None:
        """设置事件处理器"""

        @self.bot.event
        async def on_app_command_error(interaction: discord.Interaction, error: Exception):
            """处理App Command错误"""
            self.logger.error(
                f"App Command错误 - 用户: {interaction.user.display_name}, "
                f"命令: {interaction.command.name if interaction.command else 'Unknown'}, "
                f"错误: {error}",
                exc_info=True
            )

            # 发送用户友好的错误消息
            embed = EmbedBuilder.create_error_embed(
                "命令执行错误",
                "命令执行时发生错误，请稍后重试。"
            )

            await self.message_visibility.send_message(
                interaction,
                embed,
                MessageType.ERROR,
                context={'error_type': 'system'}
            )

    async def cleanup(self) -> None:
        """清理资源"""
        try:
            self.command_registry.unregister_all()
            self.logger.info("App Commands已清理")

        except Exception as e:
            self.logger.error(f"清理App Commands失败: {e}", exc_info=True)


# 使用示例
async def setup_app_commands(bot: commands.Bot, config: Any, music_player: Any) -> AppCommandsIntegration:
    """
    设置App Commands的便捷函数

    Args:
        bot: Discord机器人实例
        config: 配置管理器
        music_player: 音乐播放器实例

    Returns:
        集成器实例
    """
    integration = AppCommandsIntegration(bot, config, music_player)
    await integration.setup()
    return integration