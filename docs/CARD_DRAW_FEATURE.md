# 随机抽卡功能文档

## 概述

随机抽卡功能允许用户从歌曲历史记录中随机选择歌曲并添加到播放队列。该功能基于现有的app_commands架构实现，遵循领域驱动设计原则。

## 功能特性

### 核心功能
- **随机歌曲选择**: 从歌曲历史数据库中使用加权算法随机选择歌曲
- **多种来源池**: 支持全局池、个人池、指定用户池三种抽卡来源
- **用户交互**: 提供满意/重新抽取按钮，支持多次重抽
- **队列集成**: 选中的歌曲可直接添加到音乐播放队列

### 高级特性
- **权重算法**: 使用用户多样性加成，避免单一用户歌曲被过度选择
- **自动记录**: 所有添加到队列的歌曲自动记录到历史数据库
- **配置管理**: 支持超时时间、最大重抽次数等配置选项
- **数据持久化**: 使用SQLite数据库存储歌曲历史记录

## 命令使用

### `/随机抽卡`
从配置的歌曲来源中随机抽取一首歌曲。

**使用方法:**
```
/随机抽卡
```

**交互流程:**
1. 系统随机选择一首歌曲并显示详细信息
2. 用户可以选择"满意"将歌曲添加到队列
3. 或选择"重新抽取"获得新的歌曲（有次数限制）
4. 超时后自动取消操作

### `/设置抽卡来源`
设置随机抽卡的歌曲来源池。

**参数:**
- `来源`: 抽卡来源类型
  - `全局池（所有用户）`: 从服务器内所有用户的歌曲历史中抽取
  - `个人池（仅自己）`: 只从自己的歌曲历史中抽取
  - `指定用户池`: 从指定用户的歌曲历史中抽取
- `目标用户`: 当选择指定用户池时需要指定的目标用户

**使用示例:**
```
/设置抽卡来源 来源:全局池（所有用户）
/设置抽卡来源 来源:个人池（仅自己）
/设置抽卡来源 来源:指定用户池 目标用户:@某用户
```

## 配置选项

在 `config.yaml` 中的 `card_draw` 部分可以配置以下选项：

```yaml
card_draw:
  enabled: true  # 是否启用随机抽卡功能
  
  # 抽卡行为配置
  max_redraws: 3  # 每次抽卡的最大重抽次数
  timeout_seconds: 60  # 用户交互超时时间（秒）
  
  # 默认抽卡来源设置
  default_source: "global"  # 默认抽卡来源
  
  # 权重算法配置
  weight_algorithm:
    recent_bonus: 1.2  # 最近歌曲的权重加成倍数
    frequency_penalty: 0.8  # 高频歌曲的权重惩罚倍数
    user_diversity_bonus: 1.1  # 用户多样性加成倍数
  
  # 数据库配置
  database:
    auto_record: true  # 是否自动记录队列歌曲到历史数据库
    cleanup_days: 365  # 历史记录保留天数（0表示永久保留）
    max_records_per_user: 1000  # 每个用户最大历史记录数（0表示无限制）
```

## 技术架构

### 模块结构
```
similubot/app_commands/card_draw/
├── __init__.py                    # 模块初始化
├── database.py                    # 歌曲历史数据库管理
├── random_selector.py             # 随机选择算法
├── card_draw_commands.py          # 抽卡命令处理
└── source_settings_commands.py   # 来源设置命令处理
```

### 核心组件

#### SongHistoryDatabase
- 负责歌曲历史记录的存储和查询
- 使用SQLite数据库，支持异步操作
- 提供随机查询、统计等功能

#### RandomSongSelector
- 实现加权随机选择算法
- 支持多种来源池配置
- 提供权重计算和统计功能

#### CardDrawCommands
- 处理 `/随机抽卡` 命令
- 管理用户交互界面
- 集成音乐队列系统

#### SourceSettingsCommands
- 处理 `/设置抽卡来源` 命令
- 管理用户设置持久化
- 提供设置验证功能

### 数据库设计

#### song_history 表
```sql
CREATE TABLE song_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    artist TEXT NOT NULL,
    url TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    user_name TEXT NOT NULL,
    guild_id INTEGER NOT NULL,
    timestamp DATETIME NOT NULL,
    source_platform TEXT NOT NULL,
    duration INTEGER NOT NULL,
    thumbnail_url TEXT,
    file_format TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### 索引
- `idx_song_history_user_id`: 用户ID索引
- `idx_song_history_guild_id`: 服务器ID索引
- `idx_song_history_timestamp`: 时间戳索引
- `idx_song_history_source_platform`: 来源平台索引

## 集成说明

### 与现有系统的集成

1. **队列系统集成**: 在 `QueueManager.add_song()` 方法中自动记录歌曲到历史数据库
2. **命令注册**: 在 `CommandRegistry` 中注册新的抽卡命令
3. **依赖注入**: 使用现有的 `DependencyContainer` 管理组件生命周期
4. **配置管理**: 集成到现有的 `ConfigManager` 系统

### 启动初始化

在机器人启动时，会自动：
1. 检查抽卡功能是否启用
2. 初始化歌曲历史数据库
3. 创建必要的表结构和索引
4. 注册抽卡相关命令

## 测试

### 单元测试
- `test_card_draw_database.py`: 数据库操作测试
- `test_card_draw_selector.py`: 随机选择算法测试
- `test_card_draw_commands.py`: 命令处理测试

### 集成测试
- `test_card_draw_integration.py`: 端到端功能测试

### 运行测试
```bash
# 运行所有抽卡相关测试
python -m pytest tests/test_card_draw_*.py -v

# 运行特定测试文件
python -m unittest tests.test_card_draw_database
```

## 故障排除

### 常见问题

1. **抽卡失败，提示没有歌曲**
   - 确认服务器内有歌曲历史记录
   - 检查抽卡来源设置是否正确
   - 验证数据库是否正常初始化

2. **数据库初始化失败**
   - 检查数据目录权限
   - 确认SQLite可用
   - 查看日志中的详细错误信息

3. **命令不可用**
   - 确认 `card_draw.enabled` 配置为 `true`
   - 检查命令是否正确注册
   - 验证Discord权限设置

### 日志调试

启用调试日志以获取详细信息：
```yaml
logging:
  level: "DEBUG"
```

相关日志标签：
- `similubot.card_draw.database`: 数据库操作
- `similubot.card_draw.selector`: 随机选择
- `similubot.card_draw.commands`: 命令处理

## 未来扩展

### 计划功能
- 歌曲收藏系统
- 抽卡历史记录
- 更多权重算法选项
- 批量抽卡功能
- 抽卡统计分析

### 性能优化
- 数据库查询优化
- 缓存机制
- 异步处理改进
- 内存使用优化
