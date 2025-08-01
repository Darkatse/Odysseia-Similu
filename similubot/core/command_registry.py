"""Odysseia-Similu 音乐机器人命令注册系统。"""
import inspect
import logging
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass
import discord
from discord.ext import commands


@dataclass
class CommandInfo:
    """Information about a registered command."""
    name: str
    callback: Callable
    description: str
    required_permission: Optional[str] = None
    admin_only: bool = False
    usage_examples: Optional[List[str]] = None
    help_text: Optional[str] = None


class CommandRegistry:
    """
    音乐机器人命令注册器。

    提供集中化的命令注册方式，简化版本，不包含授权系统。
    """

    def __init__(self, bot: commands.Bot, auth_manager: Optional = None,
                 unauthorized_handler: Optional = None):
        """
        初始化命令注册器。

        Args:
            bot: Discord 机器人实例
            auth_manager: 已弃用，保持兼容性
            unauthorized_handler: 已弃用，保持兼容性
        """
        self.logger = logging.getLogger("similubot.command_registry")
        self.bot = bot
        self._commands: Dict[str, CommandInfo] = {}
        self._command_groups: Dict[str, List[CommandInfo]] = {}

    def register_command(
        self,
        name: str,
        callback: Callable,
        description: str,
        required_permission: Optional[str] = None,
        admin_only: bool = False,
        usage_examples: Optional[List[str]] = None,
        help_text: Optional[str] = None
    ) -> None:
        """
        Register a command with the bot.

        Args:
            name: Command name
            callback: Command callback function
            description: Command description
            required_permission: Required permission (command name or feature name)
            admin_only: Whether command requires admin privileges
            usage_examples: List of usage examples for help display
            help_text: Additional help text for the command
        """
        command_info = CommandInfo(
            name=name,
            callback=callback,
            description=description,
            required_permission=required_permission,
            admin_only=admin_only,
            usage_examples=usage_examples,
            help_text=help_text
        )

        self._commands[name] = command_info

        # Create wrapped command (simplified, no authorization)
        wrapped_callback = self._wrap_command_simple(command_info)

        # Register with Discord.py
        command = commands.Command(wrapped_callback, name=name, help=description)
        self.bot.add_command(command)

        self.logger.debug(f"注册命令: {name}")

    def register_command_group(
        self,
        name: str,
        description: str,
        admin_only: bool = True,
        usage_examples: Optional[List[str]] = None,
        help_text: Optional[str] = None
    ) -> commands.Group:
        """
        Register a command group with the bot.

        Args:
            name: Group name
            description: Group description
            admin_only: Whether group requires admin privileges
            usage_examples: List of usage examples for help display
            help_text: Additional help text for the command group

        Returns:
            Discord command group
        """
        async def group_callback(ctx):
            """Default group callback with custom help display."""
            if admin_only and not self.auth_manager.is_admin(ctx.author.id):
                await ctx.reply("❌ You don't have permission to use these commands.")
                return

            # Create command info for help display
            command_info = CommandInfo(
                name=name,
                callback=group_callback,
                description=description,
                admin_only=admin_only,
                usage_examples=usage_examples,
                help_text=help_text
            )

            # Show custom help using our help system
            await self._send_command_help(command_info, ctx)

        # Create wrapped group callback with authorization
        if admin_only:
            wrapped_callback = self._wrap_admin_command(group_callback)
        else:
            wrapped_callback = group_callback

        group = commands.Group(wrapped_callback, name=name, help=description, invoke_without_command=True)
        self.bot.add_command(group)

        self._command_groups[name] = []
        self.logger.debug(f"Registered command group: {name}")

        return group

    def register_group_command(
        self,
        group: commands.Group,
        name: str,
        callback: Callable,
        description: str,
        admin_only: bool = True
    ) -> None:
        """
        Register a command within a group.

        Args:
            group: Parent command group
            name: Command name
            callback: Command callback function
            description: Command description
            admin_only: Whether command requires admin privileges
        """
        command_info = CommandInfo(
            name=f"{group.name}.{name}",
            callback=callback,
            description=description,
            admin_only=admin_only
        )

        # Create wrapped command with authorization
        if admin_only:
            wrapped_callback = self._wrap_admin_command(callback)
        else:
            wrapped_callback = callback

        # Register with group
        command = commands.Command(wrapped_callback, name=name, help=description)
        group.add_command(command)

        # Track in registry
        if group.name in self._command_groups:
            self._command_groups[group.name].append(command_info)

        self.logger.debug(f"Registered group command: {group.name}.{name}")

    def _wrap_command_simple(self, command_info: CommandInfo) -> Callable:
        """
        简单包装命令回调函数。

        Args:
            command_info: 命令信息

        Returns:
            包装后的回调函数
        """
        async def wrapped_callback(ctx, *args, **kwargs):
            try:
                # 验证参数
                if not await self._validate_command_arguments(command_info, ctx, *args, **kwargs):
                    return

                # 执行原始命令
                await self._call_command_callback(command_info.callback, ctx, *args, **kwargs)

            except TypeError as e:
                # 优雅处理缺少参数错误
                if "missing" in str(e) and "required positional argument" in str(e):
                    await self._send_command_help(command_info, ctx)
                else:
                    self.logger.error(f"命令 {command_info.name} 类型错误: {e}", exc_info=True)
                    await ctx.reply(f"❌ 参数无效。使用 `!help {command_info.name}` 获取使用信息。")
            except Exception as e:
                self.logger.error(f"执行命令 {command_info.name} 时出错: {e}", exc_info=True)
                await ctx.reply(f"❌ 执行命令时发生错误: {str(e)}")

        # 保留函数元数据
        wrapped_callback.__name__ = command_info.callback.__name__
        wrapped_callback.__doc__ = command_info.callback.__doc__

        return wrapped_callback

    async def _call_command_callback(self, callback: Callable, ctx, *args, **kwargs):
        """
        Call a command callback, handling both instance methods and regular functions.

        This method properly handles the argument passing for commands that expect
        variable-length text input (like NovelAI commands with *, args: str).

        Args:
            callback: The command callback function
            ctx: Discord command context
            *args: Positional arguments from Discord.py
            **kwargs: Keyword arguments from Discord.py
        """
        # Get the function signature
        sig = inspect.signature(callback)
        params = list(sig.parameters.values())

        self.logger.debug(f"Calling command callback: {callback.__name__}")
        self.logger.debug(f"Parameters: {[p.name for p in params]}")
        self.logger.debug(f"Args count: {len(args)}")

        # Check if this is a method (has 'self' parameter)
        if params and params[0].name == 'self':
            # This is an instance method, skip 'self' parameter
            params = params[1:]

        # Check for keyword-only arguments (*, args: str pattern)
        has_var_keyword_only = any(
            p.kind == inspect.Parameter.VAR_KEYWORD or
            (p.kind == inspect.Parameter.KEYWORD_ONLY and p.name in ['args', 'arg'])
            for p in params
        )

        # Check for the specific pattern: ctx, *, args: str
        if (len(params) >= 2 and
            params[0].name == 'ctx' and
            len(params) == 2 and
            params[1].kind == inspect.Parameter.KEYWORD_ONLY and
            params[1].name == 'args'):

            # This is the NovelAI command pattern: (ctx, *, args: str)
            # Join all arguments into a single string
            args_str = ' '.join(str(arg) for arg in args) if args else ''
            self.logger.debug(f"Using keyword-only args pattern: '{args_str}'")
            await callback(ctx, args=args_str)

        elif has_var_keyword_only:
            # Handle other keyword-only patterns
            await callback(ctx, **kwargs)

        else:
            # Regular function call
            await callback(ctx, *args, **kwargs)

    async def _validate_command_arguments(self, command_info: CommandInfo, ctx, *args, **kwargs) -> bool:
        """
        Validate command arguments and show help if needed.

        Args:
            command_info: Command information
            ctx: Discord command context
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            True if arguments are valid, False if help was shown
        """
        # Get the function signature
        sig = inspect.signature(command_info.callback)
        params = list(sig.parameters.values())

        # Skip 'self' parameter if this is an instance method
        if params and params[0].name == 'self':
            params = params[1:]

        # Skip 'ctx' parameter
        if params and params[0].name == 'ctx':
            params = params[1:]

        # Check for specific command patterns that need special handling

        # NovelAI pattern: (*, args: str) - requires at least some text
        if (len(params) == 1 and
            params[0].kind == inspect.Parameter.KEYWORD_ONLY and
            params[0].name == 'args'):

            # For NovelAI commands, check if args is empty
            if not args or (len(args) == 1 and not args[0].strip()):
                await self._send_command_help(command_info, ctx)
                return False
            return True

        # MEGA pattern: (url: str, bitrate: Optional[int] = None)
        if (command_info.name == "mega" and
            len(params) >= 1 and
            params[0].name == 'url'):

            # Check if URL is missing
            if not args:
                await self._send_command_help(command_info, ctx)
                return False
            return True

        # Auth group commands - handled by Discord.py group system
        if command_info.name.startswith("auth."):
            return True

        # For other commands, check required parameters
        required_params = [p for p in params if p.default == inspect.Parameter.empty]

        if len(args) < len(required_params):
            await self._send_command_help(command_info, ctx)
            return False

        return True

    async def _send_command_help(self, command_info: CommandInfo, ctx) -> None:
        """
        Send helpful usage information for a command.

        Args:
            command_info: Command information
            ctx: Discord command context
        """
        embed = discord.Embed(
            title=f"📖 Help: {ctx.bot.command_prefix}{command_info.name}",
            description=command_info.description,
            color=0x3498db
        )

        # Add usage examples based on command type
        if command_info.name == "mega":
            embed.add_field(
                name="📝 Usage",
                value=f"`{ctx.bot.command_prefix}mega <MEGA_URL> [bitrate]`",
                inline=False
            )

            examples = [
                f"`{ctx.bot.command_prefix}mega https://mega.nz/file/example`",
                f"`{ctx.bot.command_prefix}mega https://mega.nz/file/example 192`",
                f"`{ctx.bot.command_prefix}mega https://mega.nz/file/example 320`"
            ]

            embed.add_field(
                name="💡 Examples",
                value="\n".join(examples),
                inline=False
            )

            embed.add_field(
                name="ℹ️ Parameters",
                value="• `MEGA_URL` - A valid MEGA download link\n• `bitrate` - Audio quality in kbps (optional, default: 128)",
                inline=False
            )

        elif command_info.name == "nai":
            embed.add_field(
                name="📝 Usage",
                value=f"`{ctx.bot.command_prefix}nai <prompt> [options]`",
                inline=False
            )

            examples = [
                f"`{ctx.bot.command_prefix}nai beautiful landscape, mountains, sunset`",
                f"`{ctx.bot.command_prefix}nai anime girl with blue hair discord`",
                f"`{ctx.bot.command_prefix}nai fantasy scene size:landscape`",
                f"`{ctx.bot.command_prefix}nai group scene char1:[elf warrior] char2:[mage]`"
            ]

            embed.add_field(
                name="💡 Examples",
                value="\n".join(examples),
                inline=False
            )

            embed.add_field(
                name="ℹ️ Options",
                value="• `discord/catbox` - Upload service\n• `size:portrait/landscape/square` - Image dimensions\n• `char1:[desc] char2:[desc]` - Multi-character generation",
                inline=False
            )

        elif command_info.name == "auth":
            embed.add_field(
                name="📝 Available Subcommands",
                value=f"`{ctx.bot.command_prefix}auth status` - Show system status\n"
                      f"`{ctx.bot.command_prefix}auth user <user_id>` - Show user permissions\n"
                      f"`{ctx.bot.command_prefix}auth add <user_id> <level> [modules...]` - Add user\n"
                      f"`{ctx.bot.command_prefix}auth remove <user_id>` - Remove user",
                inline=False
            )

            embed.add_field(
                name="ℹ️ Permission Levels",
                value="• `admin` - Full admin access\n• `full` - Access to all modules\n• `module` - Access to specific modules\n• `none` - No access",
                inline=False
            )

            embed.add_field(
                name="🔧 Available Modules",
                value="• `mega_download` - MEGA link processing\n• `novelai` - AI image generation\n• `general` - General bot commands",
                inline=False
            )

            embed.add_field(
                name="🔒 Admin Requirements",
                value="All authorization commands require administrator privileges. "
                      "Only users listed in the `admin_ids` configuration can use these commands.",
                inline=False
            )

        # Add custom help text if provided
        if command_info.help_text:
            embed.add_field(
                name="📋 Additional Information",
                value=command_info.help_text,
                inline=False
            )

        # Add custom usage examples if provided
        if command_info.usage_examples:
            embed.add_field(
                name="📚 More Examples",
                value="\n".join(command_info.usage_examples),
                inline=False
            )

        embed.set_footer(text="💡 Tip: Use the exact syntax shown in examples for best results")
        embed.timestamp = discord.utils.utcnow()

        await ctx.reply(embed=embed)

    def _wrap_admin_command(self, callback: Callable) -> Callable:
        """
        Wrap a command callback with admin authorization checking.

        Args:
            callback: Original callback function

        Returns:
            Wrapped callback function
        """
        async def wrapped_callback(ctx, *args, **kwargs):
            try:
                # Check admin privileges
                if not self.auth_manager.is_admin(ctx.author.id):
                    await ctx.reply("❌ You don't have permission to use this command.")
                    return

                # Execute the original command
                # Handle both instance methods and regular functions
                await self._call_command_callback(callback, ctx, *args, **kwargs)

            except TypeError as e:
                # Handle missing argument errors gracefully for admin commands too
                if "missing" in str(e) and "required positional argument" in str(e):
                    # Create a temporary command info for help display
                    temp_command_info = CommandInfo(
                        name="auth",
                        callback=callback,
                        description="Authorization management commands (admin only)"
                    )
                    await self._send_command_help(temp_command_info, ctx)
                else:
                    self.logger.error(f"TypeError in admin command: {e}", exc_info=True)
                    await ctx.reply(f"❌ Invalid arguments provided. Use `!help auth` for usage information.")
            except Exception as e:
                self.logger.error(f"Error in admin command: {e}", exc_info=True)
                await ctx.reply(f"❌ An error occurred while executing the command: {str(e)}")

        # Preserve function metadata
        wrapped_callback.__name__ = callback.__name__
        wrapped_callback.__doc__ = callback.__doc__

        return wrapped_callback

    def get_registered_commands(self) -> Dict[str, CommandInfo]:
        """
        Get all registered commands.

        Returns:
            Dictionary of command name to CommandInfo
        """
        return self._commands.copy()

    def get_command_groups(self) -> Dict[str, List[CommandInfo]]:
        """
        Get all registered command groups.

        Returns:
            Dictionary of group name to list of CommandInfo
        """
        return self._command_groups.copy()

    def is_command_registered(self, name: str) -> bool:
        """
        Check if a command is registered.

        Args:
            name: Command name

        Returns:
            True if command is registered, False otherwise
        """
        return name in self._commands
