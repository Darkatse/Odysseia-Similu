#!/usr/bin/env python3
"""
重复检测系统演示脚本

展示重复检测系统的核心功能和使用方法。
"""

import asyncio
import sys
import os
from unittest.mock import MagicMock

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from similubot.queue.queue_manager import QueueManager, DuplicateSongError
from similubot.queue.duplicate_detector import DuplicateDetector
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


async def demo_basic_functionality():
    """演示基本功能"""
    print("🎵 重复检测系统基本功能演示")
    print("=" * 50)
    
    # 创建队列管理器
    queue_manager = QueueManager(guild_id=12345)
    
    # 创建测试用户
    alice = create_mock_user(1001, "Alice")
    bob = create_mock_user(1002, "Bob")
    
    # 创建测试歌曲
    song1 = create_audio_info(
        "Never Gonna Give You Up",
        213,
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "Rick Astley"
    )
    
    song2 = create_audio_info(
        "Bohemian Rhapsody",
        355,
        "https://www.youtube.com/watch?v=fJ9rUzIMcZQ",
        "Queen"
    )
    
    # 演示1: 成功添加歌曲
    print("1. 添加歌曲到队列")
    try:
        position = await queue_manager.add_song(song1, alice)
        print(f"   ✅ Alice 添加了 '{song1.title}' (位置: {position})")
    except DuplicateSongError as e:
        print(f"   ❌ 错误: {e}")
    
    # 演示2: 重复歌曲检测
    print("\n2. 重复歌曲检测")
    try:
        position = await queue_manager.add_song(song1, alice)
        print(f"   ❌ 不应该成功: {position}")
    except DuplicateSongError as e:
        print(f"   ✅ 检测到重复: {e}")
    
    # 演示3: 不同用户可以添加相同歌曲
    print("\n3. 不同用户添加相同歌曲")
    try:
        position = await queue_manager.add_song(song1, bob)
        print(f"   ✅ Bob 添加了相同歌曲 '{song1.title}' (位置: {position})")
    except DuplicateSongError as e:
        print(f"   ❌ 错误: {e}")
    
    # 演示4: 添加不同歌曲
    print("\n4. 添加不同歌曲")
    try:
        position = await queue_manager.add_song(song2, alice)
        print(f"   ✅ Alice 添加了 '{song2.title}' (位置: {position})")
    except DuplicateSongError as e:
        print(f"   ❌ 错误: {e}")
    
    # 演示5: 查看队列状态
    print("\n5. 队列状态")
    queue_info = await queue_manager.get_queue_info()
    print(f"   队列长度: {queue_info['queue_length']}")
    print(f"   总时长: {queue_info['total_duration']} 秒")
    
    # 演示6: 重复检测统计
    print("\n6. 重复检测统计")
    stats = queue_manager.get_duplicate_detection_stats()
    print(f"   跟踪的歌曲总数: {stats['total_tracked_songs']}")
    print(f"   有歌曲的用户数: {stats['total_users_with_songs']}")
    print(f"   Alice 的歌曲数: {queue_manager.get_user_song_count(alice)}")
    print(f"   Bob 的歌曲数: {queue_manager.get_user_song_count(bob)}")


async def demo_title_normalization():
    """演示标题标准化功能"""
    print("\n\n🔤 标题标准化演示")
    print("=" * 50)
    
    detector = DuplicateDetector(guild_id=12345)
    alice = create_mock_user(1001, "Alice")
    
    # 创建标题变化的歌曲
    original_song = create_audio_info(
        "Test Song",
        180,
        "https://www.youtube.com/watch?v=test123",
        "Test Artist"
    )
    
    variations = [
        "Test Song (Official Video)",
        "Test Song [Official Audio]",
        "Test Song (Lyrics)",
        "Test Song - Official Video",
        "Test Song | Official Audio",
        "Test Song (HD)",
        "Test Song [4K]",
        "Test Song (Remastered)",
        "Test!@#$%^&*()Song",
        "   Test   Song   "
    ]
    
    # 添加原始歌曲
    detector.add_song_for_user(original_song, alice)
    print(f"原始歌曲: '{original_song.title}'")
    print(f"标准化后: '{detector._normalize_title(original_song.title)}'")
    
    print("\n标题变化检测:")
    for variation in variations:
        variant_song = create_audio_info(
            variation,
            180,
            "https://www.youtube.com/watch?v=test123",
            "Test Artist"
        )
        
        is_duplicate = detector.is_duplicate_for_user(variant_song, alice)
        normalized = detector._normalize_title(variation)
        status = "✅ 重复" if is_duplicate else "❌ 不重复"
        print(f"   '{variation}' -> '{normalized}' {status}")


