"""
测试机器人初始化修复 - 验证依赖注入和初始化顺序问题已解决
"""

import unittest
import sys
import os
from unittest.mock import MagicMock, patch
import tempfile

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from similubot.bot import SimiluBot
from similubot.utils.config_manager import ConfigManager
from similubot.core.dependency_container import DependencyContainer


class TestBotInitializationFix(unittest.TestCase):
    """测试机器人初始化修复"""

    def setUp(self):
        """设置测试环境"""
        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp()
        
        # 创建模拟配置
        self.mock_config = MagicMock(spec=ConfigManager)
        self.mock_config.get.side_effect = lambda key, default=None: {
            'discord.command_prefix': '!',
            'download.temp_dir': self.temp_dir,
            'music.enabled': True
        }.get(key, default)

    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('similubot.bot.commands.Bot')
    def test_dependency_container_initialization(self, mock_bot_class):
        """测试依赖注入容器正确初始化"""
        mock_bot_class.return_value = MagicMock()
        
        try:
            similu_bot = SimiluBot(config=self.mock_config)
            
            # 验证依赖注入容器已创建
            self.assertIsInstance(similu_bot.container, DependencyContainer)
            
            # 验证依赖项已注册
            dependency_graph = similu_bot.container.get_dependency_graph()
            expected_dependencies = [
                "temp_dir",
                "playback_engine", 
                "music_player_adapter",
                "playback_event",
                "command_registry"
            ]
            
            for dep in expected_dependencies:
                self.assertIn(dep, dependency_graph)
            
            print("✅ 依赖注入容器初始化测试通过")
            
        except Exception as e:
            self.fail(f"依赖注入容器初始化失败: {e}")

    @patch('similubot.bot.commands.Bot')
    def test_correct_initialization_order(self, mock_bot_class):
        """测试初始化顺序正确"""
        mock_bot_class.return_value = MagicMock()
        
        try:
            similu_bot = SimiluBot(config=self.mock_config)
            
            # 验证所有核心组件都已正确初始化
            self.assertIsNotNone(similu_bot.playback_engine)
            self.assertIsNotNone(similu_bot.music_player)
            self.assertIsNotNone(similu_bot.playback_event)
            self.assertIsNotNone(similu_bot.command_registry)
            
            # 验证播放事件处理器有正确的适配器
            self.assertEqual(
                similu_bot.playback_event.music_player_adapter, 
                similu_bot.music_player
            )
            
            print("✅ 初始化顺序测试通过")
            
        except Exception as e:
            self.fail(f"初始化顺序测试失败: {e}")

    @patch('similubot.bot.commands.Bot')
    def test_playback_events_registration(self, mock_bot_class):
        """测试播放事件处理器正确注册"""
        mock_bot_class.return_value = MagicMock()
        
        try:
            similu_bot = SimiluBot(config=self.mock_config)
            
            # 验证事件处理器已注册到播放引擎
            event_handlers = similu_bot.playback_engine._event_handlers
            
            required_events = [
                "show_song_info",
                "song_requester_absent_skip", 
                "your_song_notification"
            ]
            
            for event_type in required_events:
                self.assertIn(event_type, event_handlers)
                self.assertTrue(len(event_handlers[event_type]) > 0)

                # 验证处理器是正确的方法
                handler = event_handlers[event_type][0]
                # 验证处理器的方法名正确
                self.assertEqual(handler.__name__, event_type)
                # 验证处理器来自 PlaybackEvent 实例
                self.assertEqual(type(handler.__self__).__name__, 'PlaybackEvent')
            
            print("✅ 播放事件处理器注册测试通过")
            
        except Exception as e:
            self.fail(f"播放事件处理器注册测试失败: {e}")

    @patch('similubot.bot.commands.Bot')
    def test_dependency_validation(self, mock_bot_class):
        """测试依赖关系验证"""
        mock_bot_class.return_value = MagicMock()
        
        try:
            similu_bot = SimiluBot(config=self.mock_config)
            
            # 验证依赖关系有效（无循环依赖）
            is_valid = similu_bot.container.validate_dependencies()
            self.assertTrue(is_valid)
            
            print("✅ 依赖关系验证测试通过")
            
        except Exception as e:
            self.fail(f"依赖关系验证测试失败: {e}")

    @patch('similubot.bot.commands.Bot')
    def test_no_attribute_error(self, mock_bot_class):
        """测试不再出现 AttributeError: 'SimiluBot' object has no attribute 'music_player'"""
        mock_bot_class.return_value = MagicMock()
        
        try:
            # 这应该不会抛出 AttributeError
            similu_bot = SimiluBot(config=self.mock_config)
            
            # 验证 music_player 属性存在且不为 None
            self.assertTrue(hasattr(similu_bot, 'music_player'))
            self.assertIsNotNone(similu_bot.music_player)
            
            # 验证 playback_event 属性存在且不为 None
            self.assertTrue(hasattr(similu_bot, 'playback_event'))
            self.assertIsNotNone(similu_bot.playback_event)
            
            # 验证 playback_event 有正确的适配器引用
            self.assertIsNotNone(similu_bot.playback_event.music_player_adapter)
            
            print("✅ AttributeError 修复测试通过")
            
        except AttributeError as e:
            self.fail(f"仍然存在 AttributeError: {e}")
        except Exception as e:
            self.fail(f"其他初始化错误: {e}")

    def test_dependency_container_standalone(self):
        """测试依赖注入容器独立功能"""
        container = DependencyContainer()
        
        # 注册简单依赖项
        container.register_singleton("config", lambda: {"test": True})
        container.register_singleton("service", lambda config: f"Service with {config}", ["config"])
        
        # 解析依赖项
        config = container.resolve("config")
        service = container.resolve("service")
        
        self.assertEqual(config, {"test": True})
        self.assertEqual(service, "Service with {'test': True}")
        
        # 验证单例行为
        config2 = container.resolve("config")
        self.assertIs(config, config2)  # 应该是同一个实例
        
        print("✅ 依赖注入容器独立功能测试通过")

    def test_circular_dependency_detection(self):
        """测试循环依赖检测"""
        container = DependencyContainer()
        
        # 创建循环依赖
        container.register_singleton("a", lambda b: f"A depends on {b}", ["b"])
        container.register_singleton("b", lambda a: f"B depends on {a}", ["a"])
        
        # 应该检测到循环依赖
        with self.assertRaises(RuntimeError) as context:
            container.validate_dependencies()
        
        self.assertIn("循环依赖", str(context.exception))
        print("✅ 循环依赖检测测试通过")


if __name__ == '__main__':
    unittest.main()
