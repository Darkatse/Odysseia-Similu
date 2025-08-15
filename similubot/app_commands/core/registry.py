"""
命令注册系统

提供Slash命令的注册和管理功能：
- 命令注册
- 命令树管理
- 同步控制
- 生命周期管理
"""

import logging
from typing import List, Dict, Any, Optional
import discord
from discord import app_commands
from discord.ext import commands

from .command_group import SlashCommandGroup
from .dependency_container import DependencyContainer, ServiceProvider


class CommandRegistry:
    """
    命令注册器

    管理所有Slash命令的注册和生命周期
    """

    def __init__(self, bot: commands.Bot, service_provider: ServiceProvider):
        """
        初始化命令注册器

        Args:
            bot: Discord机器人实例
            service_provider: 服务提供者
        """
        self.bot = bot
        self.service_provider = service_provider
        self.container = service_provider.get_container()
        self.logger = logging.getLogger("similubot.app_commands.registry")

        # 命令组注册表
        self._command_groups: Dict[str, SlashCommandGroup] = {}

        self.logger.debug("命令注册器已初始化")

    def register_music_commands(self) -> None:
        """注册音乐相关的Slash命令"""
        try:
            # 直接注册音乐命令到机器人树，不使用命令组
            self._register_song_request_command()
            self._register_queue_commands()
            self._register_playback_commands()

            self.logger.info("音乐命令已注册")

        except Exception as e:
            self.logger.error(f"注册音乐命令失败: {e}", exc_info=True)
            raise

    def register_general_commands(self) -> None:
        """注册通用命令"""
        try:
            # 注册延迟命令
            self._register_ping_command()

            # 注册帮助命令
            self._register_help_command()

            self.logger.info("通用命令已注册")

        except Exception as e:
            self.logger.error(f"注册通用命令失败: {e}", exc_info=True)
            raise

    def _register_song_request_command(self) -> None:
        """注册点歌命令"""
        @self.bot.tree.command(name="点歌", description="搜索并添加歌曲到播放队列")
        @app_commands.describe(
            链接或名字="歌曲链接(YouTube/NetEase/Bilibili/Catbox)或搜索关键词"
        )
        async def song_request(interaction: discord.Interaction, 链接或名字: str):
            """点歌命令处理器"""
            try:
                from ..music.search_commands import MusicSearchCommands
                from similubot.utils.config_manager import ConfigManager

                config = self.container.resolve(ConfigManager)
                music_player = list(self.service_provider.container._singletons.values())[1]

                handler = MusicSearchCommands(config, music_player)
                await handler.execute(interaction, query=链接或名字)

            except Exception as e:
                self.logger.error(f"点歌命令执行失败: {e}", exc_info=True)
                await self._send_error_response(interaction, "点歌命令执行失败")

    def _register_queue_commands(self) -> None:
        """注册队列相关命令"""
        @self.bot.tree.command(name="歌曲队列", description="显示当前播放队列")
        async def queue_status(interaction: discord.Interaction):
            """队列状态命令处理器"""
            try:
                from ..music.queue_commands import QueueManagementCommands
                from similubot.utils.config_manager import ConfigManager

                config = self.container.resolve(ConfigManager)
                music_player = list(self.service_provider.container._singletons.values())[1]

                handler = QueueManagementCommands(config, music_player)
                await handler.execute(interaction)

            except Exception as e:
                self.logger.error(f"队列命令执行失败: {e}", exc_info=True)
                await self._send_error_response(interaction, "队列命令执行失败")

        @self.bot.tree.command(name="我的队列", description="查看您的队列状态和预计播放时间")
        async def my_queue(interaction: discord.Interaction):
            """我的队列命令处理器"""
            try:
                from ..music.queue_commands import QueueManagementCommands
                from similubot.utils.config_manager import ConfigManager

                config = self.container.resolve(ConfigManager)
                music_player = list(self.service_provider.container._singletons.values())[1]

                handler = QueueManagementCommands(config, music_player)
                await handler.handle_user_queue_status(interaction)

            except Exception as e:
                self.logger.error(f"我的队列命令执行失败: {e}", exc_info=True)
                await self._send_error_response(interaction, "我的队列命令执行失败")

    def _register_playback_commands(self) -> None:
        """注册播放控制命令"""
        @self.bot.tree.command(name="歌曲跳过", description="投票跳过当前播放的歌曲")
        async def skip_song(interaction: discord.Interaction):
            """跳过歌曲命令处理器"""
            try:
                from ..music.playback_commands import PlaybackControlCommands
                from similubot.utils.config_manager import ConfigManager

                config = self.container.resolve(ConfigManager)
                music_player = list(self.service_provider.container._singletons.values())[1]

                handler = PlaybackControlCommands(config, music_player)
                await handler.execute(interaction, action='skip')

            except Exception as e:
                self.logger.error(f"跳过命令执行失败: {e}", exc_info=True)
                await self._send_error_response(interaction, "跳过命令执行失败")

        @self.bot.tree.command(name="歌曲进度", description="显示当前歌曲的播放进度")
        async def song_progress(interaction: discord.Interaction):
            """歌曲进度命令处理器"""
            try:
                from ..music.playback_commands import PlaybackControlCommands
                from similubot.utils.config_manager import ConfigManager

                config = self.container.resolve(ConfigManager)
                music_player = list(self.service_provider.container._singletons.values())[1]

                handler = PlaybackControlCommands(config, music_player)
                await handler.execute(interaction, action='progress')

            except Exception as e:
                self.logger.error(f"进度命令执行失败: {e}", exc_info=True)
                await self._send_error_response(interaction, "进度命令执行失败")

    async def _send_error_response(self, interaction: discord.Interaction, message: str) -> None:
        """
        发送错误响应

        Args:
            interaction: Discord交互对象
            message: 错误消息
        """
        embed = discord.Embed(
            title="❌ 错误",
            description=message,
            color=discord.Color.red()
        )

        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            self.logger.error(f"发送错误响应失败: {e}")

    def _register_ping_command(self) -> None:
        """注册延迟命令"""
        @self.bot.tree.command(name="延迟", description="检查机器人延迟和连接质量")
        async def ping_command(interaction: discord.Interaction):
            """延迟命令处理器"""
            try:
                from ..general.ping_command import PingCommand
                from similubot.utils.config_manager import ConfigManager

                config = self.container.resolve(ConfigManager)
                command_handler = PingCommand(config)
                await command_handler.execute(interaction)

            except Exception as e:
                self.logger.error(f"延迟命令执行失败: {e}", exc_info=True)
                await self._send_error_response(interaction, "延迟检测失败")

    def _register_help_command(self) -> None:
        """注册帮助命令"""
        @self.bot.tree.command(name="帮助", description="显示机器人信息和使用指南")
        async def help_command(interaction: discord.Interaction):
            """帮助命令处理器"""
            try:
                from ..general.help_command import HelpCommand
                from similubot.utils.config_manager import ConfigManager

                config = self.container.resolve(ConfigManager)
                command_handler = HelpCommand(config)
                await command_handler.execute(interaction)

            except Exception as e:
                self.logger.error(f"帮助命令执行失败: {e}", exc_info=True)
                await self._send_error_response(interaction, "帮助信息加载失败")

    async def sync_commands(self, guild: Optional[discord.Guild] = None) -> None:
        """
        同步命令到Discord

        Args:
            guild: 可选的服务器对象，如果为None则全局同步
        """
        try:
            if guild:
                synced = await self.bot.tree.sync(guild=guild)
                self.logger.info(f"已同步 {len(synced)} 个命令到服务器 {guild.name}")
            else:
                synced = await self.bot.tree.sync()
                self.logger.info(f"已全局同步 {len(synced)} 个命令")

        except Exception as e:
            self.logger.error(f"同步命令失败: {e}", exc_info=True)
            raise

    def get_command_group(self, name: str) -> Optional[SlashCommandGroup]:
        """
        获取命令组

        Args:
            name: 命令组名称

        Returns:
            命令组实例或None
        """
        return self._command_groups.get(name)

    def unregister_all(self) -> None:
        """注销所有命令"""
        try:
            self.bot.tree.clear_commands(guild=None)
            self._command_groups.clear()
            self.logger.info("所有命令已注销")

        except Exception as e:
            self.logger.error(f"注销命令失败: {e}", exc_info=True)