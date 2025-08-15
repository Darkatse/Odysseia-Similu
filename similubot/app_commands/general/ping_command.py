"""
延迟检测命令

提供机器人延迟和连接质量检测功能
"""

import time
import logging
from typing import Optional
import discord

from ..core import BaseSlashCommand
from ..ui import EmbedBuilder, MessageVisibility, MessageType
from similubot.utils.config_manager import ConfigManager


class PingCommand(BaseSlashCommand):
    """
    延迟检测命令处理器

    检测机器人的Discord API延迟和WebSocket延迟，
    提供连接质量评估和网络诊断信息。
    """

    def __init__(self, config: ConfigManager, music_player=None):
        """
        初始化延迟检测命令

        Args:
            config: 配置管理器
            music_player: 音乐播放器（此命令不需要，保持接口一致性）
        """
        super().__init__(config, music_player)
        self.logger = logging.getLogger("similubot.app_commands.general.ping")
        self.message_visibility = MessageVisibility()

    async def handle_ping_command(self, interaction: discord.Interaction) -> None:
        """
        处理延迟检测命令

        Args:
            interaction: Discord交互对象
        """
        self.logger.debug(f"延迟命令被 {interaction.user} 在 {interaction.guild} 中调用")

        # 检查前置条件
        if not await self.check_prerequisites(interaction):
            return

        try:
            # 发送初始响应
            await interaction.response.send_message("🏓 正在测量延迟...", ephemeral=True)

            # 测量API延迟
            api_start = time.perf_counter()

            # 使用轻量级API调用测量响应时间
            if interaction.client.user:
                await interaction.client.fetch_user(interaction.client.user.id)

            api_end = time.perf_counter()
            api_latency_ms = round((api_end - api_start) * 1000, 2)

            # 获取WebSocket延迟（已经是秒，转换为毫秒）
            websocket_latency_ms = round(interaction.client.latency * 1000, 2)

            self.logger.debug(f"测量延迟 - API: {api_latency_ms}ms, WebSocket: {websocket_latency_ms}ms")

            # 确定连接质量和视觉指示器
            api_quality = self._get_latency_quality(api_latency_ms)
            ws_quality = self._get_latency_quality(websocket_latency_ms)

            # 整体质量取两者中较差的
            overall_quality = min(api_quality["level"], ws_quality["level"])
            overall_indicator = self._get_quality_indicator(overall_quality)

            # 创建结果嵌入消息
            embed = discord.Embed(
                title=f"🏓 Pong! {overall_indicator['emoji']}",
                description=f"连接质量: **{overall_indicator['text']}**",
                color=overall_indicator["color"]
            )

            # API延迟字段
            embed.add_field(
                name=f"{api_quality['emoji']} Discord API 延迟",
                value=f"**{api_latency_ms}ms**\n{api_quality['description']}",
                inline=True
            )

            # WebSocket延迟字段
            embed.add_field(
                name=f"{ws_quality['emoji']} WebSocket 延迟",
                value=f"**{websocket_latency_ms}ms**\n{ws_quality['description']}",
                inline=True
            )

            # 添加空字段用于布局
            embed.add_field(name="\u200b", value="\u200b", inline=True)

            # 附加信息
            embed.add_field(
                name="📊 连接详情",
                value=(
                    f"**分片:** {interaction.guild.shard_id if interaction.guild else 'N/A'}\n"
                    f"**网关:** {interaction.client.user.id % 1000 if interaction.client.user else 'N/A'}\n"
                    f"**时间戳:** <t:{int(time.time())}:T>"
                ),
                inline=False
            )

            embed.set_footer(text="Odysseia-Similu 音乐机器人网络诊断")
            embed.timestamp = discord.utils.utcnow()

            # 更新响应
            await interaction.edit_original_response(content=None, embed=embed)

        except discord.HTTPException as e:
            self.logger.warning(f"Discord API错误在延迟命令中: {e}")
            error_embed = EmbedBuilder.create_error_embed(
                "网络错误",
                "由于Discord API问题，无法测量API延迟。"
            )
            error_embed.add_field(
                name="WebSocket延迟",
                value=f"{round(interaction.client.latency * 1000, 2)}ms",
                inline=True
            )
            error_embed.add_field(
                name="错误详情",
                value=f"HTTP {e.status}: {e.text}",
                inline=False
            )

            await interaction.edit_original_response(content=None, embed=error_embed)

        except Exception as e:
            self.logger.error(f"延迟命令中的意外错误: {e}", exc_info=True)
            error_embed = EmbedBuilder.create_error_embed(
                "延迟测试失败",
                "测量延迟时发生意外错误。"
            )
            error_embed.add_field(
                name="错误",
                value=str(e)[:1024],  # 限制错误消息长度
                inline=False
            )

            await interaction.edit_original_response(content=None, embed=error_embed)

    async def execute(self, interaction: discord.Interaction, **kwargs) -> None:
        """
        执行延迟检测命令

        Args:
            interaction: Discord交互对象
            **kwargs: 额外参数
        """
        await self.handle_ping_command(interaction)

    def _get_latency_quality(self, latency_ms: float) -> dict:
        """
        根据延迟确定连接质量

        Args:
            latency_ms: 延迟（毫秒）

        Returns:
            包含质量信息的字典，包括表情符号、描述和等级
        """
        if latency_ms < 0:
            return {
                "emoji": "⚠️",
                "description": "无效测量",
                "level": 0
            }
        elif latency_ms <= 50:
            return {
                "emoji": "🟢",
                "description": "优秀",
                "level": 4
            }
        elif latency_ms <= 100:
            return {
                "emoji": "🟡",
                "description": "良好",
                "level": 3
            }
        elif latency_ms <= 200:
            return {
                "emoji": "🟠",
                "description": "一般",
                "level": 2
            }
        elif latency_ms <= 500:
            return {
                "emoji": "🔴",
                "description": "较差",
                "level": 1
            }
        else:
            return {
                "emoji": "🔴",
                "description": "很差",
                "level": 0
            }

    def _get_quality_indicator(self, quality_level: int) -> dict:
        """
        根据质量等级获取整体质量指示器

        Args:
            quality_level: 质量等级（0-4）

        Returns:
            包含整体质量信息的字典
        """
        if quality_level >= 4:
            return {
                "emoji": "🟢",
                "text": "优秀",
                "color": discord.Color.green()
            }
        elif quality_level >= 3:
            return {
                "emoji": "🟡",
                "text": "良好",
                "color": discord.Color.gold()
            }
        elif quality_level >= 2:
            return {
                "emoji": "🟠",
                "text": "一般",
                "color": discord.Color.orange()
            }
        elif quality_level >= 1:
            return {
                "emoji": "🔴",
                "text": "较差",
                "color": discord.Color.red()
            }
        else:
            return {
                "emoji": "⚠️",
                "text": "严重",
                "color": discord.Color.dark_red()
            }