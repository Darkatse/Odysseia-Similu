"""
Discord按钮交互系统 - 处理用户与按钮的交互

提供可重用的按钮视图类和交互回调处理，支持：
- 确认/拒绝按钮
- 多选按钮(1-5)
- 退出按钮
- 60秒超时机制
"""

import logging
import asyncio
from typing import Optional, List, Callable, Any, Dict
from enum import Enum
import discord
from discord.ext import commands

from similubot.core.interfaces import NetEaseSearchResult


class InteractionResult(Enum):
    """交互结果枚举"""
    CONFIRMED = "confirmed"
    DENIED = "denied"
    SELECTED = "selected"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    REPLACED = "replaced"  # 新增：用于歌曲替换确认


class SearchConfirmationView(discord.ui.View):
    """
    搜索确认视图 - 显示确认/拒绝按钮

    用于用户确认或拒绝最佳搜索结果。
    只有发起搜索的用户可以与此界面交互。
    """

    def __init__(self, search_result: NetEaseSearchResult, user: discord.abc.User, timeout: float = 60.0):
        """
        初始化搜索确认视图

        Args:
            search_result: 搜索结果
            user: 发起搜索的用户
            timeout: 超时时间（秒）
        """
        super().__init__(timeout=timeout)
        self.search_result = search_result
        self.user = user  # 只有此用户可以交互
        self.result: Optional[InteractionResult] = None
        self.selected_result: Optional[NetEaseSearchResult] = None
        self.logger = logging.getLogger("similubot.ui.search_confirmation")
    
    @discord.ui.button(label="✅ 确认", style=discord.ButtonStyle.green, custom_id="confirm")
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """确认按钮回调"""
        try:
            # 验证用户权限
            if interaction.user.id != self.user.id:
                await interaction.response.send_message(
                    f"❌ 只有 {self.user.display_name} 可以操作此搜索结果",
                    ephemeral=True
                )
                return

            self.logger.debug(f"用户 {interaction.user.display_name} 确认了搜索结果: {self.search_result.title}")

            self.result = InteractionResult.CONFIRMED
            self.selected_result = self.search_result
            
            # 禁用所有按钮
            for item in self.children:
                item.disabled = True
            
            # 更新消息
            embed = discord.Embed(
                title="✅ 已确认",
                description=f"正在添加歌曲到队列: **{self.search_result.get_display_name()}**",
                color=discord.Color.green()
            )
            
            await interaction.response.edit_message(embed=embed, view=self)
            self.stop()
            
        except Exception as e:
            self.logger.error(f"处理确认按钮时出错: {e}", exc_info=True)
            await interaction.response.send_message("❌ 处理确认时出错", ephemeral=True)
    
    @discord.ui.button(label="❌ 不是这首，展示更多", style=discord.ButtonStyle.red, custom_id="deny")
    async def deny_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """拒绝按钮回调"""
        try:
            # 验证用户权限
            if interaction.user.id != self.user.id:
                await interaction.response.send_message(
                    f"❌ 只有 {self.user.display_name} 可以操作此搜索结果",
                    ephemeral=True
                )
                return

            self.logger.debug(f"用户 {interaction.user.display_name} 拒绝了搜索结果: {self.search_result.title}")

            self.result = InteractionResult.DENIED
            
            # 禁用所有按钮
            for item in self.children:
                item.disabled = True
            
            # 更新消息
            embed = discord.Embed(
                title="❌ 已拒绝",
                description="正在显示更多搜索结果...",
                color=discord.Color.orange()
            )
            
            await interaction.response.edit_message(embed=embed, view=self)
            self.stop()
            
        except Exception as e:
            self.logger.error(f"处理拒绝按钮时出错: {e}", exc_info=True)
            await interaction.response.send_message("❌ 处理拒绝时出错", ephemeral=True)
    
    async def on_timeout(self):
        """超时处理"""
        self.logger.debug("搜索确认视图超时")
        self.result = InteractionResult.TIMEOUT
        
        # 禁用所有按钮
        for item in self.children:
            item.disabled = True


