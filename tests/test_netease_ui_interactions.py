"""
网易云音乐UI交互测试 - 测试按钮交互和用户界面

包含搜索确认、选择界面和交互管理器的测试。
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import discord
from discord.ext import commands

from similubot.ui.button_interactions import (
    InteractionManager, InteractionResult, 
    SearchConfirmationView, SearchSelectionView
)
from similubot.core.interfaces import NetEaseSearchResult


class TestSearchConfirmationView:
    """测试搜索确认视图"""

    @pytest.fixture
    def search_result(self):
        """创建搜索结果"""
        return NetEaseSearchResult(
            song_id="517567145",
            title="初登校",
            artist="橋本由香利",
            album="ひなこのーと COMPLETE SOUNDTRACK",
            cover_url="http://example.com/cover.jpg",
            duration=225
        )

    @pytest.fixture
    def mock_user(self):
        """创建模拟的Discord用户"""
        user = Mock(spec=discord.User)
        user.id = 12345
        user.display_name = "TestUser"
        return user

    @pytest.fixture
    def mock_interaction(self, mock_user):
        """创建模拟的Discord交互"""
        interaction = AsyncMock(spec=discord.Interaction)
        interaction.user = mock_user
        interaction.response = AsyncMock()
        return interaction

    @pytest.mark.asyncio
    async def test_view_initialization(self, search_result, mock_user):
        """测试视图初始化"""
        view = SearchConfirmationView(search_result, mock_user, timeout=30.0)

        assert view.search_result == search_result
        assert view.user == mock_user
        assert view.result is None
        assert view.selected_result is None
        assert view.timeout == 30.0
        assert len(view.children) == 2  # 确认和拒绝按钮

    @pytest.mark.asyncio
    async def test_confirm_button_callback(self, search_result, mock_user, mock_interaction):
        """测试确认按钮回调"""
        view = SearchConfirmationView(search_result, mock_user)
        
        # 模拟按钮点击
        button = Mock()
        await view.confirm_button(mock_interaction, button)
        
        # 验证结果
        assert view.result == InteractionResult.CONFIRMED
        assert view.selected_result == search_result
        
        # 验证所有按钮被禁用
        for item in view.children:
            assert item.disabled
        
        # 验证交互响应被调用
        mock_interaction.response.edit_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_deny_button_callback(self, search_result, mock_user, mock_interaction):
        """测试拒绝按钮回调"""
        view = SearchConfirmationView(search_result, mock_user)
        
        # 模拟按钮点击
        button = Mock()
        await view.deny_button(mock_interaction, button)
        
        # 验证结果
        assert view.result == InteractionResult.DENIED
        assert view.selected_result is None
        
        # 验证所有按钮被禁用
        for item in view.children:
            assert item.disabled
        
        # 验证交互响应被调用
        mock_interaction.response.edit_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_timeout_handling(self, search_result, mock_user):
        """测试超时处理"""
        view = SearchConfirmationView(search_result, mock_user, timeout=0.1)
        
        # 等待超时
        await asyncio.sleep(0.2)
        await view.on_timeout()
        
        # 验证结果
        assert view.result == InteractionResult.TIMEOUT
        
        # 验证所有按钮被禁用
        for item in view.children:
            assert item.disabled


class TestSearchSelectionView:
    """测试搜索选择视图"""

    @pytest.fixture
    def search_results(self):
        """创建搜索结果列表"""
        return [
            NetEaseSearchResult("1", "歌曲1", "艺术家1", "专辑1", duration=180),
            NetEaseSearchResult("2", "歌曲2", "艺术家2", "专辑2", duration=200),
            NetEaseSearchResult("3", "歌曲3", "艺术家3", "专辑3", duration=220)
        ]

    @pytest.fixture
    def mock_user(self):
        """创建模拟的Discord用户"""
        user = Mock(spec=discord.User)
        user.id = 12345
        user.display_name = "TestUser"
        return user

    @pytest.fixture
    def mock_interaction(self, mock_user):
        """创建模拟的Discord交互"""
        interaction = AsyncMock(spec=discord.Interaction)
        interaction.user = mock_user
        interaction.response = AsyncMock()
        return interaction

    @pytest.mark.asyncio
    async def test_view_initialization(self, search_results, mock_user):
        """测试视图初始化"""
        view = SearchSelectionView(search_results, mock_user, timeout=30.0)

        assert len(view.search_results) == 3
        assert view.user == mock_user
        assert view.result is None
        assert view.selected_result is None
        assert view.timeout == 30.0
        # 3个选择按钮 + 1个取消按钮
        assert len(view.children) == 4

    @pytest.mark.asyncio
    async def test_view_initialization_limit_results(self, mock_user):
        """测试视图初始化时限制结果数量"""
        # 创建6个结果
        results = [
            NetEaseSearchResult(str(i), f"歌曲{i}", f"艺术家{i}", f"专辑{i}")
            for i in range(6)
        ]

        view = SearchSelectionView(results, mock_user)

        # 应该只保留前5个结果
        assert len(view.search_results) == 5
        # 5个选择按钮 + 1个取消按钮
        assert len(view.children) == 6

    @pytest.mark.asyncio
    async def test_select_button_callback(self, search_results, mock_user, mock_interaction):
        """测试选择按钮回调"""
        view = SearchSelectionView(search_results, mock_user)
        
        # 获取第一个选择按钮的回调
        select_callback = view._create_select_callback(0, search_results[0])
        
        # 模拟按钮点击
        await select_callback(mock_interaction)
        
        # 验证结果
        assert view.result == InteractionResult.SELECTED
        assert view.selected_result == search_results[0]
        
        # 验证所有按钮被禁用
        for item in view.children:
            assert item.disabled
        
        # 验证交互响应被调用
        mock_interaction.response.edit_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_button_callback(self, search_results, mock_user, mock_interaction):
        """测试取消按钮回调"""
        view = SearchSelectionView(search_results, mock_user)
        
        # 模拟取消按钮点击
        button = Mock()
        await view.cancel_button(mock_interaction, button)
        
        # 验证结果
        assert view.result == InteractionResult.CANCELLED
        assert view.selected_result is None
        
        # 验证所有按钮被禁用
        for item in view.children:
            assert item.disabled
        
        # 验证交互响应被调用
        mock_interaction.response.edit_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_timeout_handling(self, search_results, mock_user):
        """测试超时处理"""
        view = SearchSelectionView(search_results, mock_user, timeout=0.1)
        
        # 等待超时
        await asyncio.sleep(0.2)
        await view.on_timeout()
        
        # 验证结果
        assert view.result == InteractionResult.TIMEOUT
        
        # 验证所有按钮被禁用
        for item in view.children:
            assert item.disabled


class TestInteractionManager:
    """测试交互管理器"""

    @pytest.fixture
    def manager(self):
        """创建交互管理器"""
        return InteractionManager()

    @pytest.fixture
    def mock_ctx(self):
        """创建模拟的Discord命令上下文"""
        ctx = AsyncMock(spec=commands.Context)
        ctx.send = AsyncMock()
        return ctx

    @pytest.fixture
    def search_result(self):
        """创建搜索结果"""
        return NetEaseSearchResult(
            song_id="517567145",
            title="初登校",
            artist="橋本由香利",
            album="ひなこのーと COMPLETE SOUNDTRACK",
            cover_url="http://example.com/cover.jpg",
            duration=225
        )

    @pytest.fixture
    def search_results(self):
        """创建搜索结果列表"""
        return [
            NetEaseSearchResult("1", "歌曲1", "艺术家1", "专辑1", duration=180),
            NetEaseSearchResult("2", "歌曲2", "艺术家2", "专辑2", duration=200),
            NetEaseSearchResult("3", "歌曲3", "艺术家3", "专辑3", duration=220)
        ]

    def test_create_confirmation_embed(self, manager, search_result):
        """测试创建确认嵌入消息"""
        mock_user = Mock(spec=discord.User)
        mock_user.display_name = "TestUser"
        embed = manager._create_confirmation_embed(search_result, mock_user)
        
        assert isinstance(embed, discord.Embed)
        assert embed.title == "🎵 找到歌曲"
        assert "是否添加这首歌曲到队列？" in embed.description
        assert embed.color == discord.Color.blue()
        
        # 检查字段
        fields = {field.name: field.value for field in embed.fields}
        assert "歌曲信息" in fields
        assert search_result.get_display_name() in fields["歌曲信息"]
        assert "时长" in fields
        assert search_result.format_duration() in fields["时长"]

    def test_create_selection_embed(self, manager, search_results):
        """测试创建选择嵌入消息"""
        mock_user = Mock(spec=discord.User)
        mock_user.display_name = "TestUser"
        embed = manager._create_selection_embed(search_results, mock_user)
        
        assert isinstance(embed, discord.Embed)
        assert embed.title == "🎵 搜索结果"
        assert "请选择要添加到队列的歌曲：" in embed.description
        assert embed.color == discord.Color.blue()
        
        # 检查字段
        fields = {field.name: field.value for field in embed.fields}
        assert "可选歌曲" in fields
        
        # 检查是否包含所有歌曲
        for i, result in enumerate(search_results):
            assert f"**{i+1}.** {result.get_display_name()}" in fields["可选歌曲"]

    @pytest.mark.asyncio
    async def test_show_search_confirmation_confirmed(self, manager, mock_ctx, search_result):
        """测试显示搜索确认 - 用户确认"""
        # 模拟消息发送
        mock_message = AsyncMock()
        mock_ctx.send.return_value = mock_message
        
        # 模拟视图等待结果
        with patch('similubot.ui.button_interactions.SearchConfirmationView') as mock_view_class:
            mock_view = AsyncMock()
            mock_view.result = InteractionResult.CONFIRMED
            mock_view.selected_result = search_result
            mock_view.wait = AsyncMock()
            mock_view_class.return_value = mock_view
            
            # 执行确认流程
            result, selected = await manager.show_search_confirmation(mock_ctx, search_result)
            
            # 验证结果
            assert result == InteractionResult.CONFIRMED
            assert selected == search_result
            
            # 验证消息发送
            mock_ctx.send.assert_called_once()
            mock_view.wait.assert_called_once()

    @pytest.mark.asyncio
    async def test_show_search_confirmation_timeout(self, manager, mock_ctx, search_result):
        """测试显示搜索确认 - 超时"""
        # 模拟消息发送
        mock_message = AsyncMock()
        mock_ctx.send.return_value = mock_message
        
        # 模拟视图超时
        with patch('similubot.ui.button_interactions.SearchConfirmationView') as mock_view_class:
            mock_view = AsyncMock()
            mock_view.result = InteractionResult.TIMEOUT
            mock_view.selected_result = None
            mock_view.wait = AsyncMock()
            mock_view_class.return_value = mock_view
            
            # 执行确认流程
            result, selected = await manager.show_search_confirmation(mock_ctx, search_result)
            
            # 验证结果
            assert result == InteractionResult.TIMEOUT
            assert selected is None
            
            # 验证超时消息编辑
            mock_message.edit.assert_called_once()

    @pytest.mark.asyncio
    async def test_show_search_selection_selected(self, manager, mock_ctx, search_results):
        """测试显示搜索选择 - 用户选择"""
        # 模拟消息发送
        mock_message = AsyncMock()
        mock_ctx.send.return_value = mock_message
        
        # 模拟视图等待结果
        with patch('similubot.ui.button_interactions.SearchSelectionView') as mock_view_class:
            mock_view = AsyncMock()
            mock_view.result = InteractionResult.SELECTED
            mock_view.selected_result = search_results[1]
            mock_view.wait = AsyncMock()
            mock_view_class.return_value = mock_view
            
            # 执行选择流程
            result, selected = await manager.show_search_selection(mock_ctx, search_results)
            
            # 验证结果
            assert result == InteractionResult.SELECTED
            assert selected == search_results[1]
            
            # 验证消息发送
            mock_ctx.send.assert_called_once()
            mock_view.wait.assert_called_once()

    @pytest.mark.asyncio
    async def test_show_search_selection_cancelled(self, manager, mock_ctx, search_results):
        """测试显示搜索选择 - 用户取消"""
        # 模拟消息发送
        mock_message = AsyncMock()
        mock_ctx.send.return_value = mock_message
        
        # 模拟视图取消
        with patch('similubot.ui.button_interactions.SearchSelectionView') as mock_view_class:
            mock_view = AsyncMock()
            mock_view.result = InteractionResult.CANCELLED
            mock_view.selected_result = None
            mock_view.wait = AsyncMock()
            mock_view_class.return_value = mock_view
            
            # 执行选择流程
            result, selected = await manager.show_search_selection(mock_ctx, search_results)
            
            # 验证结果
            assert result == InteractionResult.CANCELLED
            assert selected is None

    @pytest.mark.asyncio
    async def test_show_search_confirmation_exception_handling(self, manager, mock_ctx, search_result):
        """测试搜索确认异常处理"""
        # 模拟异常
        mock_ctx.send.side_effect = Exception("Test exception")
        
        # 执行确认流程
        result, selected = await manager.show_search_confirmation(mock_ctx, search_result)
        
        # 验证异常处理
        assert result == InteractionResult.TIMEOUT
        assert selected is None

    @pytest.mark.asyncio
    async def test_show_search_selection_exception_handling(self, manager, mock_ctx, search_results):
        """测试搜索选择异常处理"""
        # 模拟异常
        mock_ctx.send.side_effect = Exception("Test exception")
        
        # 执行选择流程
        result, selected = await manager.show_search_selection(mock_ctx, search_results)
        
        # 验证异常处理
        assert result == InteractionResult.TIMEOUT
        assert selected is None
