"""
消息可见性控制

管理Discord消息的可见性策略：
- Ephemeral消息（仅用户可见）
- Public消息（所有用户可见）
- 上下文感知的可见性决策
"""

import logging
from enum import Enum
from typing import Optional
import discord


class MessageType(Enum):
    """消息类型枚举"""
    ERROR = "error"
    SUCCESS = "success"
    WARNING = "warning"
    INFO = "info"
    SONG_ADDED = "song_added"
    QUEUE_STATUS = "queue_status"
    USER_QUEUE_STATUS = "user_queue_status"
    PROGRESS = "progress"
    SKIP_VOTE = "skip_vote"
    LYRICS = "lyrics"
    HELP = "help"


class MessageVisibility:
    """
    消息可见性控制器

    根据消息类型和上下文决定消息的可见性策略
    """

    def __init__(self):
        """初始化消息可见性控制器"""
        self.logger = logging.getLogger("similubot.app_commands.message_visibility")

        # 定义消息类型的默认可见性策略
        self._visibility_rules = {
            # Ephemeral消息（仅用户可见）
            MessageType.ERROR: True,
            MessageType.WARNING: True,
            MessageType.USER_QUEUE_STATUS: True,
            MessageType.HELP: True,

            # Public消息（所有用户可见）
            MessageType.SUCCESS: False,
            MessageType.SONG_ADDED: False,
            MessageType.QUEUE_STATUS: False,
            MessageType.PROGRESS: False,
            MessageType.SKIP_VOTE: False,
            MessageType.LYRICS: False,
            MessageType.INFO: False
        }

    def should_be_ephemeral(
        self,
        message_type: MessageType,
        context: Optional[dict] = None
    ) -> bool:
        """
        判断消息是否应该是ephemeral（仅用户可见）

        Args:
            message_type: 消息类型
            context: 上下文信息

        Returns:
            True if should be ephemeral, False if should be public
        """
        try:
            # 获取默认规则
            default_ephemeral = self._visibility_rules.get(message_type, True)

            # 应用上下文特定的规则
            if context:
                return self._apply_context_rules(message_type, default_ephemeral, context)

            return default_ephemeral

        except Exception as e:
            self.logger.error(f"判断消息可见性失败: {e}")
            # 出错时默认为ephemeral，更安全
            return True

    def _apply_context_rules(
        self,
        message_type: MessageType,
        default_ephemeral: bool,
        context: dict
    ) -> bool:
        """
        应用上下文特定的可见性规则

        Args:
            message_type: 消息类型
            default_ephemeral: 默认可见性
            context: 上下文信息

        Returns:
            最终的可见性决策
        """
        # 错误消息的特殊规则
        if message_type == MessageType.ERROR:
            # 如果是队列公平性错误，可能需要public显示
            error_type = context.get('error_type')
            if error_type == 'queue_fairness':
                # 队列公平性错误通常是ephemeral的
                return True
            elif error_type == 'permission':
                # 权限错误应该是ephemeral的
                return True
            elif error_type == 'system':
                # 系统错误可能需要public显示以便管理员注意
                return context.get('show_to_all', default_ephemeral)

        # 成功消息的特殊规则
        elif message_type == MessageType.SUCCESS:
            # 歌曲添加成功应该是public的
            if context.get('action') == 'song_added':
                return False
            # 其他成功消息可能是ephemeral的
            elif context.get('personal_action', False):
                return True

        # 信息消息的特殊规则
        elif message_type == MessageType.INFO:
            # 队列状态应该是public的
            if context.get('info_type') == 'queue_status':
                return False
            # 个人信息应该是ephemeral的
            elif context.get('info_type') == 'personal':
                return True

        # 进度消息的特殊规则
        elif message_type == MessageType.PROGRESS:
            # 如果是响应个人查询，可能是ephemeral的
            if context.get('personal_request', False):
                return True
            # 否则是public的
            return False

        return default_ephemeral

    async def send_message(
        self,
        interaction: discord.Interaction,
        embed: discord.Embed,
        message_type: MessageType,
        context: Optional[dict] = None,
        view: Optional[discord.ui.View] = None
    ) -> Optional[discord.Message]:
        """
        发送消息并自动应用可见性策略

        Args:
            interaction: Discord交互对象
            embed: 嵌入消息
            message_type: 消息类型
            context: 上下文信息
            view: 可选的视图组件

        Returns:
            发送的消息对象或None
        """
        try:
            ephemeral = self.should_be_ephemeral(message_type, context)

            self.logger.debug(
                f"发送消息 - 类型: {message_type.value}, "
                f"Ephemeral: {ephemeral}, "
                f"用户: {interaction.user.display_name}"
            )

            if interaction.response.is_done():
                return await interaction.followup.send(
                    embed=embed,
                    ephemeral=ephemeral,
                    view=view
                )
            else:
                await interaction.response.send_message(
                    embed=embed,
                    ephemeral=ephemeral,
                    view=view
                )
                return await interaction.original_response()

        except Exception as e:
            self.logger.error(f"发送消息失败: {e}", exc_info=True)
            return None

    def get_visibility_info(self, message_type: MessageType) -> dict:
        """
        获取消息类型的可见性信息

        Args:
            message_type: 消息类型

        Returns:
            可见性信息字典
        """
        ephemeral = self._visibility_rules.get(message_type, True)

        return {
            'message_type': message_type.value,
            'default_ephemeral': ephemeral,
            'visibility': 'ephemeral' if ephemeral else 'public',
            'description': self._get_visibility_description(message_type, ephemeral)
        }

    def _get_visibility_description(self, message_type: MessageType, ephemeral: bool) -> str:
        """
        获取可见性描述

        Args:
            message_type: 消息类型
            ephemeral: 是否为ephemeral

        Returns:
            可见性描述
        """
        if ephemeral:
            return "仅命令发起者可见"
        else:
            return "频道内所有用户可见"