class SearchSelectionView(discord.ui.View):
    """
    搜索选择视图 - 显示多个搜索结果供用户选择

    用于用户从多个搜索结果中选择一个。
    只有发起搜索的用户可以与此界面交互。
    """

    def __init__(self, search_results: List[NetEaseSearchResult], user: discord.abc.User, timeout: float = 60.0):
        """
        初始化搜索选择视图

        Args:
            search_results: 搜索结果列表（最多5个）
            user: 发起搜索的用户
            timeout: 超时时间（秒）
        """
        super().__init__(timeout=timeout)
        self.search_results = search_results[:5]  # 限制最多5个结果
        self.user = user  # 只有此用户可以交互
        self.result: Optional[InteractionResult] = None
        self.selected_result: Optional[NetEaseSearchResult] = None
        self.logger = logging.getLogger("similubot.ui.search_selection")
        
        # 动态添加选择按钮
        for i, result in enumerate(self.search_results):
            button = discord.ui.Button(
                label=f"{i+1}",
                style=discord.ButtonStyle.primary,
                custom_id=f"select_{i}"
            )
            button.callback = self._create_select_callback(i, result)
            self.add_item(button)
    
    def _create_select_callback(self, index: int, result: NetEaseSearchResult):
        """创建选择按钮的回调函数"""
        async def select_callback(interaction: discord.Interaction):
            try:
                # 验证用户权限
                if interaction.user.id != self.user.id:
                    await interaction.response.send_message(
                        f"❌ 只有 {self.user.display_name} 可以操作此搜索结果",
                        ephemeral=True
                    )
                    return

                self.logger.debug(f"用户 {interaction.user.display_name} 选择了结果 {index+1}: {result.title}")

                self.result = InteractionResult.SELECTED
                self.selected_result = result
                
                # 禁用所有按钮
                for item in self.children:
                    item.disabled = True
                
                # 更新消息
                embed = discord.Embed(
                    title="✅ 已选择",
                    description=f"正在添加歌曲到队列: **{result.get_display_name()}**",
                    color=discord.Color.green()
                )
                
                await interaction.response.edit_message(embed=embed, view=self)
                self.stop()
                
            except Exception as e:
                self.logger.error(f"处理选择按钮时出错: {e}", exc_info=True)
                await interaction.response.send_message("❌ 处理选择时出错", ephemeral=True)
        
        return select_callback
    
    @discord.ui.button(label="🚫 退出", style=discord.ButtonStyle.secondary, custom_id="cancel")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """取消按钮回调"""
        try:
            # 验证用户权限
            if interaction.user.id != self.user.id:
                await interaction.response.send_message(
                    f"❌ 只有 {self.user.display_name} 可以操作此搜索结果",
                    ephemeral=True
                )
                return

            self.logger.debug(f"用户 {interaction.user.display_name} 取消了搜索选择")

            self.result = InteractionResult.CANCELLED
            
            # 禁用所有按钮
            for item in self.children:
                item.disabled = True
            
            # 更新消息
            embed = discord.Embed(
                title="🚫 已取消",
                description="搜索已取消",
                color=discord.Color.light_grey()
            )
            
            await interaction.response.edit_message(embed=embed, view=self)
            self.stop()
            
        except Exception as e:
            self.logger.error(f"处理取消按钮时出错: {e}", exc_info=True)
            await interaction.response.send_message("❌ 处理取消时出错", ephemeral=True)
    
    async def on_timeout(self):
        """超时处理"""
        self.logger.debug("搜索选择视图超时")
        self.result = InteractionResult.TIMEOUT
        
        # 禁用所有按钮
        for item in self.children:
            item.disabled = True


