"""
Odysseia-Similu Slash Commands Module

基于领域驱动设计的Discord Slash Commands实现
支持音乐播放、队列管理和播放控制的完整功能

架构特点：
- 领域驱动设计：按业务领域组织代码
- 依赖注入：松耦合的模块设计
- 单一职责：每个模块只负责一个明确的功能
- 可测试性：易于单元测试和集成测试
"""

from .core import (
    BaseSlashCommand,
    SlashCommandGroup,
    CommandRegistry,
    DependencyContainer
)

from .music import (
    MusicSearchCommands,
    QueueManagementCommands,
    PlaybackControlCommands
)

from .general import (
    PingCommand,
    HelpCommand
)

from .ui import (
    EmbedBuilder,
    InteractionHandler,
    MessageVisibility
)

__all__ = [
    # Core infrastructure
    'BaseSlashCommand',
    'SlashCommandGroup',
    'CommandRegistry',
    'DependencyContainer',

    # Music domain commands
    'MusicSearchCommands',
    'QueueManagementCommands',
    'PlaybackControlCommands',

    # General commands
    'PingCommand',
    'HelpCommand',

    # UI components
    'EmbedBuilder',
    'InteractionHandler',
    'MessageVisibility'
]

__version__ = "1.0.0"