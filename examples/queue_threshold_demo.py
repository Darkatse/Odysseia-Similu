#!/usr/bin/env python3
"""
队列长度阈值功能演示脚本

展示新的队列长度阈值功能如何在低峰时段提供更灵活的用户体验，
同时在繁忙时段保持公平性限制。
"""

import asyncio
import sys
import os
from unittest.mock import MagicMock

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from similubot.queue.queue_manager import QueueManager, DuplicateSongError, QueueFairnessError
from similubot.core.interfaces import AudioInfo
from similubot.utils.config_manager import ConfigManager
import discord


def create_mock_user(user_id: int, name: str) -> discord.Member:
    """创建模拟Discord用户"""
    user = MagicMock(spec=discord.Member)
    user.id = user_id
    user.display_name = name
    return user


def create_audio_info(title: str, duration: int, url: str, uploader: str) -> AudioInfo:
    """创建音频信息"""
    return AudioInfo(
        title=title,
        duration=duration,
        url=url,
        uploader=uploader
    )


def create_mock_config(threshold: int) -> ConfigManager:
    """创建模拟配置管理器"""
    config = MagicMock(spec=ConfigManager)
    config.get.return_value = threshold
    return config


async def demo_off_peak_hours():
    """演示低峰时段的灵活体验"""
    print("🌙 低峰时段演示 (阈值: 5)")
    print("=" * 50)
    
    # 创建配置阈值为5的队列管理器
    config = create_mock_config(5)
    queue_manager = QueueManager(guild_id=12345, config_manager=config)
    
    alice = create_mock_user(1001, "Alice")
    
    # 创建多首不同歌曲
    songs = [
        create_audio_info("Morning Song", 180, "https://www.youtube.com/watch?v=morning", "Morning Artist"),
        create_audio_info("Sunrise Melody", 200, "https://www.youtube.com/watch?v=sunrise", "Sunrise Artist"),
        create_audio_info("Dawn Chorus", 220, "https://www.youtube.com/watch?v=dawn", "Dawn Artist"),
        create_audio_info("Early Bird", 240, "https://www.youtube.com/watch?v=early", "Early Artist"),
    ]
    
    print("场景: 凌晨3点，Alice是唯一的活跃用户")
    
    # Alice 可以自由添加多首歌曲
    for i, song in enumerate(songs, 1):
        try:
            position = await queue_manager.add_song(song, alice)
            print(f"   ✅ 歌曲 {i} 添加成功: '{song.title}' (位置: {position})")
        except Exception as e:
            print(f"   ❌ 歌曲 {i} 添加失败: {e}")
    
    # Alice 甚至可以添加重复歌曲
    try:
        position = await queue_manager.add_song(songs[0], alice)
        print(f"   ✅ 重复歌曲添加成功: '{songs[0].title}' (位置: {position})")
    except Exception as e:
        print(f"   ❌ 重复歌曲添加失败: {e}")
    
    # 显示队列状态
    queue_info = await queue_manager.get_queue_info()
    user_status = queue_manager.get_user_queue_status(alice)
    
    print(f"\n📊 队列状态:")
    print(f"   总长度: {queue_info['queue_length']} 首")
    print(f"   阈值: {user_status['queue_length_threshold']}")
    print(f"   限制绕过: {user_status['restrictions_bypassed']}")
    print(f"   Alice 的待播放歌曲: {user_status['pending_songs']} 首")


