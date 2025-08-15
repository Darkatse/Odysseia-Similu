"""
队列管理命令实现

处理队列管理相关的Slash命令：
- 队列状态显示
- 用户个人队列查询
- 队列统计信息
"""

import logging
from typing import Any
import discord

from ..core.base_command import BaseSlashCommand
from ..ui.message_visibility import MessageVisibility, MessageType
from similubot.utils.config_manager import ConfigManager
from similubot.queue.user_queue_status import UserQueueStatusService


class QueueManagementCommands(BaseSlashCommand):
    """
    队列管理命令处理器

    负责处理队列显示和用户状态查询功能
    """

    def __init__(self, config: ConfigManager, music_player: Any):
        """
        初始化队列管理命令

        Args:
            config: 配置管理器
            music_player: 音乐播放器实例
        """
        super().__init__(config, music_player)

        # 初始化消息可见性控制器
        self.message_visibility = MessageVisibility()

        self.logger.debug("队列管理命令已初始化")

    async def execute(self, interaction: discord.Interaction, **kwargs) -> None:
        """
        执行队列管理命令

        Args:
            interaction: Discord交互对象
            **kwargs: 命令参数
        """
        # 默认显示队列状态
        await self.handle_queue_display(interaction)

    async def handle_queue_display(self, interaction: discord.Interaction) -> None:
        """
        处理队列显示命令

        Args:
            interaction: Discord交互对象
        """
        try:
            # 检查前置条件
            if not await self.check_prerequisites(interaction):
                return

            self.logger.debug(f"显示队列 - 用户: {interaction.user.display_name}")

            # 获取队列信息
            queue_info = await self.music_player.get_queue_info(interaction.guild.id)

            if queue_info["is_empty"] and not queue_info["current_song"]:
                embed = discord.Embed(
                    title="🎵 音乐队列",
                    description="队列为空",
                    color=discord.Color.blue()
                )
                # 队列状态查询是ephemeral消息
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            embed = discord.Embed(
                title="🎵 音乐队列",
                color=discord.Color.blue()
            )

            # 添加当前歌曲信息
            if queue_info["current_song"]:
                current = queue_info["current_song"]
                embed.add_field(
                    name="🎶 正在播放",
                    value=f"**{current.title}**\n"
                          f"时长: {self._format_duration(current.duration)}\n"
                          f"点歌人: {current.requester.display_name}",
                    inline=False
                )

            # 添加队列信息
            if not queue_info["is_empty"]:
                queue_manager = self.music_player.get_queue_manager(interaction.guild.id)
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
                        value=queue_text[:1024],  # Discord字段限制
                        inline=False
                    )

                # 添加队列统计
                total_duration = self._format_duration(queue_info["total_duration"])
                embed.add_field(
                    name="📊 队列统计",
                    value=f"歌曲数量: {queue_info['queue_length']}\n"
                          f"总时长: {total_duration}",
                    inline=True
                )

            # 添加语音连接信息
            if queue_info["connected"]:
                embed.add_field(
                    name="🔊 语音状态",
                    value=f"频道: {queue_info['channel']}\n"
                          f"播放中: {'是' if queue_info['playing'] else '否'}\n"
                          f"已暂停: {'是' if queue_info['paused'] else '否'}",
                    inline=True
                )

            # 队列状态查询是ephemeral消息
            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            self.logger.error(f"显示队列失败: {e}", exc_info=True)
            await self.handle_command_error(interaction, e)

    async def handle_user_queue_status(self, interaction: discord.Interaction) -> None:
        """
        处理用户队列状态查询命令

        Args:
            interaction: Discord交互对象
        """
        try:
            # 检查前置条件
            if not await self.check_prerequisites(interaction):
                return

            self.logger.debug(f"查询用户队列状态 - 用户: {interaction.user.display_name}")

            # 检查播放引擎是否可用
            if not hasattr(self.music_player, '_playback_engine'):
                await self.send_error_response(
                    interaction,
                    "音乐播放器未正确初始化",
                    ephemeral=True
                )
                return

            # 创建用户队列状态服务
            user_queue_service = UserQueueStatusService(self.music_player._playback_engine)

            # 获取用户队列信息
            user_info = user_queue_service.get_user_queue_info(interaction.user, interaction.guild.id)

            # 创建响应嵌入消息
            if not user_info.has_queued_song:
                embed = discord.Embed(
                    title="🎵 我的队列状态",
                    description="您当前没有歌曲在队列中。",
                    color=discord.Color.blue()
                )
                embed.add_field(
                    name="💡 提示",
                    value="使用 `/点歌` 命令来添加歌曲到队列。",
                    inline=False
                )
            else:
                # 用户有歌曲在队列中
                if user_info.is_currently_playing:
                    embed = discord.Embed(
                        title="🎵 我的队列状态",
                        description="您的歌曲正在播放中！",
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

            # 个人队列状态是ephemeral消息
            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            self.logger.error(f"查询用户队列状态失败: {e}", exc_info=True)
            await self.handle_command_error(interaction, e)

    def _format_duration(self, duration_seconds: int) -> str:
        """
        格式化时长显示

        Args:
            duration_seconds: 时长（秒）

        Returns:
            格式化的时长字符串
        """
        if duration_seconds < 60:
            return f"{duration_seconds}秒"
        elif duration_seconds < 3600:
            minutes = duration_seconds // 60
            seconds = duration_seconds % 60
            return f"{minutes}:{seconds:02d}"
        else:
            hours = duration_seconds // 3600
            minutes = (duration_seconds % 3600) // 60
            seconds = duration_seconds % 60
            return f"{hours}:{minutes:02d}:{seconds:02d}"