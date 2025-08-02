"""
队列长度阈值功能测试

测试新的队列长度阈值功能，验证当队列长度低于阈值时跳过所有限制。
"""

import unittest
import asyncio
import sys
import os
from unittest.mock import MagicMock

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from similubot.queue.queue_manager import QueueManager, DuplicateSongError, QueueFairnessError
from similubot.queue.duplicate_detector import DuplicateDetector
from similubot.core.interfaces import AudioInfo
from similubot.utils.config_manager import ConfigManager
import discord


class TestQueueLengthThreshold(unittest.TestCase):
    """测试队列长度阈值功能"""
    
    def setUp(self):
        """设置测试环境"""
        # 创建模拟配置管理器
        self.mock_config = MagicMock(spec=ConfigManager)
        self.mock_config.get.return_value = 3  # 设置阈值为3
        
        self.queue_manager = QueueManager(guild_id=12345, config_manager=self.mock_config)
        
        # 创建测试用户
        self.user1 = MagicMock(spec=discord.Member)
        self.user1.id = 1001
        self.user1.display_name = "User1"
        
        self.user2 = MagicMock(spec=discord.Member)
        self.user2.id = 1002
        self.user2.display_name = "User2"
        
        # 创建测试歌曲
        self.songs = [
            AudioInfo(
                title=f"Song {i}",
                duration=180 + i*10,
                url=f"https://www.youtube.com/watch?v=song{i}",
                uploader=f"Artist {i}"
            )
            for i in range(1, 8)
        ]
    
    async def test_threshold_bypass_duplicate_detection(self):
        """测试阈值绕过重复检测"""
        print("🧪 测试阈值绕过重复检测")
        
        # 1. 添加第一首歌曲
        position1 = await self.queue_manager.add_song(self.songs[0], self.user1)
        print(f"   ✅ 第一次添加成功: 位置 {position1}")
        
        # 2. 队列长度为1，低于阈值3，应该允许重复添加
        try:
            position2 = await self.queue_manager.add_song(self.songs[0], self.user1)
            print(f"   ✅ 重复添加成功（阈值绕过）: 位置 {position2}")
        except DuplicateSongError:
            print("   ❌ 不应该被重复检测阻止")
            self.fail("重复检测应该被阈值绕过")
        
        # 3. 验证队列状态
        queue_info = await self.queue_manager.get_queue_info()
        self.assertEqual(queue_info['queue_length'], 2)
        print(f"   ✅ 队列长度: {queue_info['queue_length']}")
    
    async def test_threshold_bypass_queue_fairness(self):
        """测试阈值绕过队列公平性"""
        print("\n🧪 测试阈值绕过队列公平性")
        
        # 创建新的队列管理器
        queue_manager = QueueManager(guild_id=12346, config_manager=self.mock_config)
        
        # 1. 添加第一首歌曲
        position1 = await queue_manager.add_song(self.songs[0], self.user1)
        print(f"   ✅ 第一首歌曲添加成功: 位置 {position1}")
        
        # 2. 队列长度为1，低于阈值3，应该允许添加不同歌曲
        try:
            position2 = await queue_manager.add_song(self.songs[1], self.user1)
            print(f"   ✅ 第二首不同歌曲添加成功（阈值绕过）: 位置 {position2}")
        except QueueFairnessError:
            print("   ❌ 不应该被队列公平性阻止")
            self.fail("队列公平性应该被阈值绕过")
        
        # 3. 再添加一首歌曲，队列长度仍然低于阈值
        try:
            position3 = await queue_manager.add_song(self.songs[2], self.user1)
            print(f"   ✅ 第三首歌曲添加成功（阈值绕过）: 位置 {position3}")
        except QueueFairnessError:
            print("   ❌ 不应该被队列公平性阻止")
            self.fail("队列公平性应该被阈值绕过")
        
        # 4. 验证队列状态
        queue_info = await queue_manager.get_queue_info()
        self.assertEqual(queue_info['queue_length'], 3)
        print(f"   ✅ 队列长度: {queue_info['queue_length']}")
    
    async def test_threshold_enforcement_when_reached(self):
        """测试达到阈值时恢复限制"""
        print("\n🧪 测试达到阈值时恢复限制")
        
        # 创建新的队列管理器
        queue_manager = QueueManager(guild_id=12347, config_manager=self.mock_config)
        
        # 1. 添加歌曲直到达到阈值
        for i in range(3):
            position = await queue_manager.add_song(self.songs[i], self.user1)
            print(f"   ✅ 添加歌曲 {i+1}: 位置 {position}")
        
        # 2. 现在队列长度为3，等于阈值，限制应该恢复
        # 尝试添加重复歌曲（应该被阻止）
        with self.assertRaises(DuplicateSongError):
            await queue_manager.add_song(self.songs[0], self.user1)
        print("   ✅ 重复检测恢复生效")
        
        # 3. 尝试添加不同歌曲（应该被队列公平性阻止）
        with self.assertRaises(QueueFairnessError):
            await queue_manager.add_song(self.songs[3], self.user1)
        print("   ✅ 队列公平性恢复生效")
        
        # 4. 不同用户仍然可以添加歌曲
        try:
            position = await queue_manager.add_song(self.songs[3], self.user2)
            print(f"   ✅ 不同用户添加成功: 位置 {position}")
        except Exception as e:
            print(f"   ❌ 不同用户添加失败: {e}")
            self.fail("不同用户应该可以添加歌曲")
    
    async def test_threshold_with_playing_song(self):
        """测试包含正在播放歌曲的队列长度计算"""
        print("\n🧪 测试包含正在播放歌曲的队列长度计算")
        
        # 创建新的队列管理器
        queue_manager = QueueManager(guild_id=12348, config_manager=self.mock_config)
        
        # 1. 添加两首歌曲
        await queue_manager.add_song(self.songs[0], self.user1)
        await queue_manager.add_song(self.songs[1], self.user2)
        print("   ✅ 添加了2首歌曲到队列")
        
        # 2. 开始播放第一首歌曲
        playing_song = await queue_manager.get_next_song()
        self.assertIsNotNone(playing_song)
        print(f"   ✅ 开始播放: {playing_song.title}")
        
        # 3. 现在队列长度为2（1首在播放 + 1首在队列），低于阈值3
        # 用户应该可以添加更多歌曲
        try:
            position = await queue_manager.add_song(self.songs[2], self.user1)
            print(f"   ✅ 播放期间添加成功（阈值绕过）: 位置 {position}")
        except Exception as e:
            print(f"   ❌ 播放期间添加失败: {e}")
            self.fail("播放期间应该可以添加歌曲（阈值绕过）")
    
    def test_config_validation(self):
        """测试配置验证"""
        print("\n🧪 测试配置验证")
        
        # 1. 测试无效配置值
        invalid_config = MagicMock(spec=ConfigManager)
        invalid_config.get.return_value = -1  # 无效值
        
        detector = DuplicateDetector(guild_id=12349, config_manager=invalid_config)
        threshold = detector._get_queue_length_threshold()
        self.assertEqual(threshold, 5)  # 应该使用默认值
        print("   ✅ 无效配置使用默认值")
        
        # 2. 测试无配置管理器
        detector_no_config = DuplicateDetector(guild_id=12350)
        threshold = detector_no_config._get_queue_length_threshold()
        self.assertEqual(threshold, 5)  # 应该使用默认值
        print("   ✅ 无配置管理器使用默认值")
        
        # 3. 测试配置异常
        error_config = MagicMock(spec=ConfigManager)
        error_config.get.side_effect = Exception("Config error")
        
        detector_error = DuplicateDetector(guild_id=12351, config_manager=error_config)
        threshold = detector_error._get_queue_length_threshold()
        self.assertEqual(threshold, 5)  # 应该使用默认值
        print("   ✅ 配置异常使用默认值")
    
    def test_user_status_with_threshold_info(self):
        """测试用户状态包含阈值信息"""
        print("\n🧪 测试用户状态包含阈值信息")
        
        # 获取用户状态
        status = self.queue_manager.get_user_queue_status(self.user1)
        
        # 验证包含阈值相关信息
        self.assertIn('queue_length', status)
        self.assertIn('queue_length_threshold', status)
        self.assertIn('restrictions_bypassed', status)
        
        print(f"   ✅ 队列长度: {status['queue_length']}")
        print(f"   ✅ 阈值: {status['queue_length_threshold']}")
        print(f"   ✅ 限制绕过: {status['restrictions_bypassed']}")
        
        # 验证阈值信息正确
        self.assertEqual(status['queue_length_threshold'], 3)
        self.assertTrue(status['restrictions_bypassed'])  # 空队列应该绕过限制


