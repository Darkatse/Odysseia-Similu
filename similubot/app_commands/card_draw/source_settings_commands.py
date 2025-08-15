"""
抽卡来源设置命令实现

处理 /设置抽卡来源 Slash命令：
- 全局池/个人池/指定用户池切换
- 用户设置持久化
- 设置状态查询
"""

import logging
from typing import Any, Optional
import discord
from discord import app_commands

from ..core.base_command import BaseSlashCommand
from ..ui.message_visibility import MessageVisibility, MessageType
from similubot.utils.config_manager import ConfigManager

from .database import SongHistoryDatabase
from .random_selector import RandomSongSelector, CardDrawSource, CardDrawConfig


class SourceSettingsCommands(BaseSlashCommand):
    """
    抽卡来源设置命令处理器
    
    负责处理 /设置抽卡来源 命令
    """
    
    def __init__(
        self, 
        config: ConfigManager, 
        music_player: Any,
        database: SongHistoryDatabase,
        selector: RandomSongSelector
    ):
        """
        初始化设置命令处理器
        
        Args:
            config: 配置管理器
            music_player: 音乐播放器实例
            database: 歌曲历史数据库
            selector: 随机选择器
        """
        super().__init__(config, music_player)
        self.database = database
        self.selector = selector
        
        # 用户设置存储（实际应该使用数据库）
        self._user_settings = {}
        
        # 初始化消息可见性控制器
        self.message_visibility = MessageVisibility()
        
        self.logger.debug("抽卡来源设置命令处理器已初始化")
    
    async def execute(self, interaction: discord.Interaction, **kwargs) -> None:
        """
        执行设置抽卡来源命令
        
        Args:
            interaction: Discord交互对象
            **kwargs: 命令参数，应包含 'source' 和可选的 'target_user'
        """
        try:
            source_type = kwargs.get('source', 'global')
            target_user = kwargs.get('target_user')
            
            await self._handle_source_setting(interaction, source_type, target_user)
            
        except Exception as e:
            self.logger.error(f"执行设置抽卡来源命令失败: {e}", exc_info=True)
            await self.handle_command_error(interaction, e)
    
    async def _handle_source_setting(
        self, 
        interaction: discord.Interaction, 
        source_type: str,
        target_user: Optional[discord.Member]
    ) -> None:
        """
        处理来源设置逻辑
        
        Args:
            interaction: Discord交互对象
            source_type: 来源类型字符串
            target_user: 目标用户（当设置为指定用户池时）
        """
        guild_id = interaction.guild.id if interaction.guild else 0
        user_id = interaction.user.id
        
        # 解析来源类型
        if source_type == 'global':
            card_source = CardDrawSource.GLOBAL
            target_user_id = None
        elif source_type == 'personal':
            card_source = CardDrawSource.PERSONAL
            target_user_id = None
        elif source_type == 'specific_user':
            if not target_user:
                await self._send_error_message(
                    interaction, 
                    "设置指定用户池时必须选择目标用户"
                )
                return
            card_source = CardDrawSource.SPECIFIC_USER
            target_user_id = target_user.id
        else:
            await self._send_error_message(interaction, f"无效的来源类型: {source_type}")
            return
        
        # 验证设置的有效性
        validation_result = await self._validate_source_setting(
            guild_id, card_source, target_user_id
        )
        
        if not validation_result['valid']:
            await self._send_error_message(interaction, validation_result['message'])
            return
        
        # 保存用户设置
        await self._save_user_setting(user_id, card_source, target_user_id)
        
        # 发送确认消息
        await self._send_confirmation_message(
            interaction, card_source, target_user, validation_result['stats']
        )
    
    async def _validate_source_setting(
        self, 
        guild_id: int, 
        source: CardDrawSource, 
        target_user_id: Optional[int]
    ) -> dict:
        """
        验证来源设置的有效性
        
        Args:
            guild_id: 服务器ID
            source: 抽卡来源
            target_user_id: 目标用户ID
            
        Returns:
            验证结果字典
        """
        try:
            if source == CardDrawSource.GLOBAL:
                total_count = await self.database.get_total_song_count(guild_id)
                if total_count == 0:
                    return {
                        'valid': False,
                        'message': "服务器内还没有歌曲历史记录，请先使用 `/点歌` 命令添加一些歌曲"
                    }
                return {
                    'valid': True,
                    'stats': {'total_songs': total_count, 'source_name': '全局池'}
                }
                
            elif source == CardDrawSource.PERSONAL:
                # 个人池验证在实际抽卡时进行
                return {
                    'valid': True,
                    'stats': {'source_name': '个人池'}
                }
                
            elif source == CardDrawSource.SPECIFIC_USER:
                if not target_user_id:
                    return {
                        'valid': False,
                        'message': "指定用户池需要提供目标用户"
                    }
                
                user_count = await self.database.get_user_song_count(guild_id, target_user_id)
                if user_count == 0:
                    return {
                        'valid': False,
                        'message': "指定用户还没有歌曲历史记录"
                    }
                
                return {
                    'valid': True,
                    'stats': {
                        'total_songs': user_count, 
                        'source_name': '指定用户池',
                        'target_user_id': target_user_id
                    }
                }
            
            return {'valid': False, 'message': '未知的来源类型'}
            
        except Exception as e:
            self.logger.error(f"验证来源设置失败: {e}", exc_info=True)
            return {'valid': False, 'message': '验证设置时发生错误'}
    
    async def _save_user_setting(
        self, 
        user_id: int, 
        source: CardDrawSource, 
        target_user_id: Optional[int]
    ) -> None:
        """
        保存用户设置
        
        Args:
            user_id: 用户ID
            source: 抽卡来源
            target_user_id: 目标用户ID
        """
        # 这里应该保存到数据库，暂时使用内存存储
        self._user_settings[user_id] = {
            'source': source,
            'target_user_id': target_user_id
        }
        
        self.logger.debug(f"保存用户抽卡设置 - 用户: {user_id}, 来源: {source}")
    
    async def get_user_setting(self, user_id: int) -> CardDrawConfig:
        """
        获取用户的抽卡设置
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户抽卡配置
        """
        setting = self._user_settings.get(user_id)
        if not setting:
            # 返回默认设置
            card_draw_config = self.config.get('card_draw', {})
            return CardDrawConfig(
                source=CardDrawSource.GLOBAL,
                max_redraws=card_draw_config.get('max_redraws', 3),
                timeout_seconds=card_draw_config.get('timeout_seconds', 60)
            )
        
        card_draw_config = self.config.get('card_draw', {})
        return CardDrawConfig(
            source=setting['source'],
            target_user_id=setting['target_user_id'],
            max_redraws=card_draw_config.get('max_redraws', 3),
            timeout_seconds=card_draw_config.get('timeout_seconds', 60)
        )
    
    async def _send_confirmation_message(
        self, 
        interaction: discord.Interaction, 
        source: CardDrawSource,
        target_user: Optional[discord.Member],
        stats: dict
    ) -> None:
        """发送设置确认消息"""
        source_names = {
            CardDrawSource.GLOBAL: "全局池",
            CardDrawSource.PERSONAL: "个人池",
            CardDrawSource.SPECIFIC_USER: "指定用户池"
        }
        
        source_name = source_names.get(source, "未知")
        
        embed = discord.Embed(
            title="✅ 抽卡来源设置成功",
            description=f"已将抽卡来源设置为：**{source_name}**",
            color=discord.Color.green()
        )
        
        # 添加详细信息
        if source == CardDrawSource.GLOBAL:
            embed.add_field(
                name="📊 池子信息",
                value=f"包含服务器内所有用户的 {stats.get('total_songs', 0)} 首歌曲",
                inline=False
            )
        elif source == CardDrawSource.PERSONAL:
            embed.add_field(
                name="📊 池子信息",
                value="将从您个人的歌曲历史中抽取",
                inline=False
            )
        elif source == CardDrawSource.SPECIFIC_USER and target_user:
            embed.add_field(
                name="📊 池子信息",
                value=f"将从 {target_user.display_name} 的 {stats.get('total_songs', 0)} 首歌曲中抽取",
                inline=False
            )
        
        embed.add_field(
            name="💡 提示",
            value="现在可以使用 `/随机抽卡` 命令开始抽卡了！",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def _send_error_message(
        self, 
        interaction: discord.Interaction, 
        message: str
    ) -> None:
        """发送错误消息"""
        embed = discord.Embed(
            title="❌ 设置失败",
            description=message,
            color=discord.Color.red()
        )
        
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
