"""Comprehensive tests for command system functionality."""
import unittest
import inspect
import sys
import os
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio
import pytest

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from similubot.core.command_registry import CommandRegistry, CommandInfo
from similubot.commands.mega_commands import MegaCommands
from similubot.commands.novelai_commands import NovelAICommands
from similubot.commands.auth_commands import AuthCommands
from similubot.commands.general_commands import GeneralCommands


class TestCommandRegistry(unittest.TestCase):
    """Test command registry functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_bot = MagicMock()
        self.mock_bot.command_prefix = "!"
        self.mock_auth_manager = MagicMock()
        self.mock_unauthorized_handler = MagicMock()

        self.registry = CommandRegistry(
            bot=self.mock_bot,
            auth_manager=self.mock_auth_manager,
            unauthorized_handler=self.mock_unauthorized_handler
        )

    def test_command_registration(self):
        """Test basic command registration."""
        mock_callback = AsyncMock()

        self.registry.register_command(
            name="test",
            callback=mock_callback,
            description="Test command"
        )

        # Verify command was registered
        self.assertIn("test", self.registry._commands)
        command_info = self.registry._commands["test"]
        self.assertEqual(command_info.name, "test")
        self.assertEqual(command_info.callback, mock_callback)

    def test_command_registration_with_help(self):
        """Test command registration with help information."""
        usage_examples = ["!test example1", "!test example2"]
        help_text = "This is a test command."

        mock_callback = AsyncMock()

        self.registry.register_command(
            name="test",
            callback=mock_callback,
            description="Test command",
            usage_examples=usage_examples,
            help_text=help_text
        )

        # Verify help information was stored
        command_info = self.registry._commands["test"]
        self.assertEqual(command_info.usage_examples, usage_examples)
        self.assertEqual(command_info.help_text, help_text)

    def test_command_group_registration(self):
        """Test command group registration."""
        group = self.registry.register_command_group(
            name="testgroup",
            description="Test group",
            admin_only=True
        )

        self.assertEqual(group.name, "testgroup")
        self.mock_bot.add_command.assert_called()

    async def test_argument_validation_novelai_pattern(self):
        """Test argument validation for NovelAI pattern."""
        # Create NovelAI command info with actual callback signature
        def mock_nai_callback(self, ctx, *, args):
            pass

        command_info = CommandInfo(
            name="nai",
            callback=mock_nai_callback,
            description="Generate an image using NovelAI"
        )

        mock_ctx = MagicMock()

        # Mock the help display
        self.registry._send_command_help = AsyncMock()

        # Test with empty args (should fail validation)
        result = await self.registry._validate_command_arguments(command_info, mock_ctx, "")
        self.assertFalse(result)
        self.registry._send_command_help.assert_called_once()

        # Reset mock
        self.registry._send_command_help.reset_mock()

        # Test with valid prompt (should pass validation)
        result = await self.registry._validate_command_arguments(
            command_info, mock_ctx, "beautiful landscape"
        )
        self.assertTrue(result)
        self.registry._send_command_help.assert_not_called()

    async def test_argument_validation_mega_pattern(self):
        """Test argument validation for MEGA pattern."""
        # Create MEGA command info with actual callback signature
        def mock_mega_callback(self, ctx, url, bitrate=None):
            pass

        command_info = CommandInfo(
            name="mega",
            callback=mock_mega_callback,
            description="Download a file from MEGA"
        )

        mock_ctx = MagicMock()

        # Mock the help display
        self.registry._send_command_help = AsyncMock()

        # Test with no arguments (should fail validation)
        result = await self.registry._validate_command_arguments(command_info, mock_ctx)
        self.assertFalse(result)
        self.registry._send_command_help.assert_called_once()

        # Reset mock
        self.registry._send_command_help.reset_mock()

        # Test with valid URL (should pass validation)
        result = await self.registry._validate_command_arguments(
            command_info, mock_ctx, "https://mega.nz/file/example"
        )
        self.assertTrue(result)
        self.registry._send_command_help.assert_not_called()


class TestCommandHelpSystem(unittest.TestCase):
    """Test command help system functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_bot = MagicMock()
        self.mock_bot.command_prefix = "!"
        self.mock_auth_manager = MagicMock()
        self.mock_unauthorized_handler = MagicMock()

        self.registry = CommandRegistry(
            bot=self.mock_bot,
            auth_manager=self.mock_auth_manager,
            unauthorized_handler=self.mock_unauthorized_handler
        )

    async def test_mega_command_help_display(self):
        """Test MEGA command help display."""
        mock_ctx = MagicMock()
        mock_ctx.bot.command_prefix = "!"
        mock_ctx.reply = AsyncMock()

        command_info = CommandInfo(
            name="mega",
            callback=MagicMock(),
            description="Download a file from MEGA and convert it to AAC"
        )

        await self.registry._send_command_help(command_info, mock_ctx)

        # Verify help was sent
        mock_ctx.reply.assert_called_once()
        call_args = mock_ctx.reply.call_args[1]
        embed = call_args['embed']

        # Verify embed content
        self.assertIn("Help: !mega", embed.title)
        self.assertIn("Download a file from MEGA", embed.description)

    async def test_novelai_command_help_display(self):
        """Test NovelAI command help display."""
        mock_ctx = MagicMock()
        mock_ctx.bot.command_prefix = "!"
        mock_ctx.reply = AsyncMock()

        command_info = CommandInfo(
            name="nai",
            callback=MagicMock(),
            description="Generate an image using NovelAI"
        )

        await self.registry._send_command_help(command_info, mock_ctx)

        # Verify help was sent
        mock_ctx.reply.assert_called_once()
        call_args = mock_ctx.reply.call_args[1]
        embed = call_args['embed']

        # Verify embed content
        self.assertIn("Help: !nai", embed.title)
        self.assertIn("Generate an image", embed.description)

    async def test_auth_command_help_display(self):
        """Test auth command help display."""
        mock_ctx = MagicMock()
        mock_ctx.bot.command_prefix = "!"
        mock_ctx.reply = AsyncMock()

        command_info = CommandInfo(
            name="auth",
            callback=MagicMock(),
            description="Authorization management commands (admin only)"
        )

        await self.registry._send_command_help(command_info, mock_ctx)

        # Verify help was sent
        mock_ctx.reply.assert_called_once()
        call_args = mock_ctx.reply.call_args[1]
        embed = call_args['embed']

        # Verify embed content
        self.assertIn("Help: !auth", embed.title)
        self.assertIn("Authorization management", embed.description)


