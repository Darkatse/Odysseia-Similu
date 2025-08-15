"""
App Commands日志配置

提供统一的日志配置和管理：
- 结构化日志记录
- 性能监控
- 错误追踪
- 调试信息收集
"""

import logging
import time
import functools
from typing import Any, Callable, Optional, Dict
import discord
from discord.ext import commands


class AppCommandsLogger:
    """
    App Commands专用日志记录器

    提供结构化的日志记录和性能监控功能
    """

    def __init__(self, name: str):
        """
        初始化日志记录器

        Args:
            name: 日志记录器名称
        """
        self.logger = logging.getLogger(f"similubot.app_commands.{name}")
        self._setup_logger()

    def _setup_logger(self) -> None:
        """设置日志记录器"""
        # 确保日志级别至少为DEBUG
        if self.logger.level > logging.DEBUG:
            self.logger.setLevel(logging.DEBUG)

    def log_command_start(
        self,
        interaction: discord.Interaction,
        command_name: str,
        **kwargs
    ) -> None:
        """
        记录命令开始执行

        Args:
            interaction: Discord交互对象
            command_name: 命令名称
            **kwargs: 额外的上下文信息
        """
        context = {
            'user_id': interaction.user.id,
            'user_name': interaction.user.display_name,
            'guild_id': interaction.guild.id if interaction.guild else None,
            'guild_name': interaction.guild.name if interaction.guild else None,
            'channel_id': interaction.channel.id if interaction.channel else None,
            'command': command_name,
            'timestamp': time.time(),
            **kwargs
        }

        self.logger.info(
            f"命令开始 - {command_name} | "
            f"用户: {interaction.user.display_name} | "
            f"服务器: {interaction.guild.name if interaction.guild else 'DM'}",
            extra={'context': context}
        )

    def log_command_success(
        self,
        interaction: discord.Interaction,
        command_name: str,
        execution_time: float = None,
        **kwargs
    ) -> None:
        """
        记录命令成功执行

        Args:
            interaction: Discord交互对象
            command_name: 命令名称
            execution_time: 执行时间（秒）
            **kwargs: 额外的上下文信息
        """
        context = {
            'user_id': interaction.user.id,
            'user_name': interaction.user.display_name,
            'guild_id': interaction.guild.id if interaction.guild else None,
            'command': command_name,
            'execution_time': execution_time,
            'status': 'success',
            **kwargs
        }

        time_info = f" | 耗时: {execution_time:.2f}s" if execution_time else ""

        self.logger.info(
            f"命令成功 - {command_name} | "
            f"用户: {interaction.user.display_name}{time_info}",
            extra={'context': context}
        )

    def log_command_error(
        self,
        interaction: discord.Interaction,
        command_name: str,
        error: Exception,
        execution_time: float = None,
        **kwargs
    ) -> None:
        """
        记录命令执行错误

        Args:
            interaction: Discord交互对象
            command_name: 命令名称
            error: 异常对象
            execution_time: 执行时间（秒）
            **kwargs: 额外的上下文信息
        """
        context = {
            'user_id': interaction.user.id,
            'user_name': interaction.user.display_name,
            'guild_id': interaction.guild.id if interaction.guild else None,
            'command': command_name,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'execution_time': execution_time,
            'status': 'error',
            **kwargs
        }

        time_info = f" | 耗时: {execution_time:.2f}s" if execution_time else ""

        self.logger.error(
            f"命令错误 - {command_name} | "
            f"用户: {interaction.user.display_name} | "
            f"错误: {type(error).__name__}: {error}{time_info}",
            extra={'context': context},
            exc_info=True
        )

    def log_performance_warning(
        self,
        operation: str,
        execution_time: float,
        threshold: float = 5.0,
        **kwargs
    ) -> None:
        """
        记录性能警告

        Args:
            operation: 操作名称
            execution_time: 执行时间（秒）
            threshold: 警告阈值（秒）
            **kwargs: 额外的上下文信息
        """
        if execution_time > threshold:
            context = {
                'operation': operation,
                'execution_time': execution_time,
                'threshold': threshold,
                'performance_issue': True,
                **kwargs
            }

            self.logger.warning(
                f"性能警告 - {operation} | "
                f"耗时: {execution_time:.2f}s (阈值: {threshold}s)",
                extra={'context': context}
            )

    def debug(self, message: str, **kwargs) -> None:
        """记录调试信息"""
        self.logger.debug(message, extra={'context': kwargs})

    def info(self, message: str, **kwargs) -> None:
        """记录信息"""
        self.logger.info(message, extra={'context': kwargs})

    def warning(self, message: str, **kwargs) -> None:
        """记录警告"""
        self.logger.warning(message, extra={'context': kwargs})

    def error(self, message: str, error: Exception = None, **kwargs) -> None:
        """记录错误"""
        self.logger.error(message, extra={'context': kwargs}, exc_info=error)


def log_command_execution(logger: AppCommandsLogger):
    """
    命令执行日志装饰器

    Args:
        logger: 日志记录器实例

    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # 提取interaction和命令名称
            interaction = None
            command_name = func.__name__

            # 查找interaction参数
            for arg in args:
                if isinstance(arg, discord.Interaction):
                    interaction = arg
                    break

            if not interaction:
                # 如果没有找到interaction，直接执行函数
                return await func(*args, **kwargs)

            start_time = time.time()

            try:
                # 记录命令开始
                logger.log_command_start(interaction, command_name)

                # 执行命令
                result = await func(*args, **kwargs)

                # 计算执行时间
                execution_time = time.time() - start_time

                # 记录成功
                logger.log_command_success(interaction, command_name, execution_time)

                # 检查性能
                logger.log_performance_warning(command_name, execution_time)

                return result

            except Exception as e:
                # 计算执行时间
                execution_time = time.time() - start_time

                # 记录错误
                logger.log_command_error(interaction, command_name, e, execution_time)

                # 重新抛出异常
                raise

        return wrapper
    return decorator


def setup_app_commands_logging() -> None:
    """设置App Commands日志配置"""
    # 获取根日志记录器
    root_logger = logging.getLogger("similubot.app_commands")

    # 设置日志级别
    root_logger.setLevel(logging.DEBUG)

    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 如果没有处理器，添加控制台处理器
    if not root_logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    logging.getLogger("similubot.app_commands").info("App Commands日志系统已初始化")