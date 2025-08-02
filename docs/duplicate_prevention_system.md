# 重复检测系统 (Duplicate Prevention System)

## 概述

重复检测系统是 Odysseia-Similu 音乐机器人的一个核心功能，旨在防止用户在队列中添加重复的歌曲。该系统提供了智能的歌曲识别、用户级别的重复跟踪，以及高效的性能优化。

## 核心功能

### 1. 重复检测 (Duplicate Detection)
- **歌曲识别**: 基于标题、时长和URL的组合来唯一标识歌曲
- **标题标准化**: 自动处理标题变化（如 "Official Video", "Lyrics" 等后缀）
- **URL解析**: 智能提取YouTube视频ID和Catbox文件名作为关键标识符

### 2. 用户级别跟踪 (User-Specific Tracking)
- **独立跟踪**: 每个用户的重复请求独立跟踪
- **多用户支持**: 不同用户可以添加相同的歌曲
- **自动清理**: 歌曲播放完成后自动从跟踪列表中移除

### 3. 队列集成 (Queue Integration)
- **无缝集成**: 与现有队列管理系统完全集成
- **状态同步**: 队列操作自动更新重复检测状态
- **持久化支持**: 支持队列恢复时重建重复检测状态

## 架构设计

### 组件结构

```
similubot/queue/
├── duplicate_detector.py    # 核心重复检测逻辑
├── queue_manager.py        # 队列管理器（已集成重复检测）
└── song.py                # 歌曲数据模型
```

### 核心类

#### `SongIdentifier`
歌曲标识符数据类，用于唯一标识歌曲：
- `normalized_title`: 标准化后的歌曲标题
- `duration`: 歌曲时长（秒）
- `url_key`: URL关键标识符

#### `DuplicateDetector`
重复检测器核心类：
- 管理用户歌曲映射
- 提供高效的重复检查
- 支持歌曲添加/移除操作

#### `QueueManager` (已扩展)
队列管理器，集成了重复检测功能：
- 在添加歌曲时自动检查重复
- 在移除歌曲时更新重复检测状态
- 提供重复检测相关的查询接口

## 使用示例

### 基本用法

```python
from similubot.queue.queue_manager import QueueManager, DuplicateSongError
from similubot.core.interfaces import AudioInfo

# 创建队列管理器
queue_manager = QueueManager(guild_id=12345)

# 创建音频信息
audio_info = AudioInfo(
    title="Test Song",
    duration=180,
    url="https://www.youtube.com/watch?v=test123",
    uploader="Test Channel"
)

# 添加歌曲
try:
    position = await queue_manager.add_song(audio_info, user)
    print(f"歌曲添加成功，位置: {position}")
except DuplicateSongError as e:
    print(f"重复歌曲: {e}")
```

### 检查重复

```python
# 检查是否为重复歌曲
is_duplicate = queue_manager.check_duplicate_for_user(audio_info, user)
if is_duplicate:
    print("这首歌曲已经在队列中")
```

### 获取统计信息

```python
# 获取用户歌曲数量
user_count = queue_manager.get_user_song_count(user)
print(f"用户当前有 {user_count} 首歌曲在队列中")

# 获取重复检测统计
stats = queue_manager.get_duplicate_detection_stats()
print(f"总跟踪歌曲: {stats['total_tracked_songs']}")
print(f"有歌曲的用户数: {stats['total_users_with_songs']}")
```

## 歌曲识别算法

### 标题标准化

系统会自动标准化歌曲标题，移除以下内容：
- 官方标记: "(Official Video)", "[Official Audio]"
- 歌词标记: "(Lyrics)", "[Lyrics]"
- 质量标记: "(HD)", "[4K]"
- 重制标记: "(Remastered)"
- 特殊字符和多余空格

### URL关键字提取

- **YouTube**: 提取视频ID (如: `dQw4w9WgXcQ`)
- **Catbox**: 提取文件名 (如: `audio.mp3`)
- **其他**: 使用完整URL

### 重复判定逻辑

两首歌曲被认为是重复的，当且仅当：
1. 标准化标题相同
2. 时长相同
3. URL关键字相同

## 性能特性

### 时间复杂度
- **添加歌曲**: O(1) 平均情况
- **重复检查**: O(1) 平均情况
- **移除歌曲**: O(1) 平均情况

### 空间复杂度
- **内存使用**: O(n) 其中 n 是队列中的歌曲数量
- **数据结构**: 使用哈希表和集合确保高效查找

### 性能测试结果
- **添加性能**: ~51,000 歌曲/秒
- **检查性能**: ~53,000 检查/秒
- **移除性能**: ~66,000 移除/秒

## 错误处理

### `DuplicateSongError`
当用户尝试添加重复歌曲时抛出：
```python
class DuplicateSongError(Exception):
    def __init__(self, message: str, song_title: str, user_name: str):
        super().__init__(message)
        self.song_title = song_title
        self.user_name = user_name
```

### 用户反馈
系统提供友好的用户反馈消息：
- 重复歌曲提示
- 等待播放完成的建议
- 清晰的错误说明

## 配置和扩展

### 自定义标题标准化
可以通过修改 `DuplicateDetector._normalize_title()` 方法来自定义标题标准化规则。

### 自定义URL解析
可以通过修改 `DuplicateDetector._extract_url_key()` 方法来支持新的音频源。

### 集成新的队列操作
新的队列操作需要确保调用相应的重复检测方法来保持状态同步。

## 测试

### 单元测试
- `tests/test_duplicate_detection.py`: 核心功能测试
- 覆盖所有重复检测逻辑
- 包含边界情况和错误处理测试

### 集成测试
- `tests/test_duplicate_integration.py`: 完整工作流程测试
- 测试与音乐命令的集成
- 验证用户反馈消息

### 性能测试
- 大规模数据测试 (1000+ 歌曲)
- 并发操作测试
- 内存使用监控

## 最佳实践

1. **及时清理**: 确保歌曲播放完成后及时从重复检测器中移除
2. **状态同步**: 所有队列操作都应该更新重复检测状态
3. **错误处理**: 妥善处理 `DuplicateSongError` 并提供用户友好的反馈
4. **性能监控**: 定期监控重复检测的性能影响
5. **测试覆盖**: 确保新功能有充分的测试覆盖

## 故障排除

### 常见问题

1. **重复检测不工作**
   - 检查是否正确集成了 `DuplicateDetector`
   - 确认队列操作调用了相应的重复检测方法

2. **性能问题**
   - 检查是否有内存泄漏（未清理的歌曲跟踪）
   - 监控重复检测器的大小

3. **误报重复**
   - 检查标题标准化逻辑
   - 验证URL解析是否正确

### 调试工具

```python
# 获取重复检测器状态
stats = queue_manager.get_duplicate_detection_stats()
print(f"调试信息: {stats}")

# 检查特定歌曲的重复信息
duplicate_info = queue_manager._duplicate_detector.get_duplicate_info(audio_info)
if duplicate_info:
    song_id, user_ids = duplicate_info
    print(f"歌曲 {song_id} 被用户 {user_ids} 请求")
```

## 未来改进

1. **智能相似度检测**: 基于音频指纹的更精确重复检测
2. **用户偏好**: 允许用户自定义重复检测行为
3. **统计分析**: 提供重复请求的统计分析
4. **缓存优化**: 进一步优化大规模场景下的性能
