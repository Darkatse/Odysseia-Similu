# Odysseia-Similu App Commands 架构设计

## 概述

本文档描述了Odysseia-Similu音乐机器人从前缀命令(!music)迁移到Discord原生Slash Commands(/commands)的新架构设计。

## 设计原则

### 1. 领域驱动设计 (Domain-Driven Design)
- **音乐搜索领域**: 处理NetEase搜索、URL检测、交互式选择
- **队列管理领域**: 处理队列显示、用户状态、公平性控制
- **播放控制领域**: 处理跳过、进度显示、停止播放

### 2. 依赖注入 (Dependency Injection)
- 松耦合的模块设计
- 易于测试和模拟
- 配置驱动的组件初始化

### 3. 单一职责原则 (Single Responsibility Principle)
- 每个命令类只负责一个特定功能
- UI组件与业务逻辑分离
- 清晰的接口定义

## 模块结构

```
similubot/app_commands/
├── __init__.py                 # 模块入口和公共接口
├── core/                       # 核心基础设施
│   ├── __init__.py
│   ├── base_command.py         # 基础命令类
│   ├── command_group.py        # 命令组管理
│   ├── registry.py             # 命令注册系统
│   └── dependency_container.py # 依赖注入容器
├── music/                      # 音乐领域命令
│   ├── __init__.py
│   ├── search_commands.py      # 音乐搜索命令
│   ├── queue_commands.py       # 队列管理命令
│   └── playback_commands.py    # 播放控制命令
└── ui/                         # UI组件库
    ├── __init__.py
    ├── embed_builder.py        # 嵌入消息构建器
    ├── interaction_handler.py  # 交互处理器
    └── message_visibility.py   # 消息可见性控制
```

## 命令映射

### 前缀命令 → Slash命令映射

| 旧命令 | 新命令 | 功能描述 |
|--------|--------|----------|
| `!music [query/url]` | `/点歌 [链接/名字]` | 歌曲请求 |
| `!music skip` | `/歌曲跳过` | 跳过歌曲 |
| `!music now` | `/歌曲进度` | 显示进度 |
| `!music queue` | `/歌曲队列` | 显示队列 |
| `!music my` | `/我的队列` | 用户队列状态 |

### 移除的命令
- `!music seek` - 不再需要
- `!music jump` - 不再需要

## 消息可见性策略

### Ephemeral消息 (仅用户可见)
- 错误提示
- 个人队列状态查询
- 帮助信息

### Public消息 (所有用户可见)
- 成功添加歌曲通知
- 歌词显示
- 跳过投票通知
- 队列状态显示

## 核心组件设计

### BaseSlashCommand
所有slash命令的基础类，提供：
- 统一的错误处理机制
- 日志记录功能
- 权限检查
- 消息可见性控制

### DependencyContainer
依赖注入容器，管理：
- 音乐播放器实例
- 配置管理器
- UI组件工厂
- 服务实例生命周期

### SlashCommandGroup
命令组管理器，负责：
- 命令注册和组织
- 权限验证
- 命令路由

## 业务领域设计

### 音乐搜索领域 (MusicSearchCommands)
**职责**: 处理音乐搜索和添加请求
**命令**: `/点歌`
**功能**:
- NetEase音乐搜索
- URL检测和处理
- 交互式歌曲选择
- 队列公平性检查

### 队列管理领域 (QueueManagementCommands)
**职责**: 处理队列查看和用户状态
**命令**: `/歌曲队列`, `/我的队列`
**功能**:
- 队列状态显示
- 用户个人队列查询
- 队列统计信息

### 播放控制领域 (PlaybackControlCommands)
**职责**: 处理播放控制操作
**命令**: `/歌曲跳过`, `/歌曲进度`
**功能**:
- 民主投票跳过
- 实时进度显示
- 播放状态控制

## UI组件库设计

### EmbedBuilder
统一的嵌入消息构建器：
- 标准化的消息格式
- 主题色彩管理
- 多语言支持

### InteractionHandler
交互处理器：
- 按钮交互管理
- 选择菜单处理
- 超时处理

### MessageVisibility
消息可见性控制：
- Ephemeral/Public消息策略
- 用户权限检查
- 上下文感知的可见性决策