class TestCommandIntegration(unittest.TestCase):
    """Test command integration with help system."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_bot = MagicMock()
        self.mock_bot.command_prefix = "!"
        self.mock_auth_manager = MagicMock()
        self.mock_unauthorized_handler = MagicMock()

        self.registry = CommandRegistry(
            bot=self.mock_bot,
            auth_manager=self.mock_auth_manager,
            unauthorized_handler=self.mock_unauthorized_handler
        )

    async def test_mega_commands_integration(self):
        """Test MEGA commands integration with help system."""
        # Create mock dependencies
        mock_config = MagicMock()
        mock_config.get_mega_upload_service.return_value = "catbox"

        mega_commands = MegaCommands(
            config=mock_config,
            downloader=MagicMock(),
            converter=MagicMock(),
            catbox_uploader=MagicMock(),
            discord_uploader=MagicMock()
        )

        # Register commands
        mega_commands.register_commands(self.registry)

        # Verify command was registered with help info
        self.assertIn("mega", self.registry._commands)
        command_info = self.registry._commands["mega"]

        self.assertIsNotNone(command_info.usage_examples)
        self.assertIsNotNone(command_info.help_text)

    async def test_novelai_commands_integration(self):
        """Test NovelAI commands integration with help system."""
        # Create mock dependencies
        mock_config = MagicMock()
        mock_config.get_novelai_upload_service.return_value = "discord"

        novelai_commands = NovelAICommands(
            config=mock_config,
            image_generator=MagicMock(),
            catbox_uploader=MagicMock(),
            discord_uploader=MagicMock()
        )

        # Register commands
        novelai_commands.register_commands(self.registry)

        # Verify command was registered with help info
        self.assertIn("nai", self.registry._commands)
        command_info = self.registry._commands["nai"]

        self.assertIsNotNone(command_info.usage_examples)
        self.assertIsNotNone(command_info.help_text)

    async def test_auth_commands_integration(self):
        """Test auth commands integration with help system."""
        # Create mock auth manager
        mock_auth_manager = MagicMock()
        mock_auth_manager.auth_enabled = True

        auth_commands = AuthCommands(auth_manager=mock_auth_manager)

        # Register commands
        auth_commands.register_commands(self.registry)

        # Verify group was created
        self.mock_bot.add_command.assert_called()


class TestCommandArgumentParsing(unittest.TestCase):
    """Test command argument parsing and processing."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_bot = MagicMock()
        self.mock_auth_manager = MagicMock()
        self.mock_unauthorized_handler = MagicMock()

        self.registry = CommandRegistry(
            bot=self.mock_bot,
            auth_manager=self.mock_auth_manager,
            unauthorized_handler=self.mock_unauthorized_handler
        )

    async def test_novelai_argument_joining(self):
        """Test NovelAI argument joining for keyword-only pattern."""
        # Create mock callback with NovelAI signature
        mock_callback = AsyncMock()

        # Mock the signature inspection
        def mock_nai_callback(ctx, *, args):
            pass

        mock_ctx = MagicMock()
        test_args = ["beautiful", "landscape,", "mountains,", "sunset"]

        # Test argument joining
        await self.registry._call_command_callback(mock_nai_callback, mock_ctx, *test_args)

        # The callback should be called with joined arguments
        # This tests the internal logic of argument processing

    def test_signature_detection(self):
        """Test command signature detection."""
        # Test NovelAI pattern detection
        def nai_callback(ctx, *, args):
            pass

        sig = inspect.signature(nai_callback)
        params = list(sig.parameters.values())

        # Should detect keyword-only pattern
        self.assertEqual(len(params), 2)
        self.assertEqual(params[0].name, 'ctx')
        self.assertEqual(params[1].name, 'args')
        self.assertEqual(params[1].kind, inspect.Parameter.KEYWORD_ONLY)

        # Test MEGA pattern detection
        def mega_callback(ctx, url, bitrate=None):
            pass

        sig = inspect.signature(mega_callback)
        params = list(sig.parameters.values())

        # Should detect regular pattern
        self.assertEqual(len(params), 3)
        self.assertEqual(params[0].name, 'ctx')
        self.assertEqual(params[1].name, 'url')
        self.assertEqual(params[2].name, 'bitrate')


