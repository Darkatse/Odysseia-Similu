"""Odysseia-Similu 音乐机器人事件处理器。"""
import logging
from typing import Optional
import discord
from discord.ext import commands


class EventHandler:
    """
    Odysseia-Similu 音乐机器人事件处理器。

    管理机器人生命周期事件，简化版本。
    """

    def __init__(
        self,
        bot: commands.Bot,
        auth_manager: Optional = None,
        unauthorized_handler: Optional = None,
        mega_downloader: Optional = None,
        mega_processor_callback: Optional[callable] = None
    ):
        """
        初始化事件处理器。

        Args:
            bot: Discord 机器人实例
            auth_manager: 已弃用，保持兼容性
            unauthorized_handler: 已弃用，保持兼容性
            mega_downloader: 已弃用，保持兼容性
            mega_processor_callback: 已弃用，保持兼容性
        """
        self.logger = logging.getLogger("similubot.events")
        self.bot = bot

        # 注册事件处理器
        self._register_events()

    def _register_events(self) -> None:
        """注册 Discord 事件处理器。"""
        @self.bot.event
        async def on_ready():
            await self._on_ready()

        @self.bot.event
        async def on_message(message):
            await self._on_message(message)

        @self.bot.event
        async def on_command_error(ctx, error):
            await self._on_command_error(ctx, error)

        self.logger.debug("事件处理器注册完成")

    async def _on_ready(self) -> None:
        """处理机器人就绪事件。"""
        if self.bot.user is None:
            self.logger.error("机器人用户在 on_ready 事件中为 None")
            return

        self.logger.info(f"🎵 音乐机器人已就绪。登录为 {self.bot.user.name} ({self.bot.user.id})")

        # 设置机器人状态
        activity = discord.Activity(
            type=discord.ActivityType.listening,
            name=f"🎵 {self.bot.command_prefix}music | {self.bot.command_prefix}about"
        )
        await self.bot.change_presence(activity=activity)

        # 初始化持久化系统（如果可用）
        try:
            # 从 bot 实例获取 music_player 并初始化持久化
            if hasattr(self.bot, '_similu_bot') and hasattr(self.bot._similu_bot, 'music_player'):
                await self.bot._similu_bot.music_player.initialize_persistence()
        except Exception as e:
            self.logger.error(f"初始化持久化系统失败: {e}")

        self.logger.info("✅ Odysseia-Similu 音乐机器人已准备就绪")

    async def _on_message(self, message: discord.Message) -> None:
        """
        处理传入消息。

        Args:
            message: Discord 消息
        """
        # 忽略机器人自己的消息
        if message.author == self.bot.user:
            return

        # 处理命令
        await self.bot.process_commands(message)

    async def _on_command_error(self, ctx: commands.Context, error: Exception) -> None:
        """
        处理命令错误。

        Args:
            ctx: 命令上下文
            error: 发生的异常
        """
        # 处理特定错误类型
        if isinstance(error, commands.CommandNotFound):
            # 静默忽略未知命令
            return

        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply(f"❌ 缺少必需参数: `{error.param.name}`")
            await ctx.send_help(ctx.command)

        elif isinstance(error, commands.BadArgument):
            await ctx.reply(f"❌ 无效参数: {str(error)}")
            await ctx.send_help(ctx.command)

        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.reply(f"❌ 命令冷却中。请在 {error.retry_after:.1f} 秒后重试。")
            
        elif isinstance(error, commands.NoPrivateMessage):
            await ctx.reply("❌ 此命令不能在私信中使用。")

        elif isinstance(error, commands.DisabledCommand):
            await ctx.reply("❌ 此命令当前已禁用。")

        elif isinstance(error, commands.CheckFailure):
            await ctx.reply("❌ 您没有权限使用此命令。")

        else:
            # 记录意外错误
            self.logger.error(
                f"命令 {ctx.command} 中的意外错误: {error}",
                exc_info=True
            )
            await ctx.reply(f"❌ 发生意外错误: {str(error)}")




    def get_event_stats(self) -> dict:
        """
        Get event handling statistics.

        Returns:
            Dictionary with event statistics
        """
        return {
            "bot_ready": self.bot.is_ready(),
            "bot_user": str(self.bot.user) if self.bot.user else None,
            "guild_count": len(self.bot.guilds),
            "user_count": sum(guild.member_count or 0 for guild in self.bot.guilds),
            "authorization_enabled": self.auth_manager.auth_enabled
        }
