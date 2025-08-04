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
from similubot.utils.netease_search import search_songs, get_playback_url
from similubot.ui.button_interactions import InteractionManager, InteractionResult
from similubot.ui.skip_vote_poll import VoteManager, VoteResult


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

        # Initialize interaction manager for NetEase search
        self.interaction_manager = InteractionManager()

        # Initialize vote manager for democratic skip voting
        self.vote_manager = VoteManager(config)

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

        usage_examples = [
            "!music <搜索关键词> - 搜索并添加网易云音乐歌曲到队列（默认行为）",
            "!music <youtube链接> - 添加YouTube歌曲到队列并开始播放",
            "!music <catbox音频链接> - 添加Catbox音频文件到队列并开始播放",
            "!music <bilibili链接> - 添加Bilibili视频音频到队列并开始播放",
            "!music <netease链接> - 添加网易云音乐歌曲到队列并开始播放",
            "!music netease <搜索关键词> - 明确指定网易云音乐搜索（与默认行为相同）",
            "!music queue - 显示当前播放队列",
            "!music now - 显示当前歌曲播放进度",
            "!music my - 查看您的队列状态和预计播放时间",
            "!music skip - 跳过当前歌曲（支持民主投票）",
            "!music stop - 停止播放并清空队列",
            "!music jump <数字> - 跳转到队列指定位置",
            "!music seek <时间> - 跳转到指定时间 (例如: 1:30, +30, -1:00)",
            "!music status - 显示队列持久化状态",
            "!music exit - 安全关闭机器人（仅限所有者）"
        ]

        help_text = (
            "音乐播放和队列管理命令。支持网易云音乐搜索（默认）、YouTube视频、Catbox音频文件、Bilibili视频和网易云音乐链接。"
            "使用这些命令前您必须先加入语音频道。直接输入搜索关键词将自动在网易云音乐中搜索。"
        )

        registry.register_command(
            name="music",
            callback=self.music_command,
            description="音乐播放和队列管理",
            required_permission="music",
            usage_examples=usage_examples,
            help_text=help_text
        )

        self.logger.debug("Music commands registered")

    async def music_command(self, ctx: commands.Context, *args) -> None:
        """
        Main music command handler.

        Args:
            ctx: Discord command context
            *args: Command arguments
        """
        if not args:
            await self._show_music_help(ctx)
            return

        subcommand = args[0]

        if subcommand in ["queue", "q"]:
            await self._handle_queue_command(ctx)
        elif subcommand in ["now", "current", "playing"]:
            await self._handle_now_command(ctx)
        elif subcommand in ["my", "mine", "mystatus"]:
            await self._handle_my_command(ctx)
        elif subcommand in ["skip", "next"]:
            await self._handle_skip_command(ctx)
        elif subcommand in ["stop", "disconnect", "leave"]:
            await self._handle_stop_command(ctx)
        elif subcommand in ["jump", "goto"]:
            await self._handle_jump_command(ctx, list(args[1:]))
        elif subcommand in ["seek", "goto_time"]:
            await self._handle_seek_command(ctx, list(args[1:]))
        elif subcommand in ["persistence", "persist", "status"]:
            await self.persistence_status(ctx)
        elif subcommand in ["exit", "quit", "shutdown"]:
            await self._handle_exit_command(ctx)
        elif subcommand in ["netease", "ne", "网易", "网易云"]:
            await self._handle_netease_command(ctx, list(args[1:]))
        elif self.music_player.is_supported_url(subcommand):
            # First argument is a supported audio URL (YouTube, Catbox, Bilibili, or NetEase)
            await self._handle_play_command(ctx, subcommand)
        else:
            # Default behavior: treat as NetEase search query
            # Join all arguments to form the complete search query
            search_query = " ".join(args)
            self.logger.debug(f"默认NetEase搜索: {search_query}")
            await self._handle_netease_command(ctx, args)

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
                # 使用统一的错误处理方法
                await self._handle_queue_addition_error(response, error, ctx.author)
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
        处理跳过歌曲命令 - 支持民主投票系统

        Args:
            ctx: Discord命令上下文
        """
        try:
            # 检查服务器是否存在
            if not ctx.guild:
                await ctx.reply("❌ 此命令只能在服务器中使用")
                return

            # 停止任何活跃的进度条
            self.progress_bar.stop_progress_updates(ctx.guild.id)

            # 获取当前歌曲信息
            queue_info = await self.music_player.get_queue_info(ctx.guild.id)
            current_song = queue_info.get("current_song")

            if not current_song:
                await ctx.reply("❌ 当前没有歌曲在播放")
                return

            self.logger.debug(f"处理跳过命令 - 当前歌曲: {current_song.title}")

            # 获取语音频道成员
            voice_members = self.vote_manager.get_voice_channel_members(ctx)

            if not voice_members:
                await ctx.reply("❌ 机器人未连接到语音频道或无法获取频道成员")
                return

            # 检查是否应该使用投票系统
            if not self.vote_manager.should_use_voting(voice_members):
                # 直接跳过（人数不足或投票系统已禁用）
                self.logger.debug("使用直接跳过模式")
                await self._direct_skip_song(ctx, current_song)
                return

            # 启动民主投票
            self.logger.info(f"启动民主投票跳过 - 歌曲: {current_song.title}, 语音频道人数: {len(voice_members)}")

            # 创建投票完成回调
            async def on_vote_complete(result: VoteResult) -> None:
                """投票完成回调处理"""
                if result == VoteResult.PASSED:
                    # 投票通过，执行跳过
                    self.logger.info(f"投票通过，跳过歌曲: {current_song.title}")
                    await self._execute_skip(ctx.guild.id, current_song.title)
                else:
                    # 投票失败或超时，继续播放
                    self.logger.info(f"投票未通过 ({result.value})，继续播放: {current_song.title}")

            # 启动投票
            result = await self.vote_manager.start_skip_vote(
                ctx=ctx,
                current_song=current_song,
                on_vote_complete=on_vote_complete
            )

            if result is None:
                # 投票启动失败，回退到直接跳过
                self.logger.warning("投票启动失败，回退到直接跳过")
                await self._direct_skip_song(ctx, current_song)

        except Exception as e:
            self.logger.error(f"处理跳过命令时出错: {e}", exc_info=True)
            await ctx.reply("❌ 跳过歌曲时出错")

    async def _direct_skip_song(self, ctx: commands.Context, current_song) -> None:
        """
        直接跳过歌曲（无投票）

        Args:
            ctx: Discord命令上下文
            current_song: 当前歌曲信息
        """
        try:
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
            self.logger.info(f"直接跳过歌曲: {skipped_title}")

        except Exception as e:
            self.logger.error(f"直接跳过歌曲时出错: {e}", exc_info=True)
            await ctx.reply("❌ 跳过歌曲时出错")

    async def _execute_skip(self, guild_id: int, song_title: str) -> None:
        """
        执行歌曲跳过操作

        Args:
            guild_id: 服务器ID
            song_title: 歌曲标题（用于日志）
        """
        try:
            success, skipped_title, error = await self.music_player.skip_current_song(guild_id)

            if success:
                self.logger.info(f"成功跳过歌曲: {skipped_title}")
            else:
                self.logger.error(f"跳过歌曲失败: {error}")

        except Exception as e:
            self.logger.error(f"执行跳过操作时出错: {e}", exc_info=True)

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

    async def _handle_jump_command(self, ctx: commands.Context, args: List[str]) -> None:
        """
        Handle jump command.

        Args:
            ctx: Discord command context
            args: Command arguments
        """
        if not args:
            await ctx.reply("❌ Please specify a queue position number")
            return

        try:
            # Check if guild exists
            if not ctx.guild:
                await ctx.reply("❌ 此命令只能在服务器中使用")
                return

            position = int(args[0])
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

        except ValueError:
            await ctx.reply("❌ 无效的位置数字")
        except Exception as e:
            self.logger.error(f"Error in jump command: {e}", exc_info=True)
            await ctx.reply("❌ 跳转到指定位置时出错")

    async def _handle_seek_command(self, ctx: commands.Context, args: List[str]) -> None:
        """
        Handle seek command.

        Args:
            ctx: Discord command context
            args: Command arguments
        """
        if not args:
            # Show seek command help
            embed = discord.Embed(
                title="🎯 定位命令帮助",
                description="跳转到当前播放歌曲的指定位置",
                color=discord.Color.blue()
            )

            examples = self.music_player.seek_manager.get_seek_examples()
            examples_text = "\n".join(examples)

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
            return

        try:
            # Check if guild exists
            if not ctx.guild:
                await ctx.reply("❌ 此命令只能在服务器中使用")
                return

            time_str = args[0]

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

    async def _show_music_help(self, ctx: commands.Context) -> None:
        """
        显示音乐命令帮助。

        Args:
            ctx: Discord 命令上下文
        """
        embed = discord.Embed(
            title="🎵 音乐命令",
            description="音乐播放和队列管理命令",
            color=discord.Color.blue()
        )

        commands_text = (
            "`!music <搜索关键词>` - 搜索并添加网易云音乐歌曲（默认行为）\n"
            "`!music <youtube链接>` - 添加YouTube歌曲到队列\n"
            "`!music <catbox音频链接>` - 添加Catbox音频文件到队列\n"
            "`!music <bilibili链接>` - 添加Bilibili视频音频到队列\n"
            "`!music <netease链接>` - 添加网易云音乐歌曲到队列\n"
            "`!music netease <搜索关键词>` - 明确指定网易云音乐搜索\n"
            "`!music queue` - 显示当前队列\n"
            "`!music now` - 显示当前歌曲\n"
            "`!music my` - 查看您的队列状态\n"
            "`!music skip` - 投票跳过当前歌曲\n"
            "`!music stop` - 停止播放并清空队列\n"
            "`!music jump <数字>` - 跳转到指定位置\n"
            "`!music seek <时间>` - 跳转到指定时间 (例如: 1:30, +30, -1:00)\n"
            "`!music exit` - 安全关闭机器人（仅限所有者）"
        )

        embed.add_field(
            name="可用命令",
            value=commands_text,
            inline=False
        )

        embed.add_field(
            name="使用要求",
            value="• 您必须先加入语音频道\n• 直接输入搜索关键词将自动在网易云音乐中搜索\n• 也可提供YouTube、Catbox、Bilibili或网易云音乐链接\n• 支持格式: MP3, WAV, OGG, M4A, FLAC, AAC, OPUS, WMA",
            inline=False
        )

        embed.add_field(
            name="使用示例",
            value="`!music 初音未来` - 搜索初音未来的歌曲\n`!music 周杰伦 青花瓷` - 搜索周杰伦的青花瓷\n`!music https://youtu.be/abc123` - 添加YouTube视频\n`!music queue` - 查看播放队列",
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

    async def _handle_netease_command(self, ctx: commands.Context, args: list) -> None:
        """
        处理网易云音乐搜索命令

        Args:
            ctx: Discord命令上下文
            args: 搜索关键词参数列表
        """
        try:
            # 检查用户是否在语音频道
            if not ctx.author.voice or not ctx.author.voice.channel:
                embed = discord.Embed(
                    title="❌ 错误",
                    description="您需要先加入语音频道才能使用音乐命令",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return

            # 检查是否提供了搜索关键词
            if not args:
                embed = discord.Embed(
                    title="❌ 错误",
                    description="请提供搜索关键词\n例如: `!music netease 初音未来`",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return

            # 合并搜索关键词
            search_query = " ".join(args)
            self.logger.debug(f"用户 {ctx.author.display_name} 搜索网易云音乐: {search_query}")

            # 显示搜索中的消息
            searching_embed = discord.Embed(
                title="🔍 搜索中...",
                description=f"正在网易云音乐中搜索: **{search_query}**",
                color=discord.Color.blue()
            )
            searching_message = await ctx.send(embed=searching_embed)

            # 执行搜索
            search_results = await search_songs(search_query, limit=5)

            # 删除搜索中的消息
            try:
                await searching_message.delete()
            except:
                pass  # 忽略删除失败

            if not search_results:
                embed = discord.Embed(
                    title="❌ 未找到结果",
                    description=f"未找到与 **{search_query}** 相关的歌曲",
                    color=discord.Color.orange()
                )
                await ctx.send(embed=embed)
                return

            # 显示第一个结果的确认界面
            first_result = search_results[0]
            interaction_result, selected_result = await self.interaction_manager.show_search_confirmation(
                ctx, first_result, timeout=60.0
            )

            if interaction_result == InteractionResult.CONFIRMED and selected_result:
                # 用户确认了第一个结果，添加到队列
                await self._add_netease_song_to_queue(ctx, selected_result)

            elif interaction_result == InteractionResult.DENIED:
                # 用户拒绝了第一个结果，显示更多选择
                if len(search_results) > 1:
                    interaction_result, selected_result = await self.interaction_manager.show_search_selection(
                        ctx, search_results, timeout=60.0
                    )

                    if interaction_result == InteractionResult.SELECTED and selected_result:
                        # 用户选择了一个结果，添加到队列
                        await self._add_netease_song_to_queue(ctx, selected_result)
                    elif interaction_result == InteractionResult.CANCELLED:
                        # 用户取消了选择
                        self.logger.debug(f"用户 {ctx.author.display_name} 取消了网易云音乐搜索")
                    elif interaction_result == InteractionResult.TIMEOUT:
                        # 选择超时
                        self.logger.debug(f"用户 {ctx.author.display_name} 的网易云音乐选择超时")
                else:
                    # 只有一个结果但被拒绝
                    embed = discord.Embed(
                        title="❌ 已取消",
                        description="搜索已取消",
                        color=discord.Color.light_grey()
                    )
                    await ctx.send(embed=embed)

            elif interaction_result == InteractionResult.TIMEOUT:
                # 确认超时
                self.logger.debug(f"用户 {ctx.author.display_name} 的网易云音乐确认超时")

        except Exception as e:
            self.logger.error(f"处理网易云音乐命令时出错: {e}", exc_info=True)
            embed = discord.Embed(
                title="❌ 错误",
                description="处理网易云音乐搜索时发生错误",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    async def _add_netease_song_to_queue(self, ctx: commands.Context, search_result) -> None:
        """
        将网易云音乐歌曲添加到队列

        Args:
            ctx: Discord命令上下文
            search_result: 网易云搜索结果
        """
        try:
            # 构建网易云音乐播放URL
            playback_url = get_playback_url(search_result.song_id, use_api=True)

            self.logger.debug(f"添加网易云歌曲到队列: {search_result.get_display_name()} - URL: {playback_url}")

            # 创建进度更新器
            progress_updater = DiscordProgressUpdater(ctx)

            # 连接到用户的语音频道
            success, error = await self.music_player.connect_to_user_channel(ctx.author)
            if not success:
                embed = discord.Embed(
                    title="❌ 连接失败",
                    description=f"无法连接到语音频道: {error}",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return

            # 添加歌曲到队列
            success, position, error = await self.music_player.add_song_to_queue(
                playback_url, ctx.author, progress_updater
            )

            if success:
                # 成功添加到队列
                embed = discord.Embed(
                    title="✅ 已添加到队列",
                    description=f"**{search_result.get_display_name()}**",
                    color=discord.Color.green()
                )

                if position:
                    embed.add_field(
                        name="队列位置",
                        value=f"第 {position} 位",
                        inline=True
                    )

                if search_result.duration:
                    embed.add_field(
                        name="时长",
                        value=search_result.format_duration(),
                        inline=True
                    )

                if search_result.cover_url:
                    embed.set_thumbnail(url=search_result.cover_url)

                await ctx.send(embed=embed)

                self.logger.info(f"成功添加网易云歌曲: {search_result.get_display_name()} (位置: {position})")

            else:
                # 添加失败，处理各种错误情况
                await self._handle_queue_addition_error(ctx, error, ctx.author)

        except Exception as e:
            self.logger.error(f"添加网易云歌曲到队列时出错: {e}", exc_info=True)
            embed = discord.Embed(
                title="❌ 添加失败",
                description="添加歌曲到队列时发生错误",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    async def _handle_queue_addition_error(
        self,
        message_or_ctx,
        error_msg: str,
        user: Optional[Union[discord.User, discord.Member]] = None
    ) -> None:
        """
        统一处理队列添加错误的方法

        Args:
            message_or_ctx: Discord消息对象或命令上下文
            error_msg: 错误消息
            user: 触发错误的用户（可选）
        """
        try:
            # 检测对象类型并选择合适的错误处理方法
            # Context对象有send方法但没有edit方法，Message对象有edit方法但没有send方法
            is_context = hasattr(message_or_ctx, 'send') and not hasattr(message_or_ctx, 'edit')

            # 根据错误类型调用相应的专用错误处理方法
            if error_msg and "已经请求了这首歌曲" in error_msg:
                if is_context:
                    await self._send_duplicate_song_embed_ctx(message_or_ctx, error_msg)
                else:
                    await self._send_duplicate_song_embed(message_or_ctx, error_msg)
            elif error_msg and ("已经有" in error_msg and "首歌曲在队列中" in error_msg):
                # 确保user不为None
                if user is None:
                    self.logger.warning("队列公平性错误但用户为None")
                    # 尝试从消息或上下文中获取用户
                    user = getattr(message_or_ctx, 'author', None)
                if user is not None:
                    if is_context:
                        await self._send_queue_fairness_embed_ctx(message_or_ctx, error_msg, user)
                    else:
                        await self._send_queue_fairness_embed(message_or_ctx, error_msg, user)
                else:
                    if is_context:
                        await self._send_error_embed_ctx(message_or_ctx, "队列限制", error_msg)
                    else:
                        await self._send_error_embed(message_or_ctx, "队列限制", error_msg)
            elif error_msg and "正在播放中" in error_msg:
                if is_context:
                    await self._send_currently_playing_embed_ctx(message_or_ctx, error_msg)
                else:
                    await self._send_currently_playing_embed(message_or_ctx, error_msg)
            elif error_msg and "歌曲时长" in error_msg and "超过了最大限制" in error_msg:
                if is_context:
                    await self._send_song_too_long_embed_ctx(message_or_ctx, error_msg)
                else:
                    await self._send_song_too_long_embed(message_or_ctx, error_msg)
            else:
                if is_context:
                    await self._send_error_embed_ctx(message_or_ctx, "添加歌曲失败", error_msg or "未知错误")
                else:
                    await self._send_error_embed(message_or_ctx, "添加歌曲失败", error_msg or "未知错误")

        except Exception as e:
            self.logger.error(f"处理队列错误时出错: {e}", exc_info=True)

    # Context-aware error handling methods (for NetEase integration)
    async def _send_error_embed_ctx(
        self,
        ctx: commands.Context,
        title: str,
        description: str
    ) -> None:
        """
        Send an error embed using Context (for NetEase integration).

        Args:
            ctx: Discord command context
            title: Error title
            description: Error description
        """
        embed = discord.Embed(
            title=f"❌ {title}",
            description=description,
            color=discord.Color.red()
        )

        await ctx.send(embed=embed)

    async def _send_duplicate_song_embed_ctx(self, ctx: commands.Context, error_message: str) -> None:
        """
        Send duplicate song error embed using Context.

        Args:
            ctx: Discord command context
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
        await ctx.send(embed=embed)

    async def _send_queue_fairness_embed_ctx(self, ctx: commands.Context, error_message: str, user: Union[discord.User, discord.Member]) -> None:
        """
        发送队列公平性错误嵌入消息，使用Context对象

        Args:
            ctx: Discord命令上下文
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
            if hasattr(self.music_player, '_playback_engine') and ctx.guild and isinstance(user, discord.Member):
                from similubot.queue.user_queue_status import UserQueueStatusService
                user_queue_service = UserQueueStatusService(self.music_player._playback_engine)

                # 获取用户的详细队列信息
                user_info = user_queue_service.get_user_queue_info(user, ctx.guild.id)

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
            if ctx.guild:
                queue_info = await self.music_player.get_queue_info(ctx.guild.id)
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
                if hasattr(self.music_player, 'get_queue_info') and ctx.guild:
                    queue_info = await self.music_player.get_queue_info(ctx.guild.id)
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

        await ctx.send(embed=embed)

    async def _send_currently_playing_embed_ctx(self, ctx: commands.Context, error_message: str) -> None:
        """
        Send currently playing error embed using Context.

        Args:
            ctx: Discord command context
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
        await ctx.send(embed=embed)

    async def _send_song_too_long_embed_ctx(self, ctx: commands.Context, error_message: str) -> None:
        """
        Send song too long error embed using Context.

        Args:
            ctx: Discord command context
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
        await ctx.send(embed=embed)

    async def cleanup(self) -> None:
        """Clean up music commands resources."""
        if hasattr(self, 'progress_bar'):
            await self.progress_bar.cleanup_all_progress_bars()
            self.logger.debug("Music commands cleanup completed")