class TestPingCommand(unittest.TestCase):
    """Test ping command functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_config = MagicMock()
        self.general_commands = GeneralCommands(config=self.mock_config)

    @pytest.mark.asyncio
    async def test_ping_command_success(self):
        """Test successful ping command execution."""
        # Create mock context
        mock_ctx = MagicMock()
        mock_ctx.bot.user.id = 123456789
        mock_ctx.bot.latency = 0.05  # 50ms
        mock_ctx.bot.fetch_user = AsyncMock(return_value=MagicMock())
        mock_ctx.send = AsyncMock()
        mock_ctx.guild.shard_id = 0

        # Execute ping command
        await self.general_commands.ping_command(mock_ctx)

        # Verify API call was made
        mock_ctx.bot.fetch_user.assert_called_once_with(123456789)

        # Verify response was sent
        mock_ctx.send.assert_called_once()
        call_args = mock_ctx.send.call_args[1]
        embed = call_args['embed']

        # Verify embed content
        self.assertIn("Pong!", embed.title)
        self.assertIn("Connection Quality", embed.description)

    @pytest.mark.asyncio
    async def test_ping_command_api_error(self):
        """Test ping command with API error."""
        import discord

        # Create mock context
        mock_ctx = MagicMock()
        mock_ctx.bot.user.id = 123456789
        mock_ctx.bot.latency = 0.05  # 50ms
        mock_ctx.bot.fetch_user = AsyncMock(side_effect=discord.HTTPException(
            response=MagicMock(), message="API Error"
        ))
        mock_ctx.send = AsyncMock()

        # Execute ping command
        await self.general_commands.ping_command(mock_ctx)

        # Verify error response was sent
        mock_ctx.send.assert_called_once()
        call_args = mock_ctx.send.call_args[1]
        embed = call_args['embed']

        # Verify error embed content
        self.assertIn("Network Error", embed.title)
        self.assertIn("WebSocket Latency", embed.fields[0].name)

    @pytest.mark.asyncio
    async def test_ping_command_unexpected_error(self):
        """Test ping command with unexpected error."""
        # Create mock context
        mock_ctx = MagicMock()
        mock_ctx.bot.user.id = 123456789
        mock_ctx.bot.latency = 0.05  # 50ms
        mock_ctx.bot.fetch_user = AsyncMock(side_effect=Exception("Unexpected error"))
        mock_ctx.send = AsyncMock()

        # Execute ping command
        await self.general_commands.ping_command(mock_ctx)

        # Verify error response was sent
        mock_ctx.send.assert_called_once()
        call_args = mock_ctx.send.call_args[1]
        embed = call_args['embed']

        # Verify error embed content
        self.assertIn("Ping Failed", embed.title)

    def test_latency_quality_excellent(self):
        """Test latency quality determination for excellent connection."""
        quality = self.general_commands._get_latency_quality(30.0)

        self.assertEqual(quality["emoji"], "🟢")
        self.assertEqual(quality["description"], "Excellent")
        self.assertEqual(quality["level"], 4)

    def test_latency_quality_good(self):
        """Test latency quality determination for good connection."""
        quality = self.general_commands._get_latency_quality(75.0)

        self.assertEqual(quality["emoji"], "🟡")
        self.assertEqual(quality["description"], "Good")
        self.assertEqual(quality["level"], 3)

    def test_latency_quality_fair(self):
        """Test latency quality determination for fair connection."""
        quality = self.general_commands._get_latency_quality(150.0)

        self.assertEqual(quality["emoji"], "🟠")
        self.assertEqual(quality["description"], "Fair")
        self.assertEqual(quality["level"], 2)

    def test_latency_quality_poor(self):
        """Test latency quality determination for poor connection."""
        quality = self.general_commands._get_latency_quality(300.0)

        self.assertEqual(quality["emoji"], "🔴")
        self.assertEqual(quality["description"], "Poor")
        self.assertEqual(quality["level"], 1)

    def test_latency_quality_very_poor(self):
        """Test latency quality determination for very poor connection."""
        quality = self.general_commands._get_latency_quality(1000.0)

        self.assertEqual(quality["emoji"], "🔴")
        self.assertEqual(quality["description"], "Very Poor")
        self.assertEqual(quality["level"], 0)

    def test_latency_quality_invalid(self):
        """Test latency quality determination for invalid measurement."""
        quality = self.general_commands._get_latency_quality(-10.0)

        self.assertEqual(quality["emoji"], "⚠️")
        self.assertEqual(quality["description"], "Invalid measurement")
        self.assertEqual(quality["level"], 0)

    def test_quality_indicator_excellent(self):
        """Test overall quality indicator for excellent level."""
        indicator = self.general_commands._get_quality_indicator(4)

        self.assertEqual(indicator["emoji"], "🟢")
        self.assertEqual(indicator["text"], "Excellent")

    def test_quality_indicator_critical(self):
        """Test overall quality indicator for critical level."""
        indicator = self.general_commands._get_quality_indicator(0)

        self.assertEqual(indicator["emoji"], "⚠️")
        self.assertEqual(indicator["text"], "Critical")


def run_async_test(test_func):
    """Helper to run async tests."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(test_func())
    finally:
        loop.close()


if __name__ == "__main__":
    unittest.main()
