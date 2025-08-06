"""
队列公平性UI组件测试

测试新的队列公平性交互UI组件，包括：
1. 按钮交互处理
2. 用户权限验证
3. 超时处理
4. 错误处理
"""

import unittest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
import discord
from discord.ext import commands

from similubot.ui.button_interactions import (
    QueueFairnessReplacementView, 
    InteractionManager, 
    InteractionResult
)


class TestQueueFairnessUI(unittest.IsolatedAsyncioTestCase):
    """队列公平性UI组件测试类"""
    
    def setUp(self):
        """设置测试环境"""
        # 创建模拟用户
        self.mock_user = Mock(spec=discord.Member)
        self.mock_user.id = 67890
        self.mock_user.display_name = "TestUser"
        
        # 创建模拟的其他用户
        self.mock_other_user = Mock(spec=discord.Member)
        self.mock_other_user.id = 11111
        self.mock_other_user.display_name = "OtherUser"
        
        # 创建模拟的Discord交互
        self.mock_interaction = Mock(spec=discord.Interaction)
        self.mock_interaction.response = Mock()
        self.mock_interaction.response.send_message = AsyncMock()
        self.mock_interaction.response.edit_message = AsyncMock()
        
        # 创建模拟的命令上下文
        self.mock_ctx = Mock(spec=commands.Context)
        self.mock_ctx.author = self.mock_user
        self.mock_ctx.send = AsyncMock()
        
        # 测试数据
        self.new_song_title = "New Song"
        self.existing_song_title = "Existing Song"
        self.queue_position = 3
    
    async def test_replacement_view_initialization(self):
        """测试替换视图初始化"""
        print("\n🧪 测试替换视图初始化")
        
        view = QueueFairnessReplacementView(
            user=self.mock_user,
            new_song_title=self.new_song_title,
            existing_song_title=self.existing_song_title,
            queue_position=self.queue_position
        )
        
        # 验证初始化参数
        self.assertEqual(view.user, self.mock_user)
        self.assertEqual(view.new_song_title, self.new_song_title)
        self.assertEqual(view.existing_song_title, self.existing_song_title)
        self.assertEqual(view.queue_position, self.queue_position)
        self.assertIsNone(view.result)
        
        # 验证按钮数量
        self.assertEqual(len(view.children), 2)  # 两个按钮：确认和拒绝
        
        print("   ✅ 替换视图初始化正确")
    
    async def test_replace_button_success(self):
        """测试替换按钮成功处理"""
        print("\n🧪 测试替换按钮成功处理")

        view = QueueFairnessReplacementView(
            user=self.mock_user,
            new_song_title=self.new_song_title,
            existing_song_title=self.existing_song_title,
            queue_position=self.queue_position
        )

        # 设置交互用户为正确用户
        self.mock_interaction.user = self.mock_user

        # 找到替换按钮并调用其回调
        replace_button = None
        for child in view.children:
            if hasattr(child, 'custom_id') and child.custom_id == 'replace_confirm':
                replace_button = child
                break

        self.assertIsNotNone(replace_button, "未找到替换按钮")

        # 调用按钮回调
        await replace_button.callback(self.mock_interaction)

        # 验证结果
        self.assertEqual(view.result, InteractionResult.REPLACED)

        # 验证交互响应被调用
        self.mock_interaction.response.edit_message.assert_called_once()

        print("   ✅ 替换按钮处理成功")
    
    async def test_replace_button_wrong_user(self):
        """测试替换按钮权限验证"""
        print("\n🧪 测试替换按钮权限验证")
        
        view = QueueFairnessReplacementView(
            user=self.mock_user,
            new_song_title=self.new_song_title,
            existing_song_title=self.existing_song_title,
            queue_position=self.queue_position
        )
        
        # 设置交互用户为错误用户
        self.mock_interaction.user = self.mock_other_user
        
        # 调用替换按钮
        await view.replace_button(self.mock_interaction, Mock())
        
        # 验证结果未改变
        self.assertIsNone(view.result)
        
        # 验证发送了权限错误消息
        self.mock_interaction.response.send_message.assert_called_once()
        call_args = self.mock_interaction.response.send_message.call_args
        self.assertIn("只有", call_args[1]['content'])
        self.assertTrue(call_args[1]['ephemeral'])
        
        print("   ✅ 替换按钮权限验证正确")
    
    async def test_deny_button_success(self):
        """测试拒绝按钮成功处理"""
        print("\n🧪 测试拒绝按钮成功处理")
        
        view = QueueFairnessReplacementView(
            user=self.mock_user,
            new_song_title=self.new_song_title,
            existing_song_title=self.existing_song_title,
            queue_position=self.queue_position
        )
        
        # 设置交互用户为正确用户
        self.mock_interaction.user = self.mock_user
        
        # 调用拒绝按钮
        await view.deny_button(self.mock_interaction, Mock())
        
        # 验证结果
        self.assertEqual(view.result, InteractionResult.DENIED)
        
        # 验证交互响应被调用
        self.mock_interaction.response.edit_message.assert_called_once()
        
        print("   ✅ 拒绝按钮处理成功")
    
    async def test_view_timeout(self):
        """测试视图超时处理"""
        print("\n🧪 测试视图超时处理")
        
        view = QueueFairnessReplacementView(
            user=self.mock_user,
            new_song_title=self.new_song_title,
            existing_song_title=self.existing_song_title,
            queue_position=self.queue_position,
            timeout=0.1  # 很短的超时时间
        )
        
        # 等待超时
        await asyncio.sleep(0.2)
        await view.on_timeout()
        
        # 验证超时结果
        self.assertEqual(view.result, InteractionResult.TIMEOUT)
        
        print("   ✅ 视图超时处理正确")
    
    async def test_interaction_manager_queue_fairness(self):
        """测试交互管理器的队列公平性处理"""
        print("\n🧪 测试交互管理器的队列公平性处理")
        
        interaction_manager = InteractionManager()
        
        # 模拟快速确认（避免实际等待）
        with patch.object(QueueFairnessReplacementView, 'wait', new_callable=AsyncMock) as mock_wait:
            # 创建模拟视图，设置结果为REPLACED
            mock_view = Mock()
            mock_view.result = InteractionResult.REPLACED
            
            with patch.object(interaction_manager, '_create_queue_fairness_embed') as mock_create_embed:
                mock_embed = Mock()
                mock_create_embed.return_value = mock_embed
                
                with patch('similubot.ui.button_interactions.QueueFairnessReplacementView') as mock_view_class:
                    mock_view_class.return_value = mock_view
                    
                    # 调用交互管理器方法
                    result, _ = await interaction_manager.show_queue_fairness_replacement(
                        ctx=self.mock_ctx,
                        new_song_title=self.new_song_title,
                        existing_song_title=self.existing_song_title,
                        queue_position=self.queue_position
                    )
                    
                    # 验证结果
                    self.assertEqual(result, InteractionResult.REPLACED)
                    
                    # 验证方法调用
                    self.mock_ctx.send.assert_called_once()
                    mock_create_embed.assert_called_once()
        
        print("   ✅ 交互管理器处理正确")
    
    async def test_embed_creation(self):
        """测试嵌入消息创建"""
        print("\n🧪 测试嵌入消息创建")
        
        interaction_manager = InteractionManager()
        
        embed = interaction_manager._create_queue_fairness_embed(
            user=self.mock_user,
            new_song_title=self.new_song_title,
            existing_song_title=self.existing_song_title,
            queue_position=self.queue_position
        )
        
        # 验证嵌入消息属性
        self.assertEqual(embed.title, "⚖️ 队列公平性限制")
        self.assertIn("是否要替换现有歌曲", embed.description)
        
        # 验证字段数量
        self.assertEqual(len(embed.fields), 4)
        
        # 验证字段内容
        field_names = [field.name for field in embed.fields]
        self.assertIn("🎵 您想添加的歌曲", field_names)
        self.assertIn("🎶 您现有的队列歌曲", field_names)
        self.assertIn("📋 队列规则", field_names)
        self.assertIn("💡 选择说明", field_names)
        
        # 验证歌曲信息
        new_song_field = next(field for field in embed.fields if "想添加的歌曲" in field.name)
        self.assertIn(self.new_song_title, new_song_field.value)
        
        existing_song_field = next(field for field in embed.fields if "现有的队列歌曲" in field.name)
        self.assertIn(self.existing_song_title, existing_song_field.value)
        self.assertIn(f"第 {self.queue_position} 位", existing_song_field.value)
        
        print("   ✅ 嵌入消息创建正确")


    async def test_button_interaction_error_handling(self):
        """测试按钮交互错误处理"""
        print("\n🧪 测试按钮交互错误处理")

        view = QueueFairnessReplacementView(
            user=self.mock_user,
            new_song_title=self.new_song_title,
            existing_song_title=self.existing_song_title,
            queue_position=self.queue_position
        )

        # 设置交互用户为正确用户
        self.mock_interaction.user = self.mock_user

        # 模拟edit_message抛出异常
        self.mock_interaction.response.edit_message.side_effect = Exception("Test error")

        # 调用替换按钮（应该捕获异常）
        await view.replace_button(self.mock_interaction, Mock())

        # 验证发送了错误消息
        self.mock_interaction.response.send_message.assert_called()
        call_args = self.mock_interaction.response.send_message.call_args
        self.assertIn("处理替换确认时出错", call_args[0][0])

        print("   ✅ 按钮交互错误处理正确")

    async def test_concurrent_interactions(self):
        """测试并发交互处理"""
        print("\n🧪 测试并发交互处理")

        view = QueueFairnessReplacementView(
            user=self.mock_user,
            new_song_title=self.new_song_title,
            existing_song_title=self.existing_song_title,
            queue_position=self.queue_position
        )

        # 创建多个交互
        interactions = []
        for i in range(3):
            mock_interaction = Mock(spec=discord.Interaction)
            mock_interaction.user = self.mock_user
            mock_interaction.response = Mock()
            mock_interaction.response.edit_message = AsyncMock()
            interactions.append(mock_interaction)

        # 并发调用替换按钮
        tasks = [view.replace_button(interaction, Mock()) for interaction in interactions]
        await asyncio.gather(*tasks, return_exceptions=True)

        # 验证只有一个交互成功（第一个）
        self.assertEqual(view.result, InteractionResult.REPLACED)

        # 验证只有第一个交互调用了edit_message
        edit_calls = sum(1 for interaction in interactions
                        if interaction.response.edit_message.called)
        self.assertEqual(edit_calls, 1)

        print("   ✅ 并发交互处理正确")


if __name__ == '__main__':
    unittest.main()
