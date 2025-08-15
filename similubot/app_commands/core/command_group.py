"""
Slash命令组管理

提供命令组织和管理功能：
- 命令分组
- 权限管理
- 命令路由
- 生命周期管理
"""

import logging
from typing import List, Dict, Any, Optional, Callable
import discord
from discord import app_commands
from discord.ext import commands

from .base_command import BaseSlashCommand
from .dependency_container import DependencyContainer


class SlashCommandGroup(app_commands.Group):
    """
    Slash命令组

    管理相关命令的集合，提供统一的权限检查和错误处理
    """

    def __init__(
        self,
        name: str,
        description: str,
        container: DependencyContainer,
        **kwargs
    ):
        """
        初始化命令组

        Args:
            name: 命令组名称
            description: 命令组描述
            container: 依赖注入容器
            **kwargs: 其他参数
        """
        super().__init__(name=name, description=description, **kwargs)
        self.container = container
        self.logger = logging.getLogger(f"similubot.app_commands.{name}")
        self._commands: Dict[str, BaseSlashCommand] = {}

        self.logger.debug(f"初始化命令组: {name}")

    def add_command_handler(self, command_name: str, handler: BaseSlashCommand) -> None:
        """
        添加命令处理器

        Args:
            command_name: 命令名称
            handler: 命令处理器
        """
        self._commands[command_name] = handler
        self.logger.debug(f"添加命令处理器: {command_name}")

    async def on_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        """
        处理命令组错误

        Args:
            interaction: Discord交互对象
            error: 应用命令错误
        """
        self.logger.error(
            f"命令组错误 - 组: {self.name}, 用户: {interaction.user.display_name}, "
            f"命令: {interaction.command.name if interaction.command else 'Unknown'}, "
            f"错误: {error}",
            exc_info=True
        )

        # 发送用户友好的错误消息
        embed = discord.Embed(
            title="❌ 命令执行错误",
            description="命令执行时发生错误，请稍后重试",
            color=discord.Color.red()
        )

        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            self.logger.error(f"发送错误响应失败: {e}")


class MusicCommandGroup(SlashCommandGroup):
    """
    音乐命令组

    专门用于音乐相关的Slash命令
    """

    def __init__(self, container: DependencyContainer):
        """
        初始化音乐命令组

        Args:
            container: 依赖注入容器
        """
        super().__init__(
            name="music",
            description="音乐播放和队列管理命令",
            container=container
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """
        检查交互权限

        Args:
            interaction: Discord交互对象

        Returns:
            True if check passes, False otherwise
        """
        # 检查是否在服务器中
        if not interaction.guild:
            embed = discord.Embed(
                title="❌ 错误",
                description="此命令只能在服务器中使用",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False

        # 检查音乐功能是否启用
        try:
            from similubot.utils.config_manager import ConfigManager
            config = self.container.resolve(ConfigManager)
            if not config.get('music.enabled', True):
                embed = discord.Embed(
                    title="❌ 功能不可用",
                    description="音乐功能当前不可用",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return False
        except Exception as e:
            self.logger.error(f"检查音乐功能状态失败: {e}")
            return False

        return True