async def demo_peak_hours():
    """演示高峰时段的公平性限制"""
    print("\n\n☀️ 高峰时段演示 (阈值: 3)")
    print("=" * 50)
    
    # 创建配置阈值为3的队列管理器
    config = create_mock_config(3)
    queue_manager = QueueManager(guild_id=12346, config_manager=config)
    
    alice = create_mock_user(1001, "Alice")
    bob = create_mock_user(1002, "Bob")
    charlie = create_mock_user(1003, "Charlie")
    
    songs = [
        create_audio_info("Popular Song 1", 180, "https://www.youtube.com/watch?v=pop1", "Pop Artist 1"),
        create_audio_info("Popular Song 2", 200, "https://www.youtube.com/watch?v=pop2", "Pop Artist 2"),
        create_audio_info("Popular Song 3", 220, "https://www.youtube.com/watch?v=pop3", "Pop Artist 3"),
        create_audio_info("Popular Song 4", 240, "https://www.youtube.com/watch?v=pop4", "Pop Artist 4"),
    ]
    
    print("场景: 晚上8点，多个用户同时活跃")
    
    # 1. 用户们各自添加歌曲，快速达到阈值
    users = [alice, bob, charlie]
    for i, (user, song) in enumerate(zip(users, songs[:3]), 1):
        position = await queue_manager.add_song(song, user)
        print(f"   ✅ {user.display_name} 添加歌曲: '{song.title}' (位置: {position})")
    
    # 2. 现在队列长度达到阈值，限制开始生效
    queue_info = await queue_manager.get_queue_info()
    print(f"\n📊 队列长度达到阈值: {queue_info['queue_length']}/3")
    
    # 3. Alice 尝试添加第二首歌曲（应该被阻止）
    print("\n🚫 公平性限制生效:")
    try:
        await queue_manager.add_song(songs[3], alice)
        print("   ❌ Alice 不应该能添加第二首歌曲")
    except QueueFairnessError as e:
        print(f"   ✅ Alice 被队列公平性阻止: {e}")
    
    # 4. Alice 尝试添加重复歌曲（应该被阻止）
    try:
        await queue_manager.add_song(songs[0], alice)
        print("   ❌ Alice 不应该能添加重复歌曲")
    except DuplicateSongError as e:
        print(f"   ✅ Alice 被重复检测阻止: {e}")
    
    # 5. 显示所有用户状态
    print(f"\n👥 用户状态:")
    for user in users:
        status = queue_manager.get_user_queue_status(user)
        print(f"   {user.display_name}: 待播放 {status['pending_songs']} 首, "
              f"可添加: {status['can_add_song']}, 限制绕过: {status['restrictions_bypassed']}")


async def demo_dynamic_threshold_behavior():
    """演示动态阈值行为"""
    print("\n\n🔄 动态阈值行为演示")
    print("=" * 50)
    
    # 创建配置阈值为4的队列管理器
    config = create_mock_config(4)
    queue_manager = QueueManager(guild_id=12347, config_manager=config)
    
    alice = create_mock_user(1001, "Alice")
    
    songs = [
        create_audio_info(f"Dynamic Song {i}", 180 + i*10, f"https://www.youtube.com/watch?v=dyn{i}", f"Artist {i}")
        for i in range(1, 7)
    ]
    
    print("场景: 展示限制如何随队列长度动态变化")
    
    # 1. 逐步添加歌曲，观察限制变化
    for i in range(1, 5):  # 只添加4首歌曲
        # 添加歌曲
        position = await queue_manager.add_song(songs[i-1], alice)
        queue_info = await queue_manager.get_queue_info()
        user_status = queue_manager.get_user_queue_status(alice)

        print(f"\n步骤 {i}: 添加歌曲 '{songs[i-1].title}'")
        print(f"   位置: {position}")
        print(f"   队列长度: {queue_info['queue_length']}")
        print(f"   限制绕过: {user_status['restrictions_bypassed']}")

        # 测试是否可以添加更多歌曲
        if i < 4:  # 在前3步测试
            can_add, error = queue_manager.can_user_add_song(songs[i], alice)
            if can_add:
                print(f"   ✅ 可以继续添加歌曲")
            else:
                print(f"   🚫 不能添加更多歌曲: {error}")

    # 测试第5首歌曲是否会被阻止
    print(f"\n步骤 5: 尝试添加第5首歌曲 '{songs[4].title}'")
    try:
        position = await queue_manager.add_song(songs[4], alice)
        print(f"   ❌ 不应该成功: 位置 {position}")
    except QueueFairnessError as e:
        print(f"   ✅ 被公平性限制阻止: {e}")
    
    # 2. 播放一首歌曲，观察限制如何变化
    print(f"\n🎵 开始播放第一首歌曲")
    playing_song = await queue_manager.get_next_song()
    queue_info = await queue_manager.get_queue_info()
    user_status = queue_manager.get_user_queue_status(alice)
    
    print(f"   正在播放: {playing_song.title}")
    print(f"   队列长度: {queue_info['queue_length']} (不包括正在播放)")
    print(f"   总长度: {queue_info['queue_length'] + 1} (包括正在播放)")
    print(f"   限制绕过: {user_status['restrictions_bypassed']}")
    
    # 3. 播放完成，观察限制变化
    print(f"\n✅ 歌曲播放完成")
    queue_manager.notify_song_finished(playing_song)
    user_status = queue_manager.get_user_queue_status(alice)
    
    print(f"   Alice 可以添加歌曲: {user_status['can_add_song']}")
    print(f"   限制绕过: {user_status['restrictions_bypassed']}")


