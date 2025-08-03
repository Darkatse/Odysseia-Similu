"""
集成测试 - 验证重构后的播放事件处理器能正确集成到系统中
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


class TestPlaybackEventIntegration(unittest.TestCase):
    """测试重构后的播放事件处理器集成"""

    def setUp(self):
        """设置测试环境"""
        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp()
        
        # 创建模拟配置
        self.mock_config = MagicMock(spec=ConfigManager)
        self.mock_config.get.return_value = True  # 启用音乐功能
        
        # 模拟Discord机器人
        self.mock_bot = MagicMock()

    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('similubot.bot.commands.Bot')
    def test_bot_initialization_with_refactored_events(self, mock_bot_class):
        """测试机器人能正确初始化重构后的播放事件处理器"""
        mock_bot_class.return_value = self.mock_bot
        
        try:
            # 创建机器人实例
            similu_bot = SimiluBot(config=self.mock_config)
            
            # 验证播放事件处理器已创建
            self.assertIsNotNone(similu_bot.playback_event)
            
            # 验证播放事件处理器有正确的适配器
            self.assertIsNotNone(similu_bot.playback_event.music_player_adapter)
            self.assertEqual(similu_bot.playback_event.music_player_adapter, similu_bot.music_player)
            
            # 验证播放引擎已注册事件处理器
            self.assertTrue(len(similu_bot.playback_engine._event_handlers["show_song_info"]) > 0)
            self.assertTrue(len(similu_bot.playback_engine._event_handlers["song_requester_absent_skip"]) > 0)
            self.assertTrue(len(similu_bot.playback_engine._event_handlers["your_song_notification"]) > 0)
            
            print("✅ 机器人初始化测试通过")
            
        except Exception as e:
            self.fail(f"机器人初始化失败: {e}")

    @patch('similubot.bot.commands.Bot')
    def test_event_handler_registration(self, mock_bot_class):
        """测试事件处理器注册是否正确"""
        mock_bot_class.return_value = self.mock_bot
        
        similu_bot = SimiluBot(config=self.mock_config)
        
        # 检查事件处理器是否正确注册
        event_handlers = similu_bot.playback_engine._event_handlers
        
        # 验证每个事件类型都有处理器
        for event_type in ["show_song_info", "song_requester_absent_skip", "your_song_notification"]:
            self.assertIn(event_type, event_handlers)
            self.assertTrue(len(event_handlers[event_type]) > 0)
            
            # 验证处理器是我们重构后的方法
            handler = event_handlers[event_type][0]
            self.assertEqual(handler.__self__, similu_bot.playback_event)
        
        print("✅ 事件处理器注册测试通过")

    @patch('similubot.bot.commands.Bot')
    def test_playback_event_methods_exist(self, mock_bot_class):
        """测试播放事件处理器的方法是否存在且可调用"""
        mock_bot_class.return_value = self.mock_bot
        
        similu_bot = SimiluBot(config=self.mock_config)
        
        playback_event = similu_bot.playback_event
        
        # 验证所有必需的方法都存在
        required_methods = [
            'show_song_info',
            'song_requester_absent_skip',
            'your_song_notification',
            '_format_duration'
        ]
        
        for method_name in required_methods:
            self.assertTrue(hasattr(playback_event, method_name))
            method = getattr(playback_event, method_name)
            self.assertTrue(callable(method))
        
        print("✅ 播放事件处理器方法存在性测试通过")

    @patch('similubot.bot.commands.Bot')
    def test_format_duration_functionality(self, mock_bot_class):
        """测试时长格式化功能"""
        mock_bot_class.return_value = self.mock_bot
        
        similu_bot = SimiluBot(config=self.mock_config)
        
        playback_event = similu_bot.playback_event
        
        # 测试时长格式化
        test_cases = [
            (30, "0:30"),
            (90, "1:30"),
            (3600, "1:00:00"),
            (3661, "1:01:01"),
            (0, "0:00")
        ]
        
        for seconds, expected in test_cases:
            result = playback_event._format_duration(seconds)
            self.assertEqual(result, expected, f"格式化 {seconds} 秒失败")
        
        print("✅ 时长格式化功能测试通过")

    def test_no_old_architecture_imports(self):
        """测试确保没有导入旧架构模块"""
        # 检查 PlaybackEvent 文件内容
        playback_event_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'similubot', 'playback', 'playback_event.py'
        )
        
        with open(playback_event_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 确保没有导入旧的 music_player 模块
        self.assertNotIn('from similubot.music.music_player import', content)
        self.assertNotIn('similubot.music.music_player', content)
        
        # 确保有正确的日志记录
        self.assertIn('logging.getLogger', content)
        
        # 确保有中文注释
        self.assertIn('播放事件处理器', content)
        
        print("✅ 旧架构导入检查测试通过")


if __name__ == '__main__':
    unittest.main()
