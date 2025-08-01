"""Odysseia-Similu 音乐机器人通用命令。"""
import logging
import time
from typing import Optional
import discord
from discord.ext import commands

from similubot.core.command_registry import CommandRegistry
from similubot.utils.config_manager import ConfigManager


class GeneralCommands:
    """
    音乐机器人通用命令处理器。

    处理信息查询命令和机器人状态信息。
    """

    def __init__(self, config: ConfigManager, image_generator: Optional = None):
        """
        初始化通用命令。

        Args:
            config: 配置管理器
            image_generator: 已弃用，保持兼容性
        """
        self.logger = logging.getLogger("similubot.commands.general")
        self.config = config

    def register_commands(self, registry: CommandRegistry) -> None:
        """
        Register general commands with the command registry.

        Args:
            registry: Command registry instance
        """
        registry.register_command(
            name="about",
            callback=self.about_command,
            description="Show information about the bot",
            required_permission="about"
        )

        registry.register_command(
            name="help",
            callback=self.help_command,
            description="Show help information",
            required_permission="help"
        )

        registry.register_command(
            name="status",
            callback=self.status_command,
            description="Show bot status information",
            required_permission="status"
        )

        registry.register_command(
            name="ping",
            callback=self.ping_command,
            description="Check bot latency and connection quality",
            required_permission="ping"
        )

        self.logger.debug("General commands registered")

    async def about_command(self, ctx: commands.Context) -> None:
        """
        显示机器人信息。

        Args:
            ctx: Discord 命令上下文
        """
        embed = discord.Embed(
            title="🎵 Odysseia-Similu 音乐机器人",
            description="专为类脑/Odysseia Discord 社区打造的音乐播放机器人",
            color=discord.Color.blue()
        )

        # 音乐命令信息
        embed.add_field(
            name="🎶 音乐播放命令",
            value=f"`{ctx.bot.command_prefix}music <YouTube链接>` - 播放 YouTube 视频音频\n"
                  f"`{ctx.bot.command_prefix}music <Catbox链接>` - 播放 Catbox 音频文件\n"
                  f"`{ctx.bot.command_prefix}music queue` - 显示播放队列\n"
                  f"`{ctx.bot.command_prefix}music now` - 显示当前播放进度\n"
                  f"`{ctx.bot.command_prefix}music skip` - 跳过当前歌曲\n"
                  f"`{ctx.bot.command_prefix}music stop` - 停止播放并清空队列",
            inline=False
        )

        # 高级功能
        embed.add_field(
            name="🎯 高级功能",
            value=f"`{ctx.bot.command_prefix}music jump <数字>` - 跳转到队列指定位置\n"
                  f"`{ctx.bot.command_prefix}music seek <时间>` - 跳转到指定时间\n"
                  f"支持格式：`1:30`（绝对位置）、`+30`（向前30秒）、`-1:00`（向后1分钟）",
            inline=False
        )

        # 支持的音频格式
        embed.add_field(
            name="🎧 支持的音频格式",
            value="MP3, WAV, OGG, M4A, FLAC, AAC, OPUS, WMA",
            inline=False
        )

        # 机器人配置信息
        embed.add_field(
            name="⚙️ 配置信息",
            value=f"最大队列长度: {self.config.get('music.max_queue_size', 100)}\n"
                  f"最大歌曲时长: {self.config.get('music.max_song_duration', 3600)} 秒\n"
                  f"自动断开超时: {self.config.get('music.auto_disconnect_timeout', 300)} 秒",
            inline=True
        )

        # 机器人统计信息
        embed.add_field(
            name="📊 统计信息",
            value=f"服务器数量: {len(ctx.bot.guilds)}\n用户数量: {sum(guild.member_count or 0 for guild in ctx.bot.guilds)}",
            inline=True
        )

        # 项目链接
        embed.add_field(
            name="🔗 项目链接",
            value="[GitHub](https://github.com/Darkatse/Odysseia-Similu) • [类脑社区](https://discord.gg/odysseia)",
            inline=True
        )

        embed.set_footer(text="Odysseia-Similu 音乐机器人 • 基于 Python & discord.py")
        embed.timestamp = discord.utils.utcnow()

        await ctx.send(embed=embed)

    async def help_command(self, ctx: commands.Context, command_name: Optional[str] = None) -> None:
        """
        Show help information.

        Args:
            ctx: Discord command context
            command_name: Specific command to get help for (optional)
        """
        if command_name:
            # Show help for specific command
            command = ctx.bot.get_command(command_name)
            if command:
                embed = discord.Embed(
                    title=f"Help: {ctx.bot.command_prefix}{command.name}",
                    description=command.help or "No description available.",
                    color=0x3498db
                )

                if command.usage:
                    embed.add_field(
                        name="Usage",
                        value=f"`{ctx.bot.command_prefix}{command.name} {command.usage}`",
                        inline=False
                    )

                if command.aliases:
                    embed.add_field(
                        name="Aliases",
                        value=", ".join([f"`{alias}`" for alias in command.aliases]),
                        inline=False
                    )

                await ctx.send(embed=embed)
            else:
                await ctx.reply(f"❌ Command `{command_name}` not found.")
        else:
            # 显示通用帮助
            embed = discord.Embed(
                title="🎵 Odysseia-Similu 音乐机器人帮助",
                description="可用命令和功能",
                color=0x3498db
            )

            # 音乐命令
            music_commands = [
                f"`{ctx.bot.command_prefix}music <链接>` - 播放 YouTube 或 Catbox 音频",
                f"`{ctx.bot.command_prefix}music queue` - 显示播放队列",
                f"`{ctx.bot.command_prefix}music now` - 显示当前播放进度",
                f"`{ctx.bot.command_prefix}music skip` - 跳过当前歌曲",
                f"`{ctx.bot.command_prefix}music stop` - 停止播放并清空队列",
                f"`{ctx.bot.command_prefix}music jump <数字>` - 跳转到队列指定位置",
                f"`{ctx.bot.command_prefix}music seek <时间>` - 跳转到指定时间"
            ]

            embed.add_field(
                name="🎶 音乐命令",
                value="\n".join(music_commands),
                inline=False
            )

            # 通用命令
            general_commands = [
                f"`{ctx.bot.command_prefix}about` - 机器人信息",
                f"`{ctx.bot.command_prefix}status` - 机器人状态",
                f"`{ctx.bot.command_prefix}ping` - 检查延迟和连接质量"
            ]

            embed.add_field(
                name="📋 通用命令",
                value="\n".join(general_commands),
                inline=False
            )

            # 功能特性
            features = [
                "🎵 支持 YouTube 视频音频播放",
                "🎶 支持 Catbox 音频文件播放",
                "📋 完整的音乐队列管理",
                "🎯 精确的时间定位功能",
                "📊 实时播放进度显示"
            ]

            embed.add_field(
                name="✨ 功能特性",
                value="\n".join(features),
                inline=False
            )

            # 获取特定命令帮助
            embed.add_field(
                name="💡 需要更多帮助？",
                value=f"使用 `{ctx.bot.command_prefix}help <命令>` 获取详细的命令信息。",
                inline=False
            )

            embed.set_footer(text="Odysseia-Similu 音乐机器人帮助系统")
            await ctx.send(embed=embed)

    async def status_command(self, ctx: commands.Context) -> None:
        """
        显示机器人状态信息。

        Args:
            ctx: Discord 命令上下文
        """
        embed = discord.Embed(
            title="🎵 音乐机器人状态",
            color=0x2ecc71
        )

        # 机器人基本信息
        embed.add_field(
            name="🤖 机器人信息",
            value=f"**名称:** {ctx.bot.user.name}\n**ID:** {ctx.bot.user.id}\n**延迟:** {round(ctx.bot.latency * 1000)}ms",
            inline=True
        )

        # 服务器统计
        embed.add_field(
            name="📊 服务器统计",
            value=f"**服务器数:** {len(ctx.bot.guilds)}\n**用户数:** {sum(guild.member_count or 0 for guild in ctx.bot.guilds)}\n**频道数:** {len(list(ctx.bot.get_all_channels()))}",
            inline=True
        )

        # 功能状态
        features_status = []
        features_status.append(f"🎵 音乐播放: {'✅ 已启用' if self.config.get('music.enabled', True) else '❌ 已禁用'}")
        features_status.append(f"🎶 YouTube 支持: ✅ 可用")
        features_status.append(f"📁 Catbox 支持: ✅ 可用")

        embed.add_field(
            name="🔧 功能状态",
            value="\n".join(features_status),
            inline=False
        )

        # 配置信息
        config_info = []
        config_info.append(f"**最大队列长度:** {self.config.get('music.max_queue_size', 100)}")
        config_info.append(f"**最大歌曲时长:** {self.config.get('music.max_song_duration', 3600)} 秒")
        config_info.append(f"**自动断开超时:** {self.config.get('music.auto_disconnect_timeout', 300)} 秒")
        config_info.append(f"**默认音量:** {self.config.get('music.volume', 0.5)}")

        embed.add_field(
            name="⚙️ 配置信息",
            value="\n".join(config_info),
            inline=False
        )

        # 系统状态
        embed.add_field(
            name="🟢 系统状态",
            value="所有系统正常运行",
            inline=False
        )

        embed.set_thumbnail(url=ctx.bot.user.avatar.url if ctx.bot.user.avatar else None)
        embed.timestamp = discord.utils.utcnow()
        embed.set_footer(text="Odysseia-Similu 音乐机器人状态")

        await ctx.send(embed=embed)

    async def ping_command(self, ctx: commands.Context) -> None:
        """
        Check bot latency and connection quality.

        Measures both Discord WebSocket latency and API response time,
        displaying results with visual quality indicators.

        Args:
            ctx: Discord command context
        """
        self.logger.debug(f"Ping command invoked by {ctx.author} in {ctx.guild}")

        try:
            # Measure API latency by timing a simple Discord API call
            api_start = time.perf_counter()

            # Use a lightweight API call to measure response time
            # We'll fetch the bot's own user info as it's cached and fast
            await ctx.bot.fetch_user(ctx.bot.user.id)

            api_end = time.perf_counter()
            api_latency_ms = round((api_end - api_start) * 1000, 2)

            # Get WebSocket latency (already in seconds, convert to ms)
            websocket_latency_ms = round(ctx.bot.latency * 1000, 2)

            self.logger.debug(f"Measured latencies - API: {api_latency_ms}ms, WebSocket: {websocket_latency_ms}ms")

            # Determine connection quality and visual indicators
            api_quality = self._get_latency_quality(api_latency_ms)
            ws_quality = self._get_latency_quality(websocket_latency_ms)

            # Overall quality is the worse of the two
            overall_quality = min(api_quality["level"], ws_quality["level"])
            overall_indicator = self._get_quality_indicator(overall_quality)

            # Create embed with results
            embed = discord.Embed(
                title=f"🏓 Pong! {overall_indicator['emoji']}",
                description=f"Connection Quality: **{overall_indicator['text']}**",
                color=overall_indicator["color"]
            )

            # API Latency field
            embed.add_field(
                name=f"{api_quality['emoji']} Discord API Latency",
                value=f"**{api_latency_ms}ms**\n{api_quality['description']}",
                inline=True
            )

            # WebSocket Latency field
            embed.add_field(
                name=f"{ws_quality['emoji']} WebSocket Latency",
                value=f"**{websocket_latency_ms}ms**\n{ws_quality['description']}",
                inline=True
            )

            # Add empty field for layout
            embed.add_field(name="\u200b", value="\u200b", inline=True)

            # Additional info
            embed.add_field(
                name="📊 Connection Details",
                value=(
                    f"**Shard:** {ctx.guild.shard_id if ctx.guild else 'N/A'}\n"
                    f"**Gateway:** {ctx.bot.user.id % 1000}\n"
                    f"**Timestamp:** <t:{int(time.time())}:T>"
                ),
                inline=False
            )

            embed.set_footer(text="Odysseia-Similu 音乐机器人网络诊断")
            embed.timestamp = discord.utils.utcnow()

            await ctx.send(embed=embed)

        except discord.HTTPException as e:
            self.logger.warning(f"Discord API error during ping command: {e}")
            error_embed = discord.Embed(
                title="❌ Network Error",
                description="Failed to measure API latency due to Discord API issues.",
                color=discord.Color.red()
            )
            error_embed.add_field(
                name="WebSocket Latency",
                value=f"{round(ctx.bot.latency * 1000, 2)}ms",
                inline=True
            )
            error_embed.add_field(
                name="Error Details",
                value=f"HTTP {e.status}: {e.text}",
                inline=False
            )
            await ctx.send(embed=error_embed)

        except Exception as e:
            self.logger.error(f"Unexpected error in ping command: {e}", exc_info=True)
            error_embed = discord.Embed(
                title="❌ Ping Failed",
                description="An unexpected error occurred while measuring latency.",
                color=discord.Color.red()
            )
            error_embed.add_field(
                name="Error",
                value=str(e)[:1024],  # Limit error message length
                inline=False
            )
            await ctx.send(embed=error_embed)

    def _get_latency_quality(self, latency_ms: float) -> dict:
        """
        Determine connection quality based on latency.

        Args:
            latency_ms: Latency in milliseconds

        Returns:
            Dictionary with quality information including emoji, description, and level
        """
        if latency_ms < 0:
            return {
                "emoji": "⚠️",
                "description": "Invalid measurement",
                "level": 0
            }
        elif latency_ms <= 50:
            return {
                "emoji": "🟢",
                "description": "Excellent",
                "level": 4
            }
        elif latency_ms <= 100:
            return {
                "emoji": "🟡",
                "description": "Good",
                "level": 3
            }
        elif latency_ms <= 200:
            return {
                "emoji": "🟠",
                "description": "Fair",
                "level": 2
            }
        elif latency_ms <= 500:
            return {
                "emoji": "🔴",
                "description": "Poor",
                "level": 1
            }
        else:
            return {
                "emoji": "🔴",
                "description": "Very Poor",
                "level": 0
            }

    def _get_quality_indicator(self, quality_level: int) -> dict:
        """
        Get overall quality indicator based on quality level.

        Args:
            quality_level: Quality level (0-4)

        Returns:
            Dictionary with overall quality information
        """
        if quality_level >= 4:
            return {
                "emoji": "🟢",
                "text": "Excellent",
                "color": discord.Color.green()
            }
        elif quality_level >= 3:
            return {
                "emoji": "🟡",
                "text": "Good",
                "color": discord.Color.gold()
            }
        elif quality_level >= 2:
            return {
                "emoji": "🟠",
                "text": "Fair",
                "color": discord.Color.orange()
            }
        elif quality_level >= 1:
            return {
                "emoji": "🔴",
                "text": "Poor",
                "color": discord.Color.red()
            }
        else:
            return {
                "emoji": "⚠️",
                "text": "Critical",
                "color": discord.Color.dark_red()
            }

    def get_command_count(self) -> int:
        """
        Get the number of registered general commands.

        Returns:
            Number of commands registered by this module
        """
        return 4  # about, help, status, ping
