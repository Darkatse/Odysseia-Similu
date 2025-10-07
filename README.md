# Odysseia-Similu 音乐机器人

专为类脑/Odysseia Discord 社区打造的音乐播放机器人，支持 YouTube 视频和 Catbox 音频文件的播放。具备智能重复检测系统，提供优质的多用户音乐体验。

## 功能特性

### 🎵 核心音乐功能
- 🎵 支持 YouTube 视频音频播放
- 🎶 支持 Catbox 音频文件播放
- 📋 智能音乐队列管理
- ⏯️ 播放控制（播放、暂停、跳过、停止）
- 🎯 精确的时间定位功能
- 📊 实时播放进度显示
- 🔊 语音频道自动连接
- 🎧 支持多种音频格式（MP3、WAV、OGG、M4A、FLAC、AAC、OPUS、WMA）

### 🚫 智能重复检测系统 ⭐ **新功能**
- 🎯 **用户特定重复检测**: 防止同一用户重复添加相同歌曲
- 🧠 **智能歌曲识别**: 自动识别歌曲变体（官方版本、HD版本、歌词版本等）
- 👥 **多用户友好**: 不同用户可以添加相同歌曲
- 📏 **队列长度阈值**: 短队列时允许重复，长队列时保持保护
- 🔄 **自动清理**: 歌曲播放完成后自动清理跟踪数据
- 💬 **清晰反馈**: 提供中文用户友好的错误提示

## 系统要求

- Python 3.8 或更高版本
- FFmpeg（必须安装并添加到系统 PATH）
- Discord 机器人令牌
- 稳定的网络连接

## 安装步骤

1. 克隆仓库：
   ```bash
   git clone https://github.com/Darkatse/Odysseia-Similu.git
   cd Odysseia-Similu
   ```

2. 安装 Python 依赖包：
   ```bash
   pip install -r requirements.txt
   ```

3. 创建配置文件：
   ```bash
   cp config/config.yaml.example config/config.yaml
   ```

4. 编辑配置文件并添加你的 Discord 机器人令牌：
   ```yaml
   discord:
     token: "你的_DISCORD_机器人_令牌"
   ```

## 配置说明

`config/config.yaml` 文件包含机器人的所有配置选项：

### 基础配置
- `discord.token`: Discord 机器人令牌
- `discord.command_prefix`: 命令前缀（默认：`!`）
- `download.temp_dir`: 临时文件存储目录

### 音乐播放配置
- `music.enabled`: 是否启用音乐功能（默认：true）
- `music.max_queue_size`: 每个服务器的最大队列长度（默认：100）
- `music.max_song_duration`: 单首歌曲最大时长（秒，默认：3600）
- `music.auto_disconnect_timeout`: 无活动自动断开时间（秒，默认：300）
- `music.volume`: 默认播放音量（0.0-1.0，默认：0.5）

### 重复检测配置 ⭐ **新功能**
- `duplicate_detection.queue_length_threshold`: 队列长度阈值（默认：5）
  - 当队列长度小于此值时，允许用户重复添加歌曲
  - 当队列长度大于等于此值时，保持重复检测保护
  - **小型服务器** (< 20用户): 推荐设置为 3
  - **中型服务器** (20-100用户): 推荐设置为 5（默认）
  - **大型服务器** (> 100用户): 推荐设置为 7

### 日志配置
- `logging.level`: 日志级别（DEBUG、INFO、WARNING、ERROR、CRITICAL）
- `logging.file`: 日志文件路径
- `logging.max_size`: 日志文件最大大小（字节）
- `logging.backup_count`: 保留的备份日志文件数量

## 使用方法

1. 启动机器人：
   ```bash
   python main.py
   ```

2. 在 Discord 中使用以下命令：
   - `!music <YouTube链接>`: 播放 YouTube 视频音频
   - `!music <Catbox音频链接>`: 播放 Catbox 音频文件
   - `!music queue`: 显示当前播放队列
   - `!music now`: 显示当前播放歌曲和进度
   - `!music skip`: 跳过当前歌曲
   - `!music stop`: 停止播放并清空队列
   - `!music jump <数字>`: 跳转到队列中的指定位置
   - `!music seek <时间>`: 跳转到指定时间位置（如：1:30、+30、-1:00）
   - `!about`: 显示机器人信息
   - `!help`: 显示帮助信息

## 项目结构

```
Odysseia-Similu/
├── config/
│   └── config.yaml.example    # 配置文件模板
├── docs/                      # 项目文档
│   ├── architecture.md        # 技术架构文档
│   ├── api.md                # API 文档
│   ├── configuration.md       # 配置指南
│   ├── development.md         # 开发指南
│   └── prd.md                # 产品需求文档
├── similubot/
│   ├── bot.py                 # 主要机器人实现
│   ├── commands/
│   │   ├── music_commands.py  # 音乐命令处理
│   │   └── general_commands.py # 通用命令处理
│   ├── core/
│   │   ├── interfaces.py      # 核心接口定义
│   │   └── event_handler.py   # 事件处理器
│   ├── duplicate/             # 重复检测系统 ⭐ 新模块
│   │   ├── __init__.py        # 模块导出
│   │   ├── duplicate_detector.py # 核心重复检测逻辑
│   │   └── song_identifier.py # 歌曲标识符生成器
│   ├── playback/              # 播放引擎
│   │   ├── playback_engine.py # 播放引擎核心
│   │   ├── voice_manager.py   # 语音连接管理
│   │   └── seek_manager.py    # 时间定位管理
│   ├── provider/              # 音频提供者
│   │   ├── audio_provider_factory.py # 音频提供者工厂
│   │   ├── youtube_provider.py # YouTube 提供者
│   │   └── catbox_provider.py # Catbox 提供者
│   ├── queue/                 # 队列管理
│   │   ├── queue_manager.py   # 队列管理器
│   │   ├── song.py           # 歌曲数据模型
│   │   └── persistence_manager.py # 持久化管理
│   ├── progress/
│   │   └── base.py           # 进度显示基类
│   └── utils/
│       ├── config_manager.py  # 配置管理
│       └── logger.py          # 日志功能
├── tests/                     # 单元测试
├── .gitignore
├── README.md
├── requirements.txt
└── main.py                    # 程序入口
```

## 开发相关

### 运行测试

```bash
pytest
```

### 音乐命令示例

```bash
# 播放 YouTube 视频
!music https://www.youtube.com/watch?v=dQw4w9WgXcQ

# 播放 Catbox 音频文件
!music https://files.catbox.moe/example.mp3

# 查看播放队列
!music queue

# 显示当前播放进度
!music now

# 跳过当前歌曲
!music skip

# 跳转到队列第3首歌
!music jump 3

# 跳转到1分30秒位置
!music seek 1:30

# 向前快进30秒
!music seek +30

# 向后倒退1分钟
!music seek -1:00
```

### 重复检测系统示例 ⭐ **新功能**

```bash
# 场景1: 短队列时允许重复添加
用户A: !music https://www.youtube.com/watch?v=example
机器人: ✅ 已添加到队列位置 #1: 示例歌曲

用户A: !music https://www.youtube.com/watch?v=example  # 队列仍然较短
机器人: ✅ 已添加到队列位置 #2: 示例歌曲  # 允许重复添加

# 场景2: 长队列时的重复保护
用户A: !music https://www.youtube.com/watch?v=example
机器人: ✅ 已添加到队列位置 #6: 示例歌曲

用户A: !music https://www.youtube.com/watch?v=example  # 队列已较长
机器人: ❌ 你已经请求过这首歌曲了！**示例歌曲** 已在队列中，请等待播放完成后再次请求。

# 场景3: 不同用户可以添加相同歌曲
用户A: !music https://www.youtube.com/watch?v=example
机器人: ✅ 已添加到队列位置 #1: 示例歌曲

用户B: !music https://www.youtube.com/watch?v=example  # 不同用户
机器人: ✅ 已添加到队列位置 #2: 示例歌曲  # 始终允许

# 场景4: 智能识别歌曲变体
用户A: !music https://www.youtube.com/watch?v=example
机器人: ✅ 已添加到队列位置 #1: 示例歌曲

用户A: !music https://www.youtube.com/watch?v=example_hd  # HD版本
机器人: ❌ 你已经请求过相似的歌曲了！**示例歌曲** 已在队列中，请等待播放完成后再次请求。
```

## 许可证

本项目采用 Apache 2.0 许可证 - 详情请参阅 LICENSE 文件。

## 致谢

### 核心依赖库
- [discord.py](https://github.com/Rapptz/discord.py) - Python Discord API 封装库
- [pytubefix](https://github.com/JuanBindez/pytubefix) - YouTube 视频下载库
- [FFmpeg](https://ffmpeg.org/) - 音频/视频处理工具
- [bilibili-api-python](https://github.com/nemo2011/bilibili-api) Python Bilibili API库

### 网易云音乐支持
- [保罗 API](https://api.paugram.com/help/netease) - 提供网易云音乐 API 代理服务，解决海外访问限制
- [pyncm](https://github.com/mos9527/pyncm) - Python 网易云音乐 API 库，为会员认证和加密算法提供参考实现

### SoundCloud下载支持
- [Soundcloud-lib](https://github.com/3jackdaws/soundcloud-lib) - Python SoundCloud API库，帮助实现下载功能

## 支持

如果在使用过程中遇到问题，请在 GitHub 上提交 Issue 或联系开发者。

---

**为类脑/Odysseia Discord 社区专门定制** 🎵