class InteractionManager:
    """
    交互管理器 - 管理按钮交互的生命周期
    
    提供高级接口来处理搜索确认和选择流程。
    """
    
    def __init__(self):
        """初始化交互管理器"""
        self.logger = logging.getLogger("similubot.ui.interaction_manager")
    
    async def show_search_confirmation(
        self, 
        ctx: commands.Context, 
        search_result: NetEaseSearchResult,
        timeout: float = 60.0
    ) -> tuple[InteractionResult, Optional[NetEaseSearchResult]]:
        """
        显示搜索确认界面
        
        Args:
            ctx: Discord命令上下文
            search_result: 搜索结果
            timeout: 超时时间（秒）
            
        Returns:
            (交互结果, 选择的搜索结果)
        """
        try:
            # 创建确认视图
            view = SearchConfirmationView(search_result, ctx.author, timeout)

            # 创建嵌入消息
            embed = self._create_confirmation_embed(search_result, ctx.author)

            # 发送消息
            message = await ctx.send(embed=embed, view=view)
            
            # 等待用户交互
            await view.wait()
            
            # 处理超时
            if view.result == InteractionResult.TIMEOUT:
                embed = discord.Embed(
                    title="⏰ 超时",
                    description="搜索确认已超时",
                    color=discord.Color.light_grey()
                )
                await message.edit(embed=embed, view=view)
            
            return view.result or InteractionResult.TIMEOUT, view.selected_result
            
        except Exception as e:
            self.logger.error(f"显示搜索确认时出错: {e}", exc_info=True)
            return InteractionResult.TIMEOUT, None
    
    async def show_search_selection(
        self, 
        ctx: commands.Context, 
        search_results: List[NetEaseSearchResult],
        timeout: float = 60.0
    ) -> tuple[InteractionResult, Optional[NetEaseSearchResult]]:
        """
        显示搜索选择界面
        
        Args:
            ctx: Discord命令上下文
            search_results: 搜索结果列表
            timeout: 超时时间（秒）
            
        Returns:
            (交互结果, 选择的搜索结果)
        """
        try:
            # 创建选择视图
            view = SearchSelectionView(search_results, ctx.author, timeout)

            # 创建嵌入消息
            embed = self._create_selection_embed(search_results, ctx.author)

            # 发送消息
            message = await ctx.send(embed=embed, view=view)
            
            # 等待用户交互
            await view.wait()
            
            # 处理超时
            if view.result == InteractionResult.TIMEOUT:
                embed = discord.Embed(
                    title="⏰ 超时",
                    description="搜索选择已超时",
                    color=discord.Color.light_grey()
                )
                await message.edit(embed=embed, view=view)
            
            return view.result or InteractionResult.TIMEOUT, view.selected_result
            
        except Exception as e:
            self.logger.error(f"显示搜索选择时出错: {e}", exc_info=True)
            return InteractionResult.TIMEOUT, None

    async def show_queue_fairness_replacement(
        self,
        ctx: commands.Context,
        new_song_title: str,
        existing_song_title: str,
        queue_position: int,
        timeout: float = 60.0
    ) -> tuple[InteractionResult, None]:
        """
        显示队列公平性歌曲替换界面

        Args:
            ctx: Discord命令上下文
            new_song_title: 新歌曲标题
            existing_song_title: 现有歌曲标题
            queue_position: 现有歌曲在队列中的位置
            timeout: 超时时间（秒）

        Returns:
            (交互结果, None)
        """
        try:
            # 创建替换视图
            view = QueueFairnessReplacementView(
                ctx.author, new_song_title, existing_song_title, queue_position, timeout
            )

            # 创建嵌入消息
            embed = self._create_queue_fairness_embed(
                ctx.author, new_song_title, existing_song_title, queue_position
            )

            # 发送消息
            message = await ctx.send(embed=embed, view=view)

            # 等待用户交互
            await view.wait()

            # 处理超时
            if view.result == InteractionResult.TIMEOUT:
                embed = discord.Embed(
                    title="⏰ 超时",
                    description="歌曲替换选择已超时，保持现有歌曲在队列中。",
                    color=discord.Color.light_grey()
                )
                await message.edit(embed=embed, view=view)

            return view.result or InteractionResult.TIMEOUT, None

        except Exception as e:
            self.logger.error(f"显示队列公平性替换界面时出错: {e}", exc_info=True)
            return InteractionResult.TIMEOUT, None

    def _create_confirmation_embed(self, search_result: NetEaseSearchResult, user: discord.abc.User) -> discord.Embed:
        """
        创建搜索确认嵌入消息

        Args:
            search_result: 搜索结果
            user: 发起搜索的用户

        Returns:
            Discord嵌入消息
        """
        embed = discord.Embed(
            title="🎵 找到歌曲",
            description=f"是否添加这首歌曲到队列？",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="歌曲信息",
            value=f"**{search_result.get_display_name()}**\n专辑: {search_result.album}",
            inline=False
        )

        if search_result.duration:
            embed.add_field(
                name="时长",
                value=search_result.format_duration(),
                inline=True
            )

        if search_result.cover_url:
            embed.set_thumbnail(url=search_result.cover_url)

        embed.set_footer(text=f"请在60秒内选择 • 只有 {user.display_name} 可以操作此界面")

        return embed

    def _create_selection_embed(self, search_results: List[NetEaseSearchResult], user: discord.abc.User) -> discord.Embed:
        """
        创建搜索选择嵌入消息

        Args:
            search_results: 搜索结果列表
            user: 发起搜索的用户

        Returns:
            Discord嵌入消息
        """
        embed = discord.Embed(
            title="🎵 搜索结果",
            description="请选择要添加到队列的歌曲：",
            color=discord.Color.blue()
        )

        # 添加搜索结果
        results_text = ""
        for i, result in enumerate(search_results[:5]):
            duration_text = f" ({result.format_duration()})" if result.duration else ""
            results_text += f"**{i+1}.** {result.get_display_name()}{duration_text}\n"
            if result.album and result.album != result.title:
                results_text += f"    专辑: {result.album}\n"
            results_text += "\n"

        embed.add_field(
            name="可选歌曲",
            value=results_text.strip(),
            inline=False
        )

        embed.set_footer(text=f"请在60秒内选择 • 只有 {user.display_name} 可以操作此界面")

        return embed

    def _create_queue_fairness_embed(
        self,
        user: discord.abc.User,
        new_song_title: str,
        existing_song_title: str,
        queue_position: int
    ) -> discord.Embed:
        """
        创建队列公平性替换嵌入消息

        Args:
            user: 发起请求的用户
            new_song_title: 新歌曲标题
            existing_song_title: 现有歌曲标题
            queue_position: 现有歌曲在队列中的位置

        Returns:
            Discord嵌入消息
        """
        embed = discord.Embed(
            title="⚖️ 队列公平性限制",
            description="您已经有歌曲在队列中。是否要替换现有歌曲？",
            color=discord.Color.orange()
        )

        embed.add_field(
            name="🎵 您想添加的歌曲",
            value=f"**{new_song_title}**",
            inline=False
        )

        embed.add_field(
            name="🎶 您现有的队列歌曲",
            value=f"**{existing_song_title}**\n📍 队列位置: 第 {queue_position} 位",
            inline=False
        )

        embed.add_field(
            name="📋 队列规则",
            value="为了保证所有用户的公平使用，每位用户同时只能有一首歌曲在队列中等待播放。",
            inline=False
        )

        embed.add_field(
            name="💡 选择说明",
            value="• **是，替换现有歌曲**：用新歌曲替换现有歌曲，保持相同的队列位置\n"
                  "• **不，保持现有歌曲**：取消添加新歌曲，保持现有歌曲不变",
            inline=False
        )

        embed.set_footer(text=f"请在60秒内选择 • 只有 {user.display_name} 可以操作此界面")

        return embed