async def demo_configuration_scenarios():
    """演示不同配置场景"""
    print("\n\n⚙️ 配置场景演示")
    print("=" * 50)
    
    scenarios = [
        ("严格模式", 1),
        ("宽松模式", 10),
        ("平衡模式", 5),
    ]
    
    alice = create_mock_user(1001, "Alice")
    songs = [
        create_audio_info(f"Config Song {i}", 180, f"https://www.youtube.com/watch?v=cfg{i}", f"Config Artist {i}")
        for i in range(1, 4)
    ]
    
    for scenario_name, threshold in scenarios:
        print(f"\n📋 {scenario_name} (阈值: {threshold})")
        
        config = create_mock_config(threshold)
        queue_manager = QueueManager(guild_id=12348 + threshold, config_manager=config)
        
        # 添加一首歌曲
        await queue_manager.add_song(songs[0], alice)
        
        # 测试能否添加第二首歌曲
        can_add, error = queue_manager.can_user_add_song(songs[1], alice)
        user_status = queue_manager.get_user_queue_status(alice)
        
        print(f"   队列长度: 1, 阈值: {threshold}")
        print(f"   限制绕过: {user_status['restrictions_bypassed']}")
        print(f"   可以添加第二首歌曲: {can_add}")
        if not can_add:
            print(f"   原因: {error}")


async def main():
    """主演示函数"""
    print("🎵 Odysseia-Similu 队列长度阈值功能演示")
    print("=" * 70)
    print("新功能特性：")
    print("✅ 可配置的队列长度阈值")
    print("✅ 低峰时段的灵活用户体验")
    print("✅ 高峰时段的公平性保护")
    print("✅ 动态限制调整")
    print("✅ 详细的状态监控")
    print("=" * 70)
    
    await demo_off_peak_hours()
    await demo_peak_hours()
    await demo_dynamic_threshold_behavior()
    await demo_configuration_scenarios()
    
    print("\n\n🎉 演示完成！")
    print("=" * 70)
    print("队列长度阈值功能成功实现了以下目标：")
    print("🌙 低峰时段: 用户可以自由添加多首歌曲，提升体验")
    print("☀️ 高峰时段: 自动启用公平性限制，确保所有用户公平访问")
    print("🔄 动态调整: 限制随队列长度实时变化")
    print("⚙️ 灵活配置: 管理员可根据服务器特点调整阈值")
    print("📊 透明监控: 用户可以了解当前限制状态")
    print("\n💡 使用建议:")
    print("   - 小型服务器: 设置较高阈值 (7-10)")
    print("   - 大型服务器: 设置较低阈值 (3-5)")
    print("   - 活跃服务器: 设置较低阈值 (2-4)")


if __name__ == "__main__":
    asyncio.run(main())
