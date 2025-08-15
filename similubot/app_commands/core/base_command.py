"""
基础Slash命令类

提供所有Slash命令的通用功能：
- 统一的错误处理
- 日志记录
- 权限检查
- 消息可见性控制
"""

import logging
import traceback
from abc import ABC, abstractmethod
from typing import Optional, Any, Dict, Union
import discord
from discord import app_commands
from discord.ext import commands

from similubot.utils.config_manager import ConfigManager


class BaseSlashCommand(ABC):
    """
    所有Slash命令的基础类

    提供通用功能和标准化的命令处理流程
    """

    def __init__(self, config: ConfigManager, music_player: Any):
        """
        初始化基础命令

        Args:
            config: 配置管理器
            music_player: 音乐播放器实例
        """
        self.config = config
        self.music_player = music_player
        self.logger = logging.getLogger(f"similubot.app_commands.{self.__class__.__name__}")

        # 检查音乐功能是否启用
        self._enabled = config.get('music.enabled', True)

        self.logger.debug(f"初始化 {self.__class__.__name__}")

    def is_available(self) -> bool:
        """
        检查命令是否可用

        Returns:
            True if available, False otherwise
        """
        return self._enabled

    async def check_prerequisites(self, interaction: discord.Interaction) -> bool:
        """
        检查命令执行的前置条件

        Args:
            interaction: Discord交互对象

        Returns:
            True if prerequisites are met, False otherwise
        """
        # 检查是否在服务器中
        if not interaction.guild:
            await self.send_error_response(
                interaction,
                "此命令只能在服务器中使用",
                ephemeral=True
            )
            return False

        # 检查音乐功能是否启用
        if not self.is_available():
            await self.send_error_response(
                interaction,
                "音乐功能当前不可用",
                ephemeral=True
            )
            return False

        return True

    async def check_voice_channel(self, interaction: discord.Interaction) -> bool:
        """
        检查用户是否在语音频道中

        Args:
            interaction: Discord交互对象

        Returns:
            True if user is in voice channel, False otherwise
        """
        if not interaction.user.voice or not interaction.user.voice.channel:
            await self.send_error_response(
                interaction,
                "您必须先加入语音频道才能使用此命令",
                ephemeral=True
            )
            return False

        return True

    async def send_error_response(
        self,
        interaction: discord.Interaction,
        message: str,
        ephemeral: bool = True
    ) -> None:
        """
        发送错误响应

        Args:
            interaction: Discord交互对象
            message: 错误消息
            ephemeral: 是否为私密消息
        """
        embed = discord.Embed(
            title="❌ 错误",
            description=message,
            color=discord.Color.red()
        )

        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=ephemeral)
        except Exception as e:
            self.logger.error(f"发送错误响应失败: {e}")

    async def send_success_response(
        self,
        interaction: discord.Interaction,
        title: str,
        message: str,
        ephemeral: bool = False
    ) -> None:
        """
        发送成功响应

        Args:
            interaction: Discord交互对象
            title: 标题
            message: 消息内容
            ephemeral: 是否为私密消息
        """
        embed = discord.Embed(
            title=f"✅ {title}",
            description=message,
            color=discord.Color.green()
        )

        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=ephemeral)
        except Exception as e:
            self.logger.error(f"发送成功响应失败: {e}")

    async def handle_command_error(
        self,
        interaction: discord.Interaction,
        error: Exception
    ) -> None:
        """
        处理命令执行错误

        Args:
            interaction: Discord交互对象
            error: 异常对象
        """
        self.logger.error(
            f"命令执行错误 - 用户: {interaction.user.display_name}, "
            f"命令: {interaction.command.name if interaction.command else 'Unknown'}, "
            f"错误: {error}",
            exc_info=True
        )

        # 发送用户友好的错误消息
        await self.send_error_response(
            interaction,
            "命令执行时发生错误，请稍后重试",
            ephemeral=True
        )

    @abstractmethod
    async def execute(self, interaction: discord.Interaction, **kwargs) -> None:
        """
        执行命令的抽象方法

        Args:
            interaction: Discord交互对象
            **kwargs: 命令参数
        """
        pass