class QueueFairnessReplacementView(discord.ui.View):
    """
    队列公平性歌曲替换视图 - 显示替换/取消按钮

    当用户已有歌曲在队列中时，提供替换现有歌曲的选项。
    只有发起请求的用户可以与此界面交互。
    """

    def __init__(self, user: discord.abc.User, new_song_title: str, existing_song_title: str,
                 queue_position: int, timeout: float = 60.0):
        """
        初始化队列公平性替换视图

        Args:
            user: 发起请求的用户
            new_song_title: 新歌曲标题
            existing_song_title: 现有歌曲标题
            queue_position: 现有歌曲在队列中的位置
            timeout: 超时时间（秒）
        """
        super().__init__(timeout=timeout)
        self.user = user  # 只有此用户可以交互
        self.new_song_title = new_song_title
        self.existing_song_title = existing_song_title
        self.queue_position = queue_position
        self.result: Optional[InteractionResult] = None
        self.logger = logging.getLogger("similubot.ui.queue_fairness_replacement")

    @discord.ui.button(label="✅ 是，替换现有歌曲", style=discord.ButtonStyle.green, custom_id="replace_confirm")
    async def replace_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """替换确认按钮回调"""
        try:
            # 验证用户权限
            if interaction.user.id != self.user.id:
                await interaction.response.send_message(
                    f"❌ 只有 {self.user.display_name} 可以操作此界面",
                    ephemeral=True
                )
                return

            self.logger.debug(
                f"用户 {interaction.user.display_name} 确认替换歌曲: "
                f"{self.existing_song_title} -> {self.new_song_title}"
            )

            self.result = InteractionResult.REPLACED

            # 禁用所有按钮
            for item in self.children:
                if hasattr(item, 'disabled'):
                    item.disabled = True

            # 更新消息
            embed = discord.Embed(
                title="✅ 正在替换歌曲",
                description=f"正在将您的歌曲 **{self.existing_song_title}** 替换为 **{self.new_song_title}**...",
                color=discord.Color.green()
            )

            await interaction.response.edit_message(embed=embed, view=self)
            self.stop()

        except Exception as e:
            self.logger.error(f"处理替换确认按钮时出错: {e}", exc_info=True)
            await interaction.response.send_message("❌ 处理替换确认时出错", ephemeral=True)

    @discord.ui.button(label="❌ 不，保持现有歌曲", style=discord.ButtonStyle.red, custom_id="replace_deny")
    async def deny_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """拒绝替换按钮回调"""
        try:
            # 验证用户权限
            if interaction.user.id != self.user.id:
                await interaction.response.send_message(
                    f"❌ 只有 {self.user.display_name} 可以操作此界面",
                    ephemeral=True
                )
                return

            self.logger.debug(f"用户 {interaction.user.display_name} 拒绝替换歌曲")

            self.result = InteractionResult.DENIED

            # 禁用所有按钮
            for item in self.children:
                if hasattr(item, 'disabled'):
                    item.disabled = True

            # 更新消息
            embed = discord.Embed(
                title="❌ 已取消",
                description=f"保持您的现有歌曲 **{self.existing_song_title}** 在队列中。",
                color=discord.Color.light_grey()
            )

            await interaction.response.edit_message(embed=embed, view=self)
            self.stop()

        except Exception as e:
            self.logger.error(f"处理拒绝替换按钮时出错: {e}", exc_info=True)
            await interaction.response.send_message("❌ 处理拒绝替换时出错", ephemeral=True)

    async def on_timeout(self):
        """超时处理"""
        self.logger.debug("队列公平性替换视图超时")
        self.result = InteractionResult.TIMEOUT

        # 禁用所有按钮
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True
