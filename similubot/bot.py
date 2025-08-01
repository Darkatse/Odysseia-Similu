"""Refactored main Discord bot implementation for SimiluBot."""
import logging
import os
from typing import Optional
import discord
from discord.ext import commands

# Core modules
from similubot.core.command_registry import CommandRegistry
from similubot.core.event_handler import EventHandler

# Command modules
from similubot.commands.general_commands import GeneralCommands
from similubot.commands.music_commands import MusicCommands

# Core modules
from similubot.music.music_player import MusicPlayer
from similubot.utils.config_manager import ConfigManager


class SimiluBot:
    """
    Odysseia-Similu 音乐机器人主实现类。

    专为类脑/Odysseia Discord 社区打造的音乐播放机器人：
    - 支持 YouTube 视频和 Catbox 音频文件播放
    - 完整的音乐队列管理系统
    - 实时播放进度显示
    - 精确的时间定位功能
    - 模块化架构，易于维护和扩展
    """

    def __init__(self, config: ConfigManager):
        """
        Initialize the Discord bot.

        Args:
            config: Configuration manager
        """
        self.logger = logging.getLogger("similubot.bot")
        self.config = config

        # Set up Discord bot
        intents = discord.Intents.default()
        intents.message_content = True

        self.bot = commands.Bot(
            command_prefix=self.config.get('discord.command_prefix', '!'),
            intents=intents,
            help_command=None  # We'll use our custom help command
        )

        # Initialize core components
        self._init_core_modules()

        # Initialize command modules
        self._init_command_modules()

        # Register commands and events
        self._register_commands()
        self._setup_event_handlers()

        self.logger.info("🎵 音乐机器人初始化成功")

    def _init_core_modules(self) -> None:
        """初始化核心机器人模块。"""
        # 创建临时目录（如果不存在）
        temp_dir = self.config.get('download.temp_dir', './temp')
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
            self.logger.debug(f"创建临时目录: {temp_dir}")

        # 初始化音乐播放器
        self.music_player = MusicPlayer(
            bot=self.bot,
            temp_dir=temp_dir,
            config=self.config
        )

        # 初始化命令注册器（简化版，不需要授权系统）
        self.command_registry = CommandRegistry(
            bot=self.bot,
            auth_manager=None,
            unauthorized_handler=None
        )

        self.logger.debug("核心模块初始化完成")

    def _init_command_modules(self) -> None:
        """初始化命令模块。"""
        # 初始化通用命令
        self.general_commands = GeneralCommands(
            config=self.config,
            image_generator=None  # 不再支持图像生成
        )

        # 初始化音乐命令
        self.music_commands = MusicCommands(
            config=self.config,
            music_player=self.music_player
        )

        self.logger.debug("命令模块初始化完成")

    def _register_commands(self) -> None:
        """注册所有命令到命令注册器。"""
        # 注册通用命令
        self.general_commands.register_commands(self.command_registry)

        # 注册音乐命令（如果可用）
        if self.music_commands.is_available():
            self.music_commands.register_commands(self.command_registry)
            self.logger.info("✅ 音乐命令注册成功")
        else:
            self.logger.warning("❌ 音乐命令未注册（已禁用）")

        self.logger.info("🎵 所有命令注册完成")

    def _setup_event_handlers(self) -> None:
        """设置 Discord 事件处理器。"""
        # 初始化事件处理器（简化版，只处理基本事件）
        self.event_handler = EventHandler(
            bot=self.bot,
            auth_manager=None,
            unauthorized_handler=None,
            mega_downloader=None,
            mega_processor_callback=None
        )

        self.logger.debug("事件处理器设置完成")

    async def start(self, token: str) -> None:
        """
        Start the Discord bot.

        Args:
            token: Discord bot token
        """
        try:
            self.logger.info("🚀 启动音乐机器人...")
            await self.bot.start(token)
        except Exception as e:
            self.logger.error(f"启动机器人失败: {e}", exc_info=True)
            raise

    async def close(self) -> None:
        """关闭 Discord 机器人并清理资源。"""
        try:
            self.logger.info("🛑 正在关闭音乐机器人...")

            # 清理音乐命令（如果可用）
            if hasattr(self, 'music_commands'):
                await self.music_commands.cleanup()

            # 清理音乐播放器（如果可用）
            if hasattr(self, 'music_player'):
                await self.music_player.cleanup_all()

            await self.bot.close()
            self.logger.info("✅ 音乐机器人关闭成功")
        except Exception as e:
            self.logger.error(f"关闭过程中发生错误: {e}", exc_info=True)

    def run(self, token: str) -> None:
        """
        运行 Discord 机器人（阻塞式）。

        Args:
            token: Discord 机器人令牌
        """
        try:
            self.bot.run(token)
        except KeyboardInterrupt:
            self.logger.info("用户停止了机器人")
        except Exception as e:
            self.logger.error(f"机器人崩溃: {e}", exc_info=True)
            raise

    def get_stats(self) -> dict:
        """
        获取机器人统计信息。

        Returns:
            包含机器人统计信息的字典
        """
        stats = {
            "bot_ready": self.bot.is_ready(),
            "guild_count": len(self.bot.guilds),
            "user_count": sum(guild.member_count or 0 for guild in self.bot.guilds),
            "command_count": len(self.command_registry.get_registered_commands()),
            "music_enabled": self.music_commands.is_available() if hasattr(self, 'music_commands') else False
        }

        return stats

    def get_registered_commands(self) -> dict:
        """
        获取所有已注册的命令。

        Returns:
            已注册命令的字典
        """
        return self.command_registry.get_registered_commands()

    def is_ready(self) -> bool:
        """
        检查机器人是否就绪。

        Returns:
            如果机器人就绪返回 True，否则返回 False
        """
        return self.bot.is_ready()

    @property
    def user(self) -> Optional[discord.ClientUser]:
        """获取机器人用户。"""
        return self.bot.user

    @property
    def latency(self) -> float:
        """获取机器人延迟。"""
        return self.bot.latency

    @property
    def guilds(self) -> list:
        """获取机器人所在的服务器列表。"""
        return list(self.bot.guilds)
