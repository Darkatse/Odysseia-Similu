"""
交互处理器

提供统一的用户交互处理功能：
- 按钮交互管理
- 选择菜单处理
- 超时处理
- 权限验证
"""

import asyncio
import logging
from typing import Optional, Callable, Any, Union
import discord
from discord.ext import commands

from .embed_builder import EmbedBuilder


class InteractionHandler:
    """
    交互处理器

    管理Discord交互组件的生命周期和事件处理
    """

    def __init__(self):
        """初始化交互处理器"""
        self.logger = logging.getLogger("similubot.app_commands.interaction_handler")
        self._active_interactions = {}

    async def create_confirmation_view(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        confirm_label: str = "确认",
        cancel_label: str = "取消",
        timeout: float = 60.0
    ) -> Optional[bool]:
        """
        创建确认对话框

        Args:
            interaction: Discord交互对象
            title: 标题
            description: 描述
            confirm_label: 确认按钮标签
            cancel_label: 取消按钮标签
            timeout: 超时时间（秒）

        Returns:
            True if confirmed, False if cancelled, None if timeout
        """
        try:
            embed = EmbedBuilder.create_info_embed(title, description)

            view = ConfirmationView(
                confirm_label=confirm_label,
                cancel_label=cancel_label,
                timeout=timeout,
                user_id=interaction.user.id
            )

            if interaction.response.is_done():
                message = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
                message = await interaction.original_response()

            # 等待用户响应
            await view.wait()

            # 禁用按钮
            for item in view.children:
                item.disabled = True

            try:
                await message.edit(view=view)
            except discord.NotFound:
                pass

            return view.result

        except Exception as e:
            self.logger.error(f"创建确认对话框失败: {e}", exc_info=True)
            return None

    async def create_selection_view(
        self,
        interaction: discord.Interaction,
        title: str,
        options: list,
        placeholder: str = "请选择一个选项",
        timeout: float = 60.0
    ) -> Optional[Any]:
        """
        创建选择菜单

        Args:
            interaction: Discord交互对象
            title: 标题
            options: 选项列表
            placeholder: 占位符文本
            timeout: 超时时间（秒）

        Returns:
            选中的选项或None
        """
        try:
            embed = EmbedBuilder.create_info_embed(title, "请从下方选择一个选项：")

            view = SelectionView(
                options=options,
                placeholder=placeholder,
                timeout=timeout,
                user_id=interaction.user.id
            )

            if interaction.response.is_done():
                message = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
                message = await interaction.original_response()

            # 等待用户响应
            await view.wait()

            # 禁用选择菜单
            for item in view.children:
                item.disabled = True

            try:
                await message.edit(view=view)
            except discord.NotFound:
                pass

            return view.selected_option

        except Exception as e:
            self.logger.error(f"创建选择菜单失败: {e}", exc_info=True)
            return None

    def register_interaction(self, interaction_id: str, handler: Callable) -> None:
        """
        注册交互处理器

        Args:
            interaction_id: 交互ID
            handler: 处理函数
        """
        self._active_interactions[interaction_id] = handler

    def unregister_interaction(self, interaction_id: str) -> None:
        """
        注销交互处理器

        Args:
            interaction_id: 交互ID
        """
        self._active_interactions.pop(interaction_id, None)

    async def handle_interaction(self, interaction: discord.Interaction) -> bool:
        """
        处理交互事件

        Args:
            interaction: Discord交互对象

        Returns:
            True if handled, False otherwise
        """
        try:
            custom_id = interaction.data.get('custom_id')
            if not custom_id:
                return False

            handler = self._active_interactions.get(custom_id)
            if not handler:
                return False

            await handler(interaction)
            return True

        except Exception as e:
            self.logger.error(f"处理交互失败: {e}", exc_info=True)
            return False


class ConfirmationView(discord.ui.View):
    """确认对话框视图"""

    def __init__(
        self,
        confirm_label: str = "确认",
        cancel_label: str = "取消",
        timeout: float = 60.0,
        user_id: int = None
    ):
        super().__init__(timeout=timeout)
        self.result: Optional[bool] = None
        self.user_id = user_id

        # 添加确认按钮
        self.confirm_button = discord.ui.Button(
            label=confirm_label,
            style=discord.ButtonStyle.green,
            emoji="✅"
        )
        self.confirm_button.callback = self._confirm_callback
        self.add_item(self.confirm_button)

        # 添加取消按钮
        self.cancel_button = discord.ui.Button(
            label=cancel_label,
            style=discord.ButtonStyle.red,
            emoji="❌"
        )
        self.cancel_button.callback = self._cancel_callback
        self.add_item(self.cancel_button)

    async def _confirm_callback(self, interaction: discord.Interaction):
        """确认按钮回调"""
        if self.user_id and interaction.user.id != self.user_id:
            await interaction.response.send_message("只有命令发起者可以操作此界面。", ephemeral=True)
            return

        self.result = True
        await interaction.response.defer()
        self.stop()

    async def _cancel_callback(self, interaction: discord.Interaction):
        """取消按钮回调"""
        if self.user_id and interaction.user.id != self.user_id:
            await interaction.response.send_message("只有命令发起者可以操作此界面。", ephemeral=True)
            return

        self.result = False
        await interaction.response.defer()
        self.stop()

    async def on_timeout(self):
        """超时处理"""
        self.result = None


class SelectionView(discord.ui.View):
    """选择菜单视图"""

    def __init__(
        self,
        options: list,
        placeholder: str = "请选择一个选项",
        timeout: float = 60.0,
        user_id: int = None
    ):
        super().__init__(timeout=timeout)
        self.selected_option: Optional[Any] = None
        self.user_id = user_id

        # 创建选择菜单
        select_options = []
        for i, option in enumerate(options[:25]):  # Discord限制最多25个选项
            if isinstance(option, dict):
                select_options.append(discord.SelectOption(
                    label=option.get('label', f'选项 {i+1}'),
                    description=option.get('description', ''),
                    value=str(i),
                    emoji=option.get('emoji')
                ))
            else:
                select_options.append(discord.SelectOption(
                    label=str(option),
                    value=str(i)
                ))

        self.select_menu = discord.ui.Select(
            placeholder=placeholder,
            options=select_options
        )
        self.select_menu.callback = self._select_callback
        self.add_item(self.select_menu)

        # 保存原始选项用于返回
        self.options = options

    async def _select_callback(self, interaction: discord.Interaction):
        """选择菜单回调"""
        if self.user_id and interaction.user.id != self.user_id:
            await interaction.response.send_message("只有命令发起者可以操作此界面。", ephemeral=True)
            return

        selected_index = int(self.select_menu.values[0])
        self.selected_option = self.options[selected_index]

        await interaction.response.defer()
        self.stop()

    async def on_timeout(self):
        """超时处理"""
        self.selected_option = None