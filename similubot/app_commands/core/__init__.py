"""
App Commands Core Infrastructure

提供Slash Commands的核心基础设施，包括：
- 基础命令类
- 依赖注入容器
- 命令注册系统
- 命令组管理
"""

from .base_command import BaseSlashCommand
from .command_group import SlashCommandGroup
from .registry import CommandRegistry
from .dependency_container import DependencyContainer, ServiceProvider
from .logging_config import AppCommandsLogger, log_command_execution, setup_app_commands_logging
from .error_handler import (
    AppCommandsErrorHandler,
    AppCommandError,
    MusicCommandError,
    QueueFairnessError,
    NetworkTimeoutError,
    ErrorCategory
)

__all__ = [
    'BaseSlashCommand',
    'SlashCommandGroup',
    'CommandRegistry',
    'DependencyContainer',
    'ServiceProvider',
    'AppCommandsLogger',
    'log_command_execution',
    'setup_app_commands_logging',
    'AppCommandsErrorHandler',
    'AppCommandError',
    'MusicCommandError',
    'QueueFairnessError',
    'NetworkTimeoutError',
    'ErrorCategory'
]