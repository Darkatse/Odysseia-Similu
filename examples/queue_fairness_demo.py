#!/usr/bin/env python3
"""
队列公平性系统演示脚本

展示新的队列公平性机制如何防止用户垃圾信息攻击，同时保持多用户公平性。
"""

import asyncio
import sys
import os
from unittest.mock import MagicMock

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from similubot.queue.queue_manager import QueueManager, DuplicateSongError, QueueFairnessError
from similubot.core.interfaces import AudioInfo
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


async def demo_queue_fairness_basics():
    """演示队列公平性基础功能"""
    print("🎵 队列公平性系统基础演示")
    print("=" * 50)
    
    # 创建队列管理器和用户
    queue_manager = QueueManager(guild_id=12345)
    alice = create_mock_user(1001, "Alice")
    bob = create_mock_user(1002, "Bob")
    
    # 创建不同的歌曲
    songs = [
        create_audio_info("Song A", 180, "https://www.youtube.com/watch?v=songA", "Artist A"),
        create_audio_info("Song B", 200, "https://www.youtube.com/watch?v=songB", "Artist B"),
        create_audio_info("Song C", 220, "https://www.youtube.com/watch?v=songC", "Artist C"),
        create_audio_info("Song D", 240, "https://www.youtube.com/watch?v=songD", "Artist D"),
    ]
    
    print("1. Alice 添加第一首歌曲")
    try:
        position = await queue_manager.add_song(songs[0], alice)
        print(f"   ✅ 成功添加 '{songs[0].title}' (位置: {position})")
    except Exception as e:
        print(f"   ❌ 失败: {e}")
    
    print("\n2. Alice 尝试添加第二首不同歌曲（应该被阻止）")
    try:
        position = await queue_manager.add_song(songs[1], alice)
        print(f"   ❌ 不应该成功: {position}")
    except QueueFairnessError as e:
        print(f"   ✅ 队列公平性阻止: {e}")
    
    print("\n3. Bob 添加歌曲（应该成功，因为是不同用户）")
    try:
        position = await queue_manager.add_song(songs[1], bob)
        print(f"   ✅ 成功添加 '{songs[1].title}' (位置: {position})")
    except Exception as e:
        print(f"   ❌ 失败: {e}")
    
    print("\n4. Bob 尝试添加第二首歌曲（应该被阻止）")
    try:
        position = await queue_manager.add_song(songs[2], bob)
        print(f"   ❌ 不应该成功: {position}")
    except QueueFairnessError as e:
        print(f"   ✅ 队列公平性阻止: {e}")
    
    print("\n5. 查看当前队列状态")
    queue_info = await queue_manager.get_queue_info()
    print(f"   队列长度: {queue_info['queue_length']}")
    print(f"   总时长: {queue_info['total_duration']} 秒")
    
    print("\n6. 查看用户状态")
    alice_status = queue_manager.get_user_queue_status(alice)
    bob_status = queue_manager.get_user_queue_status(bob)
    
    print(f"   Alice: {alice_status['pending_songs']} 首待播放, 可添加: {alice_status['can_add_song']}")
    print(f"   Bob: {bob_status['pending_songs']} 首待播放, 可添加: {bob_status['can_add_song']}")


