"""
通用命令模块

提供机器人的基础功能命令：
- 延迟检测
- 帮助信息
- 机器人状态
"""

from .ping_command import PingCommand
from .help_command import HelpCommand

__all__ = [
    'PingCommand',
    'HelpCommand'
]