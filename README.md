# Odysseia-Similu 音乐机器人

专为类脑/Odysseia Discord 社区打造的音乐播放机器人，支持 YouTube 视频和 Catbox 音频文件的播放。

## 功能特性

- 🎵 支持 YouTube 视频音频播放
- 🎶 支持 Catbox 音频文件播放
- 📋 音乐队列管理
- ⏯️ 播放控制（播放、暂停、跳过、停止）
- 🎯 精确的时间定位功能
- 📊 实时播放进度显示
- 🔊 语音频道自动连接
- 🎧 支持多种音频格式（MP3、WAV、OGG、M4A、FLAC、AAC、OPUS、WMA）

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

- `discord.token`: Discord 机器人令牌
- `discord.command_prefix`: 命令前缀（默认：`!`）
- `download.temp_dir`: 临时文件存储目录
- `music.enabled`: 是否启用音乐功能（默认：true）
- `music.max_queue_size`: 每个服务器的最大队列长度（默认：100）
- `music.max_song_duration`: 单首歌曲最大时长（秒，默认：3600）
- `music.auto_disconnect_timeout`: 无活动自动断开时间（秒，默认：300）
- `music.volume`: 默认播放音量（0.0-1.0，默认：0.5）
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
│   └── config.yaml            # 配置文件
├── similubot/
│   ├── bot.py                 # 主要机器人实现
│   ├── commands/
│   │   ├── music_commands.py  # 音乐命令处理
│   │   └── general_commands.py # 通用命令处理
│   ├── core/
│   │   ├── command_registry.py # 命令注册系统
│   │   └── event_handler.py   # 事件处理器
│   ├── music/
│   │   ├── music_player.py    # 音乐播放器核心
│   │   ├── queue_manager.py   # 队列管理
│   │   ├── youtube_client.py  # YouTube 客户端
│   │   ├── catbox_client.py   # Catbox 客户端
│   │   ├── voice_manager.py   # 语音连接管理
│   │   ├── seek_manager.py    # 时间定位管理
│   │   └── lyrics_client.py   # 歌词客户端
│   ├── progress/
│   │   └── music_progress.py  # 播放进度显示
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

## 许可证

本项目采用 MIT 许可证 - 详情请参阅 LICENSE 文件。

## 致谢

- [discord.py](https://github.com/Rapptz/discord.py) - Python Discord API 封装库
- [pytubefix](https://github.com/JuanBindez/pytubefix) - YouTube 视频下载库
- [FFmpeg](https://ffmpeg.org/) - 音频/视频处理工具

## 支持

如果在使用过程中遇到问题，请在 GitHub 上提交 Issue 或联系开发者。

---

**为类脑/Odysseia Discord 社区专门定制** 🎵