async def demo_url_extraction():
    """演示URL关键字提取功能"""
    print("\n\n🔗 URL关键字提取演示")
    print("=" * 50)
    
    detector = DuplicateDetector(guild_id=12345)
    
    test_urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "http://youtube.com/watch?v=test123",
        "https://files.catbox.moe/abc123.mp3",
        "https://catbox.moe/c/def456.wav",
        "https://example.com/audio.mp3"
    ]
    
    for url in test_urls:
        key = detector._extract_url_key(url)
        print(f"   {url}")
        print(f"   -> {key}")
        print()


async def demo_queue_operations():
    """演示队列操作对重复检测的影响"""
    print("\n\n⚙️ 队列操作演示")
    print("=" * 50)
    
    queue_manager = QueueManager(guild_id=12345)
    alice = create_mock_user(1001, "Alice")
    
    song = create_audio_info(
        "Test Song",
        180,
        "https://www.youtube.com/watch?v=test123",
        "Test Artist"
    )
    
    # 添加歌曲
    print("1. 添加歌曲")
    position = await queue_manager.add_song(song, alice)
    print(f"   歌曲添加到位置: {position}")
    print(f"   用户歌曲数: {queue_manager.get_user_song_count(alice)}")
    
    # 尝试重复添加
    print("\n2. 尝试重复添加")
    try:
        await queue_manager.add_song(song, alice)
    except DuplicateSongError:
        print("   ✅ 重复检测生效")
    
    # 播放歌曲（从队列移除）
    print("\n3. 播放歌曲（从队列移除）")
    next_song = await queue_manager.get_next_song()
    print(f"   播放: {next_song.title}")
    print(f"   用户歌曲数: {queue_manager.get_user_song_count(alice)}")
    
    # 现在可以重新添加
    print("\n4. 重新添加相同歌曲")
    try:
        position = await queue_manager.add_song(song, alice)
        print(f"   ✅ 成功添加到位置: {position}")
    except DuplicateSongError as e:
        print(f"   ❌ 错误: {e}")


async def demo_performance():
    """演示性能特性"""
    print("\n\n⚡ 性能演示")
    print("=" * 50)
    
    import time
    
    detector = DuplicateDetector(guild_id=12345)
    
    # 创建大量测试数据
    users = [create_mock_user(1000 + i, f"User{i}") for i in range(100)]
    songs = [
        create_audio_info(
            f"Song {i}",
            180 + (i % 300),
            f"https://www.youtube.com/watch?v=test{i:04d}",
            f"Artist {i % 20}"
        )
        for i in range(1000)
    ]
    
    print(f"测试数据: {len(users)} 用户, {len(songs)} 歌曲")
    
    # 测试添加性能
    start_time = time.time()
    for i, song in enumerate(songs):
        user = users[i % len(users)]
        detector.add_song_for_user(song, user)
    
    add_time = time.time() - start_time
    print(f"添加性能: {len(songs)/add_time:.1f} 歌曲/秒")
    
    # 测试检查性能
    start_time = time.time()
    for i in range(1000):
        song = songs[i % len(songs)]
        user = users[i % len(users)]
        detector.is_duplicate_for_user(song, user)
    
    check_time = time.time() - start_time
    print(f"检查性能: {1000/check_time:.1f} 检查/秒")
    
    # 显示统计信息
    print(f"跟踪的歌曲总数: {detector.get_total_tracked_songs()}")
    print(f"有歌曲的用户数: {len(detector._user_songs)}")


async def main():
    """主演示函数"""
    print("🎵 Odysseia-Similu 重复检测系统演示")
    print("=" * 60)
    
    await demo_basic_functionality()
    await demo_title_normalization()
    await demo_url_extraction()
    await demo_queue_operations()
    await demo_performance()
    
    print("\n\n🎉 演示完成！")
    print("=" * 60)
    print("重复检测系统已成功集成到音乐机器人中。")
    print("用户现在无法添加重复的歌曲，提供了更好的队列管理体验。")


if __name__ == "__main__":
    asyncio.run(main())
