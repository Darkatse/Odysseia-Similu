# Odysseia-Similu 架构重构迁移指南

## 概述

本指南帮助开发者从旧的单体架构迁移到新的模块化架构。新架构保持了完全的向后兼容性，同时提供了更好的可维护性和扩展性。

## 快速开始

### 新架构导入方式

```python
# 旧方式
from similubot.music import MusicPlayer, QueueManager, Song

# 新方式 (推荐)
from similubot.core.interfaces import AudioInfo, SongInfo
from similubot.provider import AudioProviderFactory
from similubot.queue import QueueManager, Song, PersistenceManager
from similubot.playback import VoiceManager, PlaybackEngine
```

### 基本使用示例

```python
# 创建播放引擎 (新架构的核心)
from similubot.playback import PlaybackEngine

playback_engine = PlaybackEngine(bot, temp_dir="./temp", config=config)

# 初始化持久化系统
await playback_engine.initialize_persistence()

# 添加歌曲到队列
success, position, error = await playback_engine.add_song_to_queue(
    url="https://www.youtube.com/watch?v=example",
    requester=ctx.author
)

# 连接到用户语音频道
success, error = await playback_engine.connect_to_user_channel(ctx.author)

# 获取队列信息
queue_info = playback_engine.get_queue_info(ctx.guild.id)
```

## 模块迁移指南

### 1. 音频提供者 (Audio Providers)

#### 旧方式
```python
from similubot.music import YouTubeClient, CatboxClient

youtube_client = YouTubeClient(temp_dir, config)
catbox_client = CatboxClient(temp_dir)

# 检查URL支持
if youtube_client.is_supported_url(url):
    audio_info = await youtube_client.extract_audio_info(url)
```

#### 新方式
```python
from similubot.provider import AudioProviderFactory

provider_factory = AudioProviderFactory(temp_dir, config)

# 自动检测并处理URL
if provider_factory.is_supported_url(url):
    audio_info = await provider_factory.extract_audio_info(url)
    
# 或者获取特定提供者
youtube_provider = provider_factory.get_provider_by_name('youtube')
```

### 2. 队列管理 (Queue Management)

#### 旧方式
```python
from similubot.music import QueueManager

queue_manager = QueueManager(guild_id)
await queue_manager.add_song(audio_info, requester)
```

#### 新方式
```python
from similubot.queue import QueueManager, PersistenceManager

# 创建持久化管理器
persistence_manager = PersistenceManager("data")

# 创建队列管理器 (支持持久化)
queue_manager = QueueManager(guild_id, persistence_manager)
await queue_manager.add_song(audio_info, requester)

# 恢复队列状态
success = await queue_manager.restore_from_persistence(guild)
```

### 3. 语音管理 (Voice Management)

#### 旧方式
```python
from similubot.music import VoiceManager

voice_manager = VoiceManager(bot)
success, error = await voice_manager.connect_to_user_channel(user)
```

#### 新方式
```python
from similubot.playback import VoiceManager

voice_manager = VoiceManager(bot)
success, error = await voice_manager.connect_to_user_channel(user)

# 新增功能: 获取连接信息
connection_info = voice_manager.get_connection_info(guild_id)
```

### 4. 播放控制 (Playback Control)

#### 旧方式
```python
from similubot.music import MusicPlayer

music_player = MusicPlayer(bot, temp_dir, config)
success, position, error = await music_player.add_song_to_queue(url, requester)
```

#### 新方式
```python
from similubot.playback import PlaybackEngine

playback_engine = PlaybackEngine(bot, temp_dir, config)
success, position, error = await playback_engine.add_song_to_queue(url, requester)

# 新增功能: 更好的错误处理和状态管理
success, next_song, error = await playback_engine.skip_song(guild_id)
```

## 接口变更说明

### 1. 数据模型变更

#### Song 类增强
```python
from similubot.queue import Song

# 新增方法
song_dict = song.to_dict()  # 序列化
song = Song.from_dict(song_dict, guild)  # 反序列化
display_info = song.get_display_info()  # 显示信息
```

#### AudioInfo 标准化
```python
from similubot.core.interfaces import AudioInfo

# 统一的音频信息结构
audio_info = AudioInfo(
    title="歌曲标题",
    duration=180,
    url="https://example.com/audio.mp3",
    uploader="上传者",
    file_path="/path/to/file",  # 可选
    thumbnail_url="https://example.com/thumb.jpg",  # 可选
    file_size=1024000,  # 可选
    file_format="mp3"  # 可选
)
```

### 2. 异步方法变更

