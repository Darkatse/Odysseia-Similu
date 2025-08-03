"""Odysseia-Similu 音乐命令模块"""

import logging
import asyncio
from typing import Optional, List, Dict, Any, Union
import discord
from discord.ext import commands
import sys

from similubot.core.command_registry import CommandRegistry
from similubot.progress.discord_updater import DiscordProgressUpdater
from similubot.progress.music_progress import MusicProgressBar
from similubot.utils.config_manager import ConfigManager
from similubot.queue.user_queue_status import UserQueueStatusService


class MusicCommands:
    """
    Music command handlers for SimiluBot.

    Provides commands for music playback, queue management,
    and voice channel interaction.
    """

    def __init__(self, config: ConfigManager, music_player: Any):
        """
        初始化音乐命令模块

        Args:
            config: 配置管理器
            music_player: 音乐播放器实例（支持新旧架构）
        """
        self.logger = logging.getLogger("similubot.commands.music")
        self.config = config
        self.music_player = music_player

        # Initialize progress bar
        self.progress_bar = MusicProgressBar(music_player)

        # Check if music functionality is enabled
        self._enabled = config.get('music.enabled', True)

        self.logger.debug("Music commands initialized")

    def is_available(self) -> bool:
        """
        Check if music commands are available.

        Returns:
            True if available, False otherwise
        """
        return self._enabled

    def register_commands(self, registry: CommandRegistry) -> None:
        """
        Register music commands with the command registry.

        Args:
            registry: Command registry instance
        """
        if not self.is_available():
            self.logger.info("Music commands not registered (disabled)")
            return

        # 1. Play Command (main command for adding songs)
        registry.register_command(
            name="play",
            aliases=["music", "m"],
            callback=self.play_command,
            description="添加歌曲到队列并开始播放",
            required_permission="music",
            usage_examples=[
                "!play <youtube链接>",
                "!m <catbox链接>",
                "!music <bilibili链接>"
            ],
            help_text="支持YouTube, Catbox, Bilibili链接。使用前需加入语音频道。"
        )

        # 2. Queue Command
        registry.register_command(
            name="queue",
            aliases=["q"],
            callback=self._handle_queue_command,
            description="显示当前播放队列",
            required_permission="music"
        )

        # 3. Now Playing Command
        registry.register_command(
            name="now",
            aliases=["np", "current", "playing"],
            callback=self._handle_now_command,
            description="显示当前歌曲播放进度",
            required_permission="music"
        )

        # 4. My Status Command
        registry.register_command(
            name="my",
            aliases=["mine", "mystatus"],
            callback=self._handle_my_command,
            description="查看您的队列状态和预计播放时间",
            required_permission="music"
        )

        # 5. Skip Command
        registry.register_command(
            name="skip",
            aliases=["next"],
            callback=self._handle_skip_command,
            description="跳过当前歌曲",
            required_permission="music"
        )

        # 6. Stop Command
        registry.register_command(
            name="stop",
            aliases=["disconnect", "leave"],
            callback=self._handle_stop_command,
            description="停止播放并清空队列",
            required_permission="music"
        )

        # 7. Jump Command
        registry.register_command(
            name="jump",
            aliases=["goto"],
            callback=self.jump_command,
            description="跳转到队列指定位置",
            required_permission="music",
            usage_examples=["!jump 5"]
        )

        # 8. Seek Command
        registry.register_command(
            name="seek",
            callback=self.seek_command,
            description="跳转到指定时间",
            required_permission="music",
            usage_examples=["!seek 1:30", "!seek +30"]
        )

        # 9. Persistence Status Command
        registry.register_command(
            name="status",
            aliases=["persistence", "persist"],
            callback=self.persistence_status,
            description="显示队列持久化状态",
            required_permission="music"
        )

        self.logger.debug("All music commands registered as top-level commands.")

    async def play_command(self, ctx: commands.Context, *, url: str) -> None:
        """
        Handles the play command, which now accepts a URL directly.
        This is the primary command for adding songs.
        """
        if self.music_player.is_supported_url(url):
            await self._handle_play_command(ctx, url)
        else:
            await ctx.reply("❌ 无效的链接。请输入一个有效的 YouTube, Catbox 或 Bilibili 链接。")

    async def jump_command(self, ctx: commands.Context, position: int) -> None:
        """
        Handles the jump command with automatic type conversion.
        """
        await self._handle_jump_command(ctx, position)

    async def seek_command(self, ctx: commands.Context, *, time_str: Optional[str] = None) -> None:
        """
        Handles the seek command. Shows help if no time is provided.
        """
        if not time_str:
            await self._show_seek_help(ctx)
            return
        await self._handle_seek_command(ctx, time_str)

    async def _handle_play_command(self, ctx: commands.Context, url: str) -> None:
        """
        Handle play command (add song to queue).

        Args:
            ctx: Discord command context
            url: Audio URL (YouTube or Catbox)
        """
        # Check if user is in voice channel
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.reply("❌ 您必须先加入语音频道才能播放音乐！")
            return

        # Connect to voice channel if not already connected
        success, error = await self.music_player.connect_to_user_channel(ctx.author)
        if not success:
            await ctx.reply(f"❌ {error}")
            return

        # Set the text channel for event notifications (修复事件通知频道问题)
        if hasattr(self.music_player, '_playback_engine') and ctx.guild:
            self.music_player._playback_engine.set_text_channel(ctx.guild.id, ctx.channel.id)
            self.logger.debug(f"🔧 设置服务器 {ctx.guild.id} 的文本频道为 {ctx.channel.id}")

        # Detect source type for initial message
        source_type = self.music_player.detect_audio_source_type(url)
        source_name = source_type.value.title() if source_type else "Audio"

        # Send initial response
        response = await ctx.reply(f"🔄 Processing {source_name} URL...")

        # Create progress updater
        progress_updater = DiscordProgressUpdater(response)
        progress_callback = progress_updater.create_callback()

        try:
            # Add song to queue
            success, position, error = await self.music_player.add_song_to_queue(
                url, ctx.author, progress_callback
            )

            if not success:
                # Check the type of error and provide appropriate feedback
                if error and "已经请求了这首歌曲" in error:
                    await self._send_duplicate_song_embed(response, error)
                elif error and ("已经有" in error and "首歌曲在队列中" in error):
                    await self._send_queue_fairness_embed(response, error, ctx.author)
                elif error and "正在播放中" in error:
                    await self._send_currently_playing_embed(response, error)
                elif error and "歌曲时长" in error and "超过了最大限制" in error:
                    await self._send_song_too_long_embed(response, error)
                else:
                    await self._send_error_embed(response, "添加歌曲失败", error or "未知错误")
                return

            # Get audio info for the added song based on source type
            audio_info = None
            if source_type and source_type.value == "youtube":
                audio_info = await self.music_player.youtube_client.extract_audio_info(url)
            elif source_type and source_type.value == "catbox":
                audio_info = await self.music_player.catbox_client.extract_audio_info(url)
            elif source_type and source_type.value == "bilibili":
                audio_info = await self.music_player.bilibili_client.extract_audio_info(url)

            if not audio_info:
                await self._send_error_embed(response, "错误", "获取歌曲信息失败")
                return

            # Create success embed
            embed = discord.Embed(
                title="🎵 歌曲已添加到队列",
                color=discord.Color.green()
            )

            embed.add_field(
                name="歌曲标题",
                value=audio_info.title,
                inline=False
            )

            # Format duration based on source type
            if hasattr(audio_info, 'duration') and audio_info.duration > 0:
                duration_str = self.music_player.youtube_client.format_duration(audio_info.duration)
            else:
                duration_str = "未知"

            embed.add_field(
                name="时长",
                value=duration_str,
                inline=True
            )

            embed.add_field(
                name="来源",
                value=audio_info.uploader,
                inline=True
            )

            # Add file size for Catbox files
            if hasattr(audio_info, 'file_size') and audio_info.file_size:
                try:
                    file_size_str = self.music_player.catbox_client.format_file_size(audio_info.file_size)
                    embed.add_field(
                        name="文件大小",
                        value=file_size_str,
                        inline=True
                    )
                    self.logger.debug(f"成功格式化Catbox文件大小: {file_size_str}")
                except Exception as e:
                    self.logger.warning(f"格式化Catbox文件大小失败: {e}")
                    # 提供备用的文件大小显示
                    embed.add_field(
                        name="文件大小",
                        value=f"{audio_info.file_size} bytes",
                        inline=True
                    )

            embed.add_field(
                name="队列位置",
                value=f"#{position}",
                inline=True
            )

            embed.add_field(
                name="点歌人",
                value=ctx.author.display_name,
                inline=True
            )

            # Add format info for Catbox files
            if hasattr(audio_info, 'file_format') and audio_info.file_format:
                embed.add_field(
                    name="格式",
                    value=audio_info.file_format.upper(),
                    inline=True
                )

            if hasattr(audio_info, 'thumbnail_url') and audio_info.thumbnail_url:
                embed.set_thumbnail(url=audio_info.thumbnail_url)

            await response.edit(content=None, embed=embed)

        except Exception as e:
            self.logger.error(f"Error in play command: {e}", exc_info=True)
            await self._send_error_embed(response, "意外错误", str(e))

    async def _handle_queue_command(self, ctx: commands.Context) -> None:
        """
        Handle queue display command.

        Args:
            ctx: Discord command context
        """
        try:
            queue_info = await self.music_player.get_queue_info(ctx.guild.id)

            if queue_info["is_empty"] and not queue_info["current_song"]:
                embed = discord.Embed(
                    title="🎵 音乐队列",
                    description="队列为空",
                    color=discord.Color.blue()
                )
                await ctx.reply(embed=embed)
                return

            embed = discord.Embed(
                title="🎵 音乐队列",
                color=discord.Color.blue()
            )

            # Add current song info
            if queue_info["current_song"]:
                current = queue_info["current_song"]
                embed.add_field(
                    name="🎶 正在播放",
                    value=f"**{current.title}**\n"
                          f"时长: {self.music_player.youtube_client.format_duration(current.duration)}\n"
                          f"点歌人: {current.requester.display_name}",
                    inline=False
                )

            # Add queue info
            if not queue_info["is_empty"]:
                queue_manager = self.music_player.get_queue_manager(ctx.guild.id)
                queue_display = await queue_manager.get_queue_display(max_songs=10)

                if queue_display:
                    queue_text = ""
                    for song in queue_display:
                        queue_text += (
                            f"**{song['position']}.** {song['title']}\n"
                            f"    时长: {song['duration']} | "
                            f"点歌人: {song['requester']}\n\n"
                        )

                    embed.add_field(
                        name="📋 即将播放",
                        value=queue_text[:1024],  # Discord field limit
                        inline=False
                    )

                # Add queue summary
                total_duration = self.music_player.youtube_client.format_duration(
                    queue_info["total_duration"]
                )
                embed.add_field(
                    name="📊 队列统计",
                    value=f"歌曲数量: {queue_info['queue_length']}\n"
                          f"总时长: {total_duration}",
                    inline=True
                )

            # Add voice connection info
            if queue_info["connected"]:
                embed.add_field(
                    name="🔊 语音状态",
                    value=f"频道: {queue_info['channel']}\n"
                          f"播放中: {'是' if queue_info['playing'] else '否'}\n"
                          f"已暂停: {'是' if queue_info['paused'] else '否'}",
                    inline=True
                )

            await ctx.reply(embed=embed)

        except Exception as e:
            self.logger.error(f"Error in queue command: {e}", exc_info=True)
            await ctx.reply("❌ 获取队列信息时出错")

    async def _handle_now_command(self, ctx: commands.Context) -> None:
        """
        Handle now playing command with real-time progress bar.

        Args:
            ctx: Discord command context
        """
        try:
            # Check if guild exists
            if not ctx.guild:
                await ctx.reply("❌ This command can only be used in a server")
                return

            queue_info = await self.music_player.get_queue_info(ctx.guild.id)
            current_song = queue_info.get("current_song")

            if not current_song:
                await ctx.reply("❌ 当前没有歌曲在播放")
                return

            # Send initial response
            response = await ctx.reply("🔄 Loading progress bar...")

            # Start real-time progress bar
            success = await self.progress_bar.show_progress_bar(response, ctx.guild.id)

            if not success:
                # Fallback to static display
                embed = discord.Embed(
                    title="🎶 正在播放",
                    color=discord.Color.green()
                )

                embed.add_field(
                    name="歌曲标题",
                    value=current_song.title,
                    inline=False
                )

                embed.add_field(
                    name="时长",
                    value=self.music_player.youtube_client.format_duration(current_song.duration),
                    inline=True
                )

                embed.add_field(
                    name="上传者",
                    value=current_song.uploader,
                    inline=True
                )

                embed.add_field(
                    name="点歌人",
                    value=current_song.requester.display_name,
                    inline=True
                )

                # Add static status
                if queue_info["playing"]:
                    embed.add_field(
                        name="状态",
                        value="▶️ 播放中",
                        inline=True
                    )
                elif queue_info["paused"]:
                    embed.add_field(
                        name="状态",
                        value="⏸️ 已暂停",
                        inline=True
                    )

                if current_song.audio_info.thumbnail_url:
                    embed.set_thumbnail(url=current_song.audio_info.thumbnail_url)

                await response.edit(content=None, embed=embed)

        except Exception as e:
            self.logger.error(f"Error in now command: {e}", exc_info=True)
            await ctx.reply("❌ 获取当前歌曲信息时出错")

    async def _handle_my_command(self, ctx: commands.Context) -> None:
        """
        处理用户队列状态查询命令 (!music my)

        显示用户当前在队列中的歌曲详情，包括：
        - 歌曲名称
        - 队列位置
        - 预计播放时间

        Args:
            ctx: Discord命令上下文
        """
        try:
            # 检查服务器是否存在
            if not ctx.guild:
                await ctx.reply("❌ 此命令只能在服务器中使用")
                return

            # 创建用户队列状态服务实例
            # 使用音乐播放器适配器的内部播放引擎
            if not hasattr(self.music_player, '_playback_engine'):
                await ctx.reply("❌ 音乐播放器未正确初始化")
                return

            user_queue_service = UserQueueStatusService(self.music_player._playback_engine)

            # 获取用户队列信息
            user_info = user_queue_service.get_user_queue_info(ctx.author, ctx.guild.id)

            # 创建响应嵌入消息
            if not user_info.has_queued_song:
                embed = discord.Embed(
                    title="🎵 我的队列状态",
                    description="您当前没有歌曲在队列中。",
                    color=discord.Color.blue()
                )
                embed.add_field(
                    name="💡 提示",
                    value="使用 `!music <YouTube链接>` 或 `!music <Catbox链接>` 来添加歌曲到队列。",
                    inline=False
                )
            else:
                # 用户有歌曲在队列中
                if user_info.is_currently_playing:
                    embed = discord.Embed(
                        title="🎵 我的队列状态",
                        description=f"您的歌曲正在播放中！",
                        color=discord.Color.green()
                    )
                    embed.add_field(
                        name="🎶 正在播放",
                        value=f"**{user_info.queued_song_title}**",
                        inline=False
                    )
                else:
                    embed = discord.Embed(
                        title="🎵 我的队列状态",
                        description="您有歌曲在队列中等待播放。",
                        color=discord.Color.orange()
                    )
                    embed.add_field(
                        name="🎶 排队歌曲",
                        value=f"**{user_info.queued_song_title}**",
                        inline=False
                    )

                    if user_info.queue_position:
                        embed.add_field(
                            name="📍 队列位置",
                            value=f"第 {user_info.queue_position} 位",
                            inline=True
                        )

                    if user_info.estimated_play_time_seconds is not None:
                        embed.add_field(
                            name="⏰ 预计播放时间",
                            value=f"{user_info.format_estimated_time()} 后",
                            inline=True
                        )

            await ctx.reply(embed=embed)

        except Exception as e:
            self.logger.error(f"Error in my command: {e}", exc_info=True)
            await ctx.reply("❌ 获取您的队列状态时出错")

    async def _handle_exit_command(self, ctx: commands.Context) -> None:
        """
        暴力结束进程。
        """

        if (ctx.author.id != self.config.get('bot.owner_id') and
                ctx.author.id != self.config.get('bot.admin_id')):
            await ctx.reply("❌ 您没有权限执行此命令")
            return

        try:
            # Check if guild exists
            if not ctx.guild:
                await ctx.reply("❌ 此命令只能在服务器中使用")
                return

            # Stop any active progress bars
            self.progress_bar.stop_progress_updates(ctx.guild.id)

            # Save persistence state
            await self.music_player.manual_save(ctx.guild.id)

            # Disconnect from voice channel
            success = await self.music_player.voice_manager.disconnect_from_guild(ctx.guild.id)
    
            if not success:
                await ctx.reply("❌ 断开连接失败")
                return

            embed = discord.Embed(
                title="🔌 已断开连接",
                description="已终止进程。",
                color=discord.Color.red()
            )

            await ctx.reply(embed=embed)

            # Violently end the process
            sys.exit(0)

        except Exception as e:
            self.logger.error(f"Error in exit command: {e}", exc_info=True)
            await ctx.reply("❌ 断开连接时出错")

    async def _handle_skip_command(self, ctx: commands.Context) -> None:
        """
        Handle skip command.

        Args:
            ctx: Discord command context
        """
        try:
            # Check if guild exists
            if not ctx.guild:
                await ctx.reply("❌ 此命令只能在服务器中使用")
                return

            # Stop any active progress bars
            self.progress_bar.stop_progress_updates(ctx.guild.id)

            success, skipped_title, error = await self.music_player.skip_current_song(ctx.guild.id)

            if not success:
                await ctx.reply(f"❌ {error}")
                return

            embed = discord.Embed(
                title="⏭️ 歌曲已跳过",
                description=f"已跳过: **{skipped_title}**",
                color=discord.Color.orange()
            )

            await ctx.reply(embed=embed)

        except Exception as e:
            self.logger.error(f"Error in skip command: {e}", exc_info=True)
            await ctx.reply("❌ 跳过歌曲时出错")

    async def _handle_stop_command(self, ctx: commands.Context) -> None:
        """
        Handle stop command.

        Args:
            ctx: Discord command context
        """
        try:
            # Check if guild exists
            if not ctx.guild:
                await ctx.reply("❌ 此命令只能在服务器中使用")
                return

            # Stop any active progress bars
            self.progress_bar.stop_progress_updates(ctx.guild.id)

            success, error = await self.music_player.stop_playback(ctx.guild.id)

            if not success:
                await ctx.reply(f"❌ {error}")
                return

            embed = discord.Embed(
                title="⏹️ 播放已停止",
                description="已停止播放并清空队列，已断开语音频道连接。",
                color=discord.Color.red()
            )

            await ctx.reply(embed=embed)

        except Exception as e:
            self.logger.error(f"Error in stop command: {e}", exc_info=True)
            await ctx.reply("❌ 停止播放时出错")

    async def _handle_jump_command(self, ctx: commands.Context, position: int) -> None:
        """
        Handle jump command.

        Args:
            ctx: Discord command context
            position: Target queue position (converted by discord.py)
        """
        try:
            # Check if guild exists
            if not ctx.guild:
                await ctx.reply("❌ 此命令只能在服务器中使用")
                return

            if position < 1:
                await ctx.reply("❌ 队列位置必须大于等于1")
                return

            # Stop any active progress bars
            self.progress_bar.stop_progress_updates(ctx.guild.id)

            success, song_title, error = await self.music_player.jump_to_position(
                ctx.guild.id, position
            )

            if not success:
                await ctx.reply(f"❌ {error}")
                return

            embed = discord.Embed(
                title="⏭️ 已跳转到歌曲",
                description=f"正在播放: **{song_title}**",
                color=discord.Color.green()
            )

            await ctx.reply(embed=embed)

        except commands.BadArgument:
            await ctx.reply("❌ 无效的位置数字。请输入一个整数。")
        except Exception as e:
            self.logger.error(f"Error in jump command: {e}", exc_info=True)
            await ctx.reply("❌ 跳转到指定位置时出错")

    async def _handle_seek_command(self, ctx: commands.Context, time_str: str) -> None:
        """
        Handle seek command.

        Args:
            ctx: Discord command context
            time_str: Time string for seeking (e.g., "1:30", "+30")
        """
        try:
            # Check if guild exists
            if not ctx.guild:
                await ctx.reply("❌ 此命令只能在服务器中使用")
                return

            # Perform seek operation
            success, error = await self.music_player.seek_to_position(ctx.guild.id, time_str)

            if not success:
                await ctx.reply(f"❌ {error}")
                return

            # Parse the time for display purposes
            seek_result = self.music_player.seek_manager.parse_seek_time(time_str)
            if seek_result.success and seek_result.target_position is not None:
                is_relative = self.music_player.seek_manager.is_relative_seek(time_str)

                if is_relative:
                    # For relative seeks, show the direction
                    direction = "向前" if seek_result.target_position >= 0 else "向后"
                    formatted_time = self.music_player.seek_manager.format_time(abs(seek_result.target_position))
                    description = f"已{direction}跳转 {formatted_time}"
                else:
                    # For absolute seeks, show the target position
                    formatted_time = self.music_player.seek_manager.format_time(seek_result.target_position)
                    description = f"已跳转到 {formatted_time}"
            else:
                description = f"已跳转到位置: {time_str}"

            embed = discord.Embed(
                title="🎯 定位完成",
                description=description,
                color=discord.Color.green()
            )

            await ctx.reply(embed=embed)

        except Exception as e:
            self.logger.error(f"Error in seek command: {e}", exc_info=True)
            await ctx.reply("❌ 跳转到指定位置时出错")

    async def _show_seek_help(self, ctx: commands.Context) -> None:
        """
        Shows help for the seek command.
        """
        embed = discord.Embed(
            title="🎯 定位命令帮助 (`!seek`)",
            description="跳转到当前播放歌曲的指定位置。",
            color=discord.Color.blue()
        )

        examples = self.music_player.seek_manager.get_seek_examples()
        examples_text = "\n".join(f"`{ex}`" for ex in examples)

        embed.add_field(
            name="使用示例",
            value=examples_text,
            inline=False
        )

        embed.add_field(
            name="支持的格式",
            value="• `mm:ss` - 跳转到绝对位置\n"
                  "• `hh:mm:ss` - 跳转到绝对位置（包含小时）\n"
                  "• `+mm:ss` - 相对当前位置向前跳转\n"
                  "• `-mm:ss` - 相对当前位置向后跳转\n"
                  "• `+秒数` - 向前跳转指定秒数\n"
                  "• `-秒数` - 向后跳转指定秒数",
            inline=False
        )

        await ctx.reply(embed=embed)

    async def _send_error_embed(
        self,
        message: discord.Message,
        title: str,
        description: str
    ) -> None:
        """
        Send an error embed.

        Args:
            message: Message to edit
            title: Error title
            description: Error description
        """
        embed = discord.Embed(
            title=f"❌ {title}",
            description=description,
            color=discord.Color.red()
        )

        await message.edit(content=None, embed=embed)

    async def _send_duplicate_song_embed(self, message: discord.Message, error_message: str) -> None:
        """
        Send duplicate song error embed message.

        Args:
            message: Message to edit
            error_message: Duplicate error message
        """
        embed = discord.Embed(
            title="🔄 重复歌曲",
            description=error_message,
            color=discord.Color.orange()
        )
        embed.add_field(
            name="💡 提示",
            value="等待当前歌曲播放完成后，您就可以再次请求这首歌曲了。",
            inline=False
        )
        await message.edit(content=None, embed=embed)

    async def _send_queue_fairness_embed(self, message: discord.Message, error_message: str, user: Union[discord.User, discord.Member]) -> None:
        """
        发送队列公平性错误嵌入消息，包含详细的用户队列状态信息

        Args:
            message: 要编辑的消息
            error_message: 队列公平性错误消息
            user: 触发错误的用户
        """
        embed = discord.Embed(
            title="⚖️ 队列公平性限制",
            description="您已经有歌曲在队列中，请等待播放完成后再添加新歌曲。",
            color=discord.Color.orange()
        )

        embed.add_field(
            name="📋 队列规则",
            value="为了保证所有用户的公平使用，每位用户同时只能有一首歌曲在队列中等待播放。",
            inline=False
        )

        # 尝试获取用户的详细队列状态信息
        try:
            # 显示用户特定的队列状态（仅对成员用户）
            if hasattr(self.music_player, '_playback_engine') and message.guild and isinstance(user, discord.Member):
                user_queue_service = UserQueueStatusService(self.music_player._playback_engine)

                # 获取用户的详细队列信息
                user_info = user_queue_service.get_user_queue_info(user, message.guild.id)

                if user_info.has_queued_song:
                    if user_info.is_currently_playing:
                        embed.add_field(
                            name="🎶 您的歌曲状态",
                            value=f"**{user_info.queued_song_title}** 正在播放中",
                            inline=False
                        )
                    else:
                        status_text = f"**{user_info.queued_song_title}**"
                        if user_info.queue_position:
                            status_text += f"\n📍 队列位置: 第 {user_info.queue_position} 位"
                        if user_info.estimated_play_time_seconds is not None:
                            status_text += f"\n⏰ 预计播放时间: {user_info.format_estimated_time()} 后"

                        embed.add_field(
                            name="🎶 您的排队歌曲",
                            value=status_text,
                            inline=False
                        )

            # 显示通用队列状态（对所有用户）
            if message.guild:
                queue_info = await self.music_player.get_queue_info(message.guild.id)
                if queue_info:
                    embed.add_field(
                        name="📊 当前队列状态",
                        value=f"队列长度: {queue_info.get('queue_length', 0)} 首歌曲",
                        inline=True
                    )

        except Exception as e:
            self.logger.debug(f"获取详细队列状态信息失败: {e}")
            # 如果获取详细信息失败，显示基本信息
            try:
                if hasattr(self.music_player, 'get_queue_info') and message.guild:
                    queue_info = await self.music_player.get_queue_info(message.guild.id)
                    if queue_info:
                        embed.add_field(
                            name="📊 当前队列状态",
                            value=f"队列长度: {queue_info.get('queue_length', 0)} 首歌曲",
                            inline=True
                        )
            except Exception:
                pass  # 忽略获取队列信息的错误

        embed.add_field(
            name="💡 建议",
            value="使用 `!music my` 命令查看您当前的队列状态和预计播放时间。",
            inline=False
        )

        await message.edit(content=None, embed=embed)

    async def _send_currently_playing_embed(self, message: discord.Message, error_message: str) -> None:
        """
        Send currently playing error embed message.

        Args:
            message: Message to edit
            error_message: Currently playing error message
        """
        embed = discord.Embed(
            title="🎵 歌曲正在播放",
            description=error_message,
            color=discord.Color.blue()
        )
        embed.add_field(
            name="🎧 当前状态",
            value="您的歌曲正在播放中，请耐心等待播放完成。",
            inline=False
        )
        embed.add_field(
            name="⏭️ 下一步",
            value="歌曲播放完成后，您就可以添加新的歌曲了。",
            inline=False
        )
        await message.edit(content=None, embed=embed)

    async def _send_song_too_long_embed(self, message: discord.Message, error_message: str) -> None:
        """
        Send song too long error embed message.

        Args:
            message: Message to edit
            error_message: Song too long error message
        """
        embed = discord.Embed(
            title="⏱️ 歌曲时长超限",
            description=error_message,
            color=discord.Color.red()
        )
        embed.add_field(
            name="📏 时长限制说明",
            value="为了确保队列的流畅性和公平性，系统限制了单首歌曲的最大时长。",
            inline=False
        )
        embed.add_field(
            name="💡 建议",
            value="请尝试寻找该歌曲的较短版本，或选择其他歌曲。",
            inline=False
        )
        embed.add_field(
            name="🎵 替代方案",
            value="• 寻找歌曲的单曲版本而非专辑版本\n• 选择官方版本而非扩展混音版本\n• 考虑添加歌曲的精华片段",
            inline=False
        )
        await message.edit(content=None, embed=embed)

    async def persistence_status(self, ctx: commands.Context) -> None:
        """
        显示队列持久化状态信息

        Args:
            ctx: Discord 命令上下文
        """
        if not self._enabled:
            await ctx.send("❌ 音乐功能已禁用")
            return

        try:
            # 获取持久化统计信息
            if hasattr(self.music_player, 'queue_persistence') and self.music_player.queue_persistence:
                stats = self.music_player.queue_persistence.get_persistence_stats()

                embed = discord.Embed(
                    title="📊 队列持久化状态",
                    color=discord.Color.blue()
                )

                embed.add_field(
                    name="🔧 基本信息",
                    value=f"持久化已启用: ✅\n"
                          f"数据目录: `{stats.get('data_directory', 'N/A')}`\n"
                          f"自动保存: {'✅' if stats.get('auto_save_enabled', False) else '❌'}",
                    inline=False
                )

                embed.add_field(
                    name="📈 统计信息",
                    value=f"活动队列: {len(self.music_player._queue_managers)}\n"
                          f"队列文件: {stats.get('queue_files', 0)}\n"
                          f"播放任务: {len(self.music_player._playback_tasks)}",
                    inline=True
                )

                embed.add_field(
                    name="💾 存储信息",
                    value=f"缓存服务器: {stats.get('cached_guilds', 0)}\n"
                          f"备份文件: {stats.get('backup_files', 0)}",
                    inline=True
                )

            else:
                embed = discord.Embed(
                    title="📊 队列持久化状态",
                    description="❌ 队列持久化未启用",
                    color=discord.Color.orange()
                )

            await ctx.send(embed=embed)

        except Exception as e:
            self.logger.error(f"获取持久化状态失败: {e}")
            await ctx.send("❌ 获取持久化状态时发生错误")

    async def cleanup(self) -> None:
        """Clean up music commands resources."""
        if hasattr(self, 'progress_bar'):
            await self.progress_bar.cleanup_all_progress_bars()
            self.logger.debug("Music commands cleanup completed")