async def demo_playback_lifecycle():
    """演示播放生命周期中的公平性控制"""
    print("\n\n🎧 播放生命周期公平性演示")
    print("=" * 50)
    
    # 创建新的队列管理器
    queue_manager = QueueManager(guild_id=12346)
    alice = create_mock_user(1001, "Alice")
    
    songs = [
        create_audio_info("First Song", 180, "https://www.youtube.com/watch?v=first", "Artist 1"),
        create_audio_info("Second Song", 200, "https://www.youtube.com/watch?v=second", "Artist 2"),
    ]
    
    print("1. Alice 添加歌曲到队列")
    position = await queue_manager.add_song(songs[0], alice)
    print(f"   ✅ 歌曲添加成功: 位置 {position}")
    
    print("\n2. 歌曲开始播放")
    song = await queue_manager.get_next_song()
    print(f"   ✅ 开始播放: {song.title}")
    
    print("\n3. 播放期间 Alice 尝试添加新歌曲（应该被阻止）")
    try:
        await queue_manager.add_song(songs[1], alice)
        print("   ❌ 不应该成功")
    except QueueFairnessError as e:
        print(f"   ✅ 播放期间被阻止: {e}")
    
    print("\n4. 查看 Alice 的状态")
    status = queue_manager.get_user_queue_status(alice)
    print(f"   正在播放: {status['is_currently_playing']}")
    print(f"   待播放歌曲: {status['pending_songs']}")
    print(f"   可以添加歌曲: {status['can_add_song']}")
    
    print("\n5. 歌曲播放完成")
    queue_manager.notify_song_finished(song)
    print("   ✅ 播放完成通知")
    
    print("\n6. 播放完成后 Alice 可以添加新歌曲")
    try:
        position = await queue_manager.add_song(songs[1], alice)
        print(f"   ✅ 播放完成后添加成功: 位置 {position}")
    except Exception as e:
        print(f"   ❌ 失败: {e}")


async def demo_spam_prevention():
    """演示垃圾信息防护"""
    print("\n\n🛡️ 垃圾信息防护演示")
    print("=" * 50)
    
    # 创建新的队列管理器
    queue_manager = QueueManager(guild_id=12347)
    spammer = create_mock_user(1001, "Spammer")
    normal_user = create_mock_user(1002, "NormalUser")
    
    # 创建多首不同歌曲（模拟垃圾信息攻击）
    spam_songs = [
        create_audio_info(f"Spam Song {i}", 180 + i*10, f"https://www.youtube.com/watch?v=spam{i}", f"Spam Artist {i}")
        for i in range(1, 6)
    ]
    
    print("1. 垃圾信息用户尝试快速添加多首歌曲")
    
    # 第一首歌曲应该成功
    try:
        position = await queue_manager.add_song(spam_songs[0], spammer)
        print(f"   ✅ 第1首歌曲成功: '{spam_songs[0].title}' (位置: {position})")
    except Exception as e:
        print(f"   ❌ 第1首歌曲失败: {e}")
    
    # 后续歌曲应该被阻止
    for i, song in enumerate(spam_songs[1:], 2):
        try:
            position = await queue_manager.add_song(song, spammer)
            print(f"   ❌ 第{i}首歌曲不应该成功: {position}")
        except QueueFairnessError:
            print(f"   ✅ 第{i}首歌曲被阻止: '{song.title}'")
    
    print("\n2. 正常用户仍然可以添加歌曲")
    normal_song = create_audio_info("Normal Song", 200, "https://www.youtube.com/watch?v=normal", "Normal Artist")
    try:
        position = await queue_manager.add_song(normal_song, normal_user)
        print(f"   ✅ 正常用户添加成功: '{normal_song.title}' (位置: {position})")
    except Exception as e:
        print(f"   ❌ 正常用户失败: {e}")
    
    print("\n3. 最终队列状态")
    queue_info = await queue_manager.get_queue_info()
    print(f"   队列长度: {queue_info['queue_length']} (应该是2，不是6)")
    print(f"   垃圾信息攻击被成功阻止！")


async def demo_duplicate_detection_integration():
    """演示重复检测与队列公平性的集成"""
    print("\n\n🔄 重复检测集成演示")
    print("=" * 50)
    
    # 创建新的队列管理器
    queue_manager = QueueManager(guild_id=12348)
    user = create_mock_user(1001, "TestUser")
    
    song = create_audio_info("Test Song", 180, "https://www.youtube.com/watch?v=test", "Test Artist")
    
    print("1. 用户添加歌曲")
    position = await queue_manager.add_song(song, user)
    print(f"   ✅ 歌曲添加成功: 位置 {position}")
    
    print("\n2. 用户尝试添加相同歌曲（重复检测）")
    try:
        await queue_manager.add_song(song, user)
        print("   ❌ 不应该成功")
    except DuplicateSongError as e:
        print(f"   ✅ 重复检测阻止: {e}")
    
    print("\n3. 用户尝试添加不同歌曲（队列公平性）")
    different_song = create_audio_info("Different Song", 200, "https://www.youtube.com/watch?v=different", "Different Artist")
    try:
        await queue_manager.add_song(different_song, user)
        print("   ❌ 不应该成功")
    except QueueFairnessError as e:
        print(f"   ✅ 队列公平性阻止: {e}")
    
    print("\n4. 歌曲播放完成后，用户可以添加任何歌曲")
    song_playing = await queue_manager.get_next_song()
    queue_manager.notify_song_finished(song_playing)
    
    # 现在可以添加不同歌曲
    position = await queue_manager.add_song(different_song, user)
    print(f"   ✅ 播放完成后添加不同歌曲成功: 位置 {position}")
    
    # 也可以重新添加原来的歌曲
    song_playing2 = await queue_manager.get_next_song()
    queue_manager.notify_song_finished(song_playing2)
    
    position = await queue_manager.add_song(song, user)
    print(f"   ✅ 播放完成后重新添加原歌曲成功: 位置 {position}")