大部分方法保持异步，但增加了更好的错误处理：

```python
# 统一的返回格式
success, result, error = await method_call()

if success:
    # 处理成功结果
    process_result(result)
else:
    # 处理错误
    handle_error(error)
```

### 3. 配置管理

配置管理保持不变，但新架构提供了更好的配置验证：

```python
from similubot.utils.config_manager import ConfigManager

config = ConfigManager('config.yaml')

# 新架构会自动验证配置
playback_engine = PlaybackEngine(bot, temp_dir, config)
```

## 兼容性适配器

为了确保平滑迁移，提供了兼容性适配器：

### MusicPlayer 适配器
```python
# 旧代码可以继续使用
from similubot.music import MusicPlayer

# 内部使用新架构，但保持旧接口
music_player = MusicPlayer(bot, temp_dir, config)
```

### 渐进式迁移策略

1. **第一阶段**: 保持旧导入，内部使用新架构
2. **第二阶段**: 逐步更新导入语句
3. **第三阶段**: 使用新架构的高级功能

## 新功能和改进

### 1. 更好的错误处理
```python
# 详细的错误信息
success, result, error = await playback_engine.add_song_to_queue(url, requester)
if not success:
    await ctx.send(f"添加歌曲失败: {error}")
```

### 2. 增强的持久化
```python
# 获取持久化统计信息
stats = persistence_manager.get_persistence_stats()
print(f"队列文件数: {stats['queue_files']}")
print(f"总大小: {stats['total_size_bytes']} 字节")
```

### 3. 模块化配置
```python
# 每个模块可以独立配置
youtube_provider = YouTubeProvider(temp_dir, config)
catbox_provider = CatboxProvider(temp_dir)

# 自定义提供者工厂
custom_factory = AudioProviderFactory(temp_dir, config)
custom_factory.add_provider(my_custom_provider)
```

### 4. 更好的测试支持
```python
# 使用接口进行模拟测试
from unittest.mock import Mock
from similubot.core.interfaces import IQueueManager

mock_queue_manager = Mock(spec=IQueueManager)
playback_engine = PlaybackEngine(bot, temp_dir, config)
playback_engine._queue_managers[guild_id] = mock_queue_manager
```

## 性能优化

### 1. 按需加载
```python
# 只加载需要的提供者
from similubot.provider import YouTubeProvider  # 只加载YouTube支持

# 或者使用工厂自动管理
from similubot.provider import AudioProviderFactory  # 加载所有支持的提供者
```

### 2. 内存管理
```python
# 新架构提供更好的资源清理
await playback_engine.cleanup_all_connections()
cleanup_results = provider_factory.cleanup_temp_files()
```

## 故障排除

### 常见问题

#### 1. 导入错误
```python
# 错误: ImportError: No module named 'similubot.provider'
# 解决: 确保新模块已正确安装

# 检查模块是否存在
import sys
print('similubot.provider' in sys.modules)
```

#### 2. 接口不兼容
```python
# 错误: 方法签名不匹配
# 解决: 检查新接口文档，更新方法调用

# 旧方式
result = await old_method(arg1, arg2)

# 新方式
success, result, error = await new_method(arg1, arg2)
```

#### 3. 配置问题
```python
# 错误: 配置未正确加载
# 解决: 检查配置文件格式和路径

from similubot.utils.config_manager import ConfigManager
config = ConfigManager('config.yaml')
print(config.get('youtube.po_token'))  # 检查配置是否加载
```

## 最佳实践

### 1. 使用依赖注入
```python
# 推荐: 通过构造函数注入依赖
class MyMusicCommand:
    def __init__(self, playback_engine: PlaybackEngine):
        self.playback_engine = playback_engine

# 避免: 直接创建依赖
class MyMusicCommand:
    def __init__(self):
        self.playback_engine = PlaybackEngine(...)  # 不推荐
```

### 2. 使用接口编程
```python
from similubot.core.interfaces import IQueueManager

def process_queue(queue_manager: IQueueManager):
    # 使用接口，不依赖具体实现
    return queue_manager.get_queue_length()
```

### 3. 错误处理
```python
# 统一的错误处理模式
try:
    success, result, error = await operation()
    if not success:
        logger.error(f"操作失败: {error}")
        return False
    return result
except Exception as e:
    logger.exception(f"未预期的错误: {e}")
    return False
```

## 总结

新架构提供了更好的可维护性、可扩展性和可测试性，同时保持了完全的向后兼容性。建议采用渐进式迁移策略，逐步享受新架构带来的优势。

如有任何问题，请参考架构文档或提交Issue。
