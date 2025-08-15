"""
随机抽卡命令实现

处理 /随机抽卡 Slash命令：
- 随机歌曲选择和展示
- 用户交互（满意/重新抽取按钮）
- 超时处理
- 队列集成
"""

import logging
import asyncio
from typing import Any, Optional, Dict
import discord
from discord import app_commands

from ..core.base_command import BaseSlashCommand
from ..ui.message_visibility import MessageVisibility, MessageType
from similubot.utils.config_manager import ConfigManager
from similubot.core.interfaces import AudioInfo
from similubot.progress.discord_updater import DiscordProgressUpdater

from .database import SongHistoryDatabase, SongHistoryEntry
from .random_selector import RandomSongSelector, CardDrawConfig, CardDrawSource


class CardDrawView(discord.ui.View):
    """抽卡交互视图"""
    
    def __init__(
        self, 
        command_handler: 'CardDrawCommands',
        song_entry: SongHistoryEntry,
        user_id: int,
        config: CardDrawConfig,
        remaining_redraws: int
    ):
        super().__init__(timeout=config.timeout_seconds)
        self.command_handler = command_handler
        self.song_entry = song_entry
        self.user_id = user_id
        self.config = config
        self.remaining_redraws = remaining_redraws
        self.logger = logging.getLogger("similubot.card_draw.view")
    
    @discord.ui.button(label="满意", style=discord.ButtonStyle.green, emoji="✅")
    async def confirm_song(self, interaction: discord.Interaction, button: discord.ui.Button):
        """确认选择当前歌曲"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 只有抽卡者可以操作", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        # 添加歌曲到队列
        success = await self.command_handler._add_song_to_queue(interaction, self.song_entry)
        
        if success:
            # 更新消息显示确认状态
            embed = self._create_confirmed_embed()
            await interaction.edit_original_response(embed=embed, view=None)
        
        self.stop()
    
    @discord.ui.button(label="重新抽取", style=discord.ButtonStyle.secondary, emoji="🔄")
    async def redraw_song(self, interaction: discord.Interaction, button: discord.ui.Button):
        """重新抽取歌曲"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 只有抽卡者可以操作", ephemeral=True)
            return
        
        if self.remaining_redraws <= 0:
            await interaction.response.send_message("❌ 已达到最大重抽次数", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        # 执行重新抽取
        await self.command_handler._handle_redraw(
            interaction, 
            self.config, 
            self.remaining_redraws - 1
        )
        
        self.stop()
    
    def _create_confirmed_embed(self) -> discord.Embed:
        """创建确认选择的嵌入消息"""
        embed = discord.Embed(
            title="🎵 抽卡完成",
            description=f"已将 **{self.song_entry.title}** 添加到播放队列",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="歌曲信息",
            value=(
                f"**标题**: {self.song_entry.title}\n"
                f"**艺术家**: {self.song_entry.artist}\n"
                f"**时长**: {self._format_duration(self.song_entry.duration)}\n"
                f"**来源**: {self.song_entry.source_platform}"
            ),
            inline=False
        )
        
        embed.add_field(
            name="原点歌者",
            value=f"<@{self.song_entry.user_id}>",
            inline=True
        )
        
        if self.song_entry.thumbnail_url:
            embed.set_thumbnail(url=self.song_entry.thumbnail_url)
        
        embed.set_footer(text="歌曲已添加到队列")
        return embed
    
    def _format_duration(self, duration: int) -> str:
        """格式化时长"""
        minutes = duration // 60
        seconds = duration % 60
        return f"{minutes}:{seconds:02d}"
    
    async def on_timeout(self):
        """处理超时"""
        self.logger.debug("抽卡交互超时")


class CardDrawCommands(BaseSlashCommand):
    """
    随机抽卡命令处理器
    
    负责处理 /随机抽卡 命令的完整流程
    """
    
    def __init__(
        self, 
        config: ConfigManager, 
        music_player: Any,
        database: SongHistoryDatabase,
        selector: RandomSongSelector
    ):
        """
        初始化抽卡命令处理器
        
        Args:
            config: 配置管理器
            music_player: 音乐播放器实例
            database: 歌曲历史数据库
            selector: 随机选择器
        """
        super().__init__(config, music_player)
        self.database = database
        self.selector = selector
        
        # 初始化消息可见性控制器
        self.message_visibility = MessageVisibility()
        
        self.logger.debug("随机抽卡命令处理器已初始化")
    
    async def execute(self, interaction: discord.Interaction, **kwargs) -> None:
        """
        执行随机抽卡命令
        
        Args:
            interaction: Discord交互对象
            **kwargs: 命令参数
        """
        try:
            # 检查前置条件
            if not await self.check_prerequisites(interaction):
                return
            
            # 获取用户的抽卡配置（这里使用默认配置，实际应从用户设置中获取）
            config = await self._get_user_card_draw_config(interaction.user.id)
            
            # 执行抽卡
            await self._handle_card_draw(interaction, config, config.max_redraws)
            
        except Exception as e:
            self.logger.error(f"执行随机抽卡命令失败: {e}", exc_info=True)
            await self.handle_command_error(interaction, e)
    
    async def _handle_card_draw(
        self, 
        interaction: discord.Interaction, 
        config: CardDrawConfig,
        remaining_redraws: int
    ) -> None:
        """
        处理抽卡逻辑
        
        Args:
            interaction: Discord交互对象
            config: 抽卡配置
            remaining_redraws: 剩余重抽次数
        """
        guild_id = interaction.guild.id if interaction.guild else 0
        
        # 获取候选歌曲并选择
        if config.source == CardDrawSource.PERSONAL:
            candidates = await self.selector.get_candidates_for_user(
                guild_id, interaction.user.id, config
            )
        else:
            candidates = await self.selector._get_candidates(guild_id, config)
        
        if not candidates:
            await self._send_no_songs_message(interaction, config)
            return
        
        # 随机选择歌曲
        selected_song = self.selector._weighted_random_selection(candidates)
        
        # 创建展示嵌入消息
        embed = self._create_card_draw_embed(selected_song, remaining_redraws)
        
        # 创建交互视图
        view = CardDrawView(
            self, selected_song, interaction.user.id, config, remaining_redraws
        )
        
        # 发送消息
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=view)
        else:
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def _handle_redraw(
        self,
        interaction: discord.Interaction,
        config: CardDrawConfig,
        remaining_redraws: int
    ) -> None:
        """处理重新抽取"""
        await self._handle_card_draw(interaction, config, remaining_redraws)

    def _create_card_draw_embed(
        self,
        song_entry: SongHistoryEntry,
        remaining_redraws: int
    ) -> discord.Embed:
        """
        创建抽卡结果嵌入消息

        Args:
            song_entry: 选中的歌曲记录
            remaining_redraws: 剩余重抽次数

        Returns:
            Discord嵌入消息
        """
        embed = discord.Embed(
            title="🎲 随机抽卡结果",
            description=f"为您抽取到了这首歌曲：",
            color=discord.Color.blue()
        )

        # 歌曲基本信息
        embed.add_field(
            name="🎵 歌曲信息",
            value=(
                f"**标题**: {song_entry.title}\n"
                f"**艺术家**: {song_entry.artist}\n"
                f"**时长**: {self._format_duration(song_entry.duration)}\n"
                f"**来源**: {song_entry.source_platform}"
            ),
            inline=False
        )

        # 原点歌者信息
        embed.add_field(
            name="👤 原点歌者",
            value=f"<@{song_entry.user_id}>",
            inline=True
        )

        # 添加时间信息
        embed.add_field(
            name="📅 添加时间",
            value=song_entry.timestamp.strftime("%Y-%m-%d %H:%M"),
            inline=True
        )

        # 重抽信息
        if remaining_redraws > 0:
            embed.add_field(
                name="🔄 重抽机会",
                value=f"剩余 {remaining_redraws} 次",
                inline=True
            )

        # 设置缩略图
        if song_entry.thumbnail_url:
            embed.set_thumbnail(url=song_entry.thumbnail_url)

        embed.set_footer(text="请选择是否满意此结果，或重新抽取")
        return embed

    async def _send_no_songs_message(
        self,
        interaction: discord.Interaction,
        config: CardDrawConfig
    ) -> None:
        """发送没有可用歌曲的消息"""
        source_name = {
            CardDrawSource.GLOBAL: "全局歌曲池",
            CardDrawSource.PERSONAL: "个人歌曲池",
            CardDrawSource.SPECIFIC_USER: "指定用户歌曲池"
        }.get(config.source, "歌曲池")

        embed = discord.Embed(
            title="❌ 抽卡失败",
            description=f"{source_name}中没有可用的歌曲",
            color=discord.Color.orange()
        )

        embed.add_field(
            name="💡 建议",
            value="请先使用 `/点歌` 命令添加一些歌曲到队列，建立歌曲历史记录",
            inline=False
        )

        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=None)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _add_song_to_queue(
        self,
        interaction: discord.Interaction,
        song_entry: SongHistoryEntry
    ) -> bool:
        """
        将选中的歌曲添加到播放队列

        Args:
            interaction: Discord交互对象
            song_entry: 歌曲记录

        Returns:
            添加是否成功
        """
        try:
            # 检查语音频道连接
            if not await self.check_voice_channel(interaction):
                return False

            # 连接到用户的语音频道
            success, error = await self.music_player.connect_to_user_channel(interaction.user)
            if not success:
                await self.send_error_response(interaction, f"无法连接到语音频道: {error}")
                return False

            # 设置文本频道用于事件通知
            if hasattr(self.music_player, '_playback_engine') and interaction.guild:
                self.music_player._playback_engine.set_text_channel(
                    interaction.guild.id,
                    interaction.channel.id
                )

            # 创建AudioInfo对象
            audio_info = AudioInfo(
                title=song_entry.title,
                duration=song_entry.duration,
                url=song_entry.url,
                uploader=song_entry.artist,
                thumbnail_url=song_entry.thumbnail_url,
                file_format=song_entry.file_format
            )

            # 创建进度更新器
            progress_updater = DiscordProgressUpdater(interaction)
            progress_callback = progress_updater.create_callback()

            # 添加到队列
            success, position, error = await self.music_player.add_song_to_queue(
                song_entry.url, interaction.user, progress_callback
            )

            if success:
                self.logger.info(f"抽卡歌曲添加到队列成功 - 位置: {position}, 歌曲: {song_entry.title}")

                # 触发公共通知（抽卡来源）
                await self._trigger_public_notification(interaction, audio_info, position, "抽卡")

                return True
            else:
                self.logger.error(f"抽卡歌曲添加到队列失败: {error}")
                await self.send_error_response(interaction, f"添加歌曲到队列失败: {error}")
                return False

        except Exception as e:
            self.logger.error(f"添加抽卡歌曲到队列时发生异常: {e}", exc_info=True)
            await self.send_error_response(interaction, "添加歌曲时发生错误")
            return False

    async def _trigger_public_notification(
        self,
        interaction: discord.Interaction,
        audio_info: AudioInfo,
        position: int,
        source_type: str
    ) -> None:
        """
        触发公共歌曲添加通知

        Args:
            interaction: Discord交互对象
            audio_info: 音频信息
            position: 队列位置
            source_type: 来源类型
        """
        try:
            # 检查是否有有效的服务器
            if not interaction.guild:
                self.logger.warning("无法获取服务器信息，跳过公共通知")
                return

            # 获取播放引擎实例
            if hasattr(self.music_player, '_playback_engine'):
                playback_engine = self.music_player._playback_engine
                await playback_engine._trigger_song_added_notification(
                    interaction.guild.id, audio_info, position, source_type, interaction.user
                )
            else:
                self.logger.warning("无法获取播放引擎实例，跳过公共通知")

        except Exception as e:
            self.logger.error(f"触发公共通知失败: {e}", exc_info=True)

    async def _get_user_card_draw_config(self, user_id: int) -> CardDrawConfig:
        """
        获取用户的抽卡配置

        Args:
            user_id: 用户ID

        Returns:
            用户抽卡配置
        """
        # 这里应该从数据库或配置文件中读取用户设置
        # 暂时返回默认配置
        card_draw_config = self.config.get('card_draw', {})

        return CardDrawConfig(
            source=CardDrawSource.GLOBAL,  # 默认全局池
            max_redraws=card_draw_config.get('max_redraws', 3),
            timeout_seconds=card_draw_config.get('timeout_seconds', 60)
        )

    def _format_duration(self, duration: int) -> str:
        """格式化时长为可读字符串"""
        minutes = duration // 60
        seconds = duration % 60
        return f"{minutes}:{seconds:02d}"