async def demo_comprehensive_status():
    """演示综合状态查询"""
    print("\n\n📊 综合状态查询演示")
    print("=" * 50)
    
    # 创建队列管理器和多个用户
    queue_manager = QueueManager(guild_id=12349)
    users = [
        create_mock_user(1001, "Alice"),
        create_mock_user(1002, "Bob"),
        create_mock_user(1003, "Charlie"),
    ]
    
    songs = [
        create_audio_info("Alice's Song", 180, "https://www.youtube.com/watch?v=alice", "Alice Artist"),
        create_audio_info("Bob's Song", 200, "https://www.youtube.com/watch?v=bob", "Bob Artist"),
    ]
    
    print("1. 设置测试场景")
    # Alice 添加歌曲
    await queue_manager.add_song(songs[0], users[0])
    print("   ✅ Alice 添加了歌曲")
    
    # Bob 添加歌曲
    await queue_manager.add_song(songs[1], users[1])
    print("   ✅ Bob 添加了歌曲")
    
    # Alice 的歌曲开始播放
    alice_song = await queue_manager.get_next_song()
    print(f"   ✅ Alice 的歌曲开始播放: {alice_song.title}")
    
    print("\n2. 查看所有用户状态")
    for user in users:
        status = queue_manager.get_user_queue_status(user)
        print(f"   {user.display_name}:")
        print(f"     - 待播放歌曲: {status['pending_songs']}")
        print(f"     - 正在播放: {status['is_currently_playing']}")
        print(f"     - 可以添加歌曲: {status['can_add_song']}")
        if status['pending_song_titles']:
            print(f"     - 待播放列表: {', '.join(status['pending_song_titles'])}")
    
    print("\n3. 系统统计信息")
    stats = queue_manager.get_duplicate_detection_stats()
    print(f"   跟踪的歌曲总数: {stats['total_tracked_songs']}")
    print(f"   有歌曲的用户数: {stats['total_users_with_songs']}")
    print(f"   有待播放歌曲的用户数: {stats['total_users_with_pending']}")
    print(f"   当前播放用户ID: {stats['currently_playing_user']}")


async def main():
    """主演示函数"""
    print("🎵 Odysseia-Similu 队列公平性系统演示")
    print("=" * 70)
    print("新系统特性：")
    print("✅ 防止用户同时添加多首歌曲到队列")
    print("✅ 保持多用户公平性")
    print("✅ 集成原有重复检测功能")
    print("✅ 提供详细的用户状态查询")
    print("=" * 70)
    
    await demo_queue_fairness_basics()
    await demo_playback_lifecycle()
    await demo_spam_prevention()
    await demo_duplicate_detection_integration()
    await demo_comprehensive_status()
    
    print("\n\n🎉 演示完成！")
    print("=" * 70)
    print("队列公平性系统成功实现了以下目标：")
    print("🛡️ 防止队列垃圾信息攻击")
    print("⚖️ 确保所有用户的公平访问")
    print("🔄 保持原有重复检测功能")
    print("📊 提供全面的状态监控")
    print("🎯 优雅的用户体验和反馈")


if __name__ == "__main__":
    asyncio.run(main())