async def run_tests():
    """运行所有测试"""
    print("🎵 队列长度阈值功能测试")
    print("=" * 60)
    
    test_instance = TestQueueLengthThreshold()
    
    # 运行异步测试
    async_tests = [
        test_instance.test_threshold_bypass_duplicate_detection,
        test_instance.test_threshold_bypass_queue_fairness,
        test_instance.test_threshold_enforcement_when_reached,
        test_instance.test_threshold_with_playing_song,
    ]
    
    for test_func in async_tests:
        try:
            test_instance.setUp()  # 重新设置测试环境
            await test_func()
        except Exception as e:
            print(f"❌ {test_func.__name__} 失败: {e}")
            return False
    
    # 运行同步测试
    sync_tests = [
        test_instance.test_config_validation,
        test_instance.test_user_status_with_threshold_info,
    ]
    
    for test_func in sync_tests:
        try:
            test_instance.setUp()  # 重新设置测试环境
            test_func()
        except Exception as e:
            print(f"❌ {test_func.__name__} 失败: {e}")
            return False
    
    print("\n🎉 所有测试通过！")
    print("=" * 60)
    print("队列长度阈值功能验证成功：")
    print("✅ 低于阈值时绕过重复检测")
    print("✅ 低于阈值时绕过队列公平性")
    print("✅ 达到阈值时恢复所有限制")
    print("✅ 正确计算包含播放歌曲的队列长度")
    print("✅ 配置验证和错误处理正常")
    print("✅ 用户状态包含阈值信息")
    
    return True


if __name__ == "__main__":
    success = asyncio.run(run_tests())
    if not success:
        exit(1)
