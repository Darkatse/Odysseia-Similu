"""
帮助命令

提供机器人信息和使用指南
"""

import logging
from typing import Optional
import discord

from ..core import BaseSlashCommand
from ..ui import EmbedBuilder, MessageVisibility, MessageType
from similubot.utils.config_manager import ConfigManager


class HelpCommand(BaseSlashCommand):
    """
    帮助命令处理器

    显示机器人信息、功能介绍和使用指南。
    结合了原来的about和help命令功能。
    """

    def __init__(self, config: ConfigManager, music_player=None):
        """
        初始化帮助命令

        Args:
            config: 配置管理器
            music_player: 音乐播放器（此命令不需要，保持接口一致性）
        """
        super().__init__(config, music_player)
        self.logger = logging.getLogger("similubot.app_commands.general.help")
        self.message_visibility = MessageVisibility()

    async def handle_help_command(self, interaction: discord.Interaction) -> None:
        """
        处理帮助命令

        Args:
            interaction: Discord交互对象
        """
        self.logger.debug(f"帮助命令被 {interaction.user} 在 {interaction.guild} 中调用")

        # 检查前置条件
        if not await self.check_prerequisites(interaction):
            return

        try:
            # 创建主要的帮助嵌入消息
            embed = discord.Embed(
                title="🎵 Odysseia-Similu 音乐机器人",
                description="专为类脑/Odysseia Discord 社区打造的音乐播放机器人",
                color=discord.Color.blue()
            )

            # Slash Commands 音乐功能
            embed.add_field(
                name="🎶 音乐播放命令",
                value=(
                    "`/点歌 <链接或名字>` - 播放音乐或搜索歌曲\n"
                    "`/歌曲队列` - 显示播放队列\n"
                    "`/歌曲进度` - 显示当前播放进度\n"
                    "`/歌曲跳过` - 跳过当前歌曲\n"
                    "`/我的队列` - 查看个人队列状态"
                ),
                inline=False
            )

            # 随机抽卡功能
            embed.add_field(
                name="🎲 随机抽卡命令",
                value=(
                    "`/随机抽卡` - 从歌曲历史中随机抽取一首歌曲\n"
                    "`/设置抽卡来源` - 设置抽卡的歌曲来源池"
                ),
                inline=False
            )

            # 通用命令
            embed.add_field(
                name="📋 通用命令",
                value=(
                    "`/帮助` - 显示此帮助信息\n"
                    "`/延迟` - 检查机器人延迟和连接质量"
                ),
                inline=False
            )

            # 支持的音频格式和来源
            embed.add_field(
                name="🎧 支持的音频来源",
                value=(
                    "• **YouTube** - 视频音频播放\n"
                    "• **NetEase云音乐** - 搜索和播放\n"
                    "• **Catbox** - 音频文件播放\n"
                    "• **Bilibili** - 视频音频播放\n"
                    "• **直接链接** - MP3, WAV, OGG, M4A, FLAC, AAC, OPUS, WMA"
                ),
                inline=False
            )

            # 机器人配置信息
            embed.add_field(
                name="⚙️ 配置信息",
                value=(
                    f"最大队列长度: {self.config.get('music.max_queue_size', 100)}\n"
                    f"最大歌曲时长: {self.config.get('music.max_song_duration', 3600)} 秒\n"
                    f"自动断开超时: {self.config.get('music.auto_disconnect_timeout', 300)} 秒"
                ),
                inline=True
            )

            # 机器人统计信息
            if interaction.client.guilds:
                guild_count = len(interaction.client.guilds)
                user_count = sum(guild.member_count or 0 for guild in interaction.client.guilds)
                embed.add_field(
                    name="📊 统计信息",
                    value=f"服务器数量: {guild_count}\n用户数量: {user_count}",
                    inline=True
                )

            # 项目链接
            embed.add_field(
                name="🔗 项目链接",
                value="[GitHub](https://github.com/Darkatse/Odysseia-Similu) • [类脑社区](https://discord.gg/odysseia)",
                inline=True
            )

            # 功能特性
            embed.add_field(
                name="✨ 功能特性",
                value=(
                    "🎵 智能音乐搜索和播放\n"
                    "📋 完整的音乐队列管理\n"
                    "🎯 实时播放进度显示\n"
                    "⚖️ 队列公平性保证\n"
                    "🗳️ 智能跳过投票系统\n"
                    "🎨 美观的交互界面"
                ),
                inline=False
            )

            embed.set_footer(text="Odysseia-Similu 音乐机器人 • 基于 Python & discord.py")
            embed.timestamp = discord.utils.utcnow()

            # 发送响应（ephemeral，因为是帮助信息）
            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            self.logger.error(f"帮助命令中的意外错误: {e}", exc_info=True)
            error_embed = EmbedBuilder.create_error_embed(
                "帮助信息加载失败",
                "获取帮助信息时发生错误。"
            )

            if interaction.response.is_done():
                await interaction.followup.send(embed=error_embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=error_embed, ephemeral=True)

    async def execute(self, interaction: discord.Interaction, **kwargs) -> None:
        """
        执行帮助命令

        Args:
            interaction: Discord交互对象
            **kwargs: 额外参数
        """
        await self.handle_help_command(interaction)