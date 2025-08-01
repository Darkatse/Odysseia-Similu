"""Comprehensive integration tests for SimiluBot."""
import unittest
import tempfile
import os
import sys
from unittest.mock import MagicMock, patch, AsyncMock
import pytest

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from similubot.core.command_registry import CommandRegistry
from similubot.commands.mega_commands import MegaCommands
from similubot.commands.novelai_commands import NovelAICommands
from similubot.commands.auth_commands import AuthCommands


class TestCommandWorkflowIntegration(unittest.TestCase):
    """Test complete command workflow integration."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_bot = MagicMock()
        self.mock_bot.command_prefix = "!"
        self.mock_auth_manager = MagicMock()
        self.mock_auth_manager.is_authorized.return_value = True
        self.mock_unauthorized_handler = MagicMock()

        self.registry = CommandRegistry(
            bot=self.mock_bot,
            auth_manager=self.mock_auth_manager,
            unauthorized_handler=self.mock_unauthorized_handler
        )

    @pytest.mark.asyncio
    async def test_mega_command_full_workflow(self):
        """Test complete MEGA command workflow."""
        # Create mock dependencies
        mock_config = MagicMock()
        mock_config.get_mega_upload_service.return_value = "catbox"
        mock_config.get_default_bitrate.return_value = 128

        mock_downloader = MagicMock()
        mock_downloader.is_valid_mega_link.return_value = True
        mock_downloader.download.return_value = (True, "/tmp/test.mp3", None)

        mock_converter = MagicMock()
        mock_converter.convert_to_aac.return_value = (True, "/tmp/test.aac", None)

        mock_catbox_uploader = MagicMock()
        mock_catbox_uploader.upload.return_value = (True, "https://files.catbox.moe/test.aac", None)

        mock_discord_uploader = MagicMock()

        # Create MEGA commands
        mega_commands = MegaCommands(
            config=mock_config,
            downloader=mock_downloader,
            converter=mock_converter,
            catbox_uploader=mock_catbox_uploader,
            discord_uploader=mock_discord_uploader
        )

        # Register commands
        mega_commands.register_commands(self.registry)

        # Create mock context
        mock_ctx = MagicMock()
        mock_ctx.author.id = "123456789"
        mock_ctx.reply = AsyncMock()

        # Get wrapped command
        command_info = self.registry._commands["mega"]
        wrapped_command = self.registry._wrap_command_with_auth(command_info)

        # Execute command
        await wrapped_command(mock_ctx, "https://mega.nz/file/test", "192")

        # Verify workflow
        mock_downloader.download.assert_called_once()
        mock_converter.convert_to_aac.assert_called_once()
        mock_catbox_uploader.upload.assert_called_once()

    @pytest.mark.asyncio
    async def test_novelai_command_full_workflow(self):
        """Test complete NovelAI command workflow."""
        # Create mock dependencies
        mock_config = MagicMock()
        mock_config.get_novelai_upload_service.return_value = "discord"

        mock_image_generator = MagicMock()
        mock_image_generator.generate_image.return_value = (
            True, b"image_data", {"prompt": "test"}, None
        )

        mock_catbox_uploader = MagicMock()
        mock_discord_uploader = MagicMock()
        mock_discord_uploader.upload.return_value = (True, MagicMock(), None)

        # Create NovelAI commands
        novelai_commands = NovelAICommands(
            config=mock_config,
            image_generator=mock_image_generator,
            catbox_uploader=mock_catbox_uploader,
            discord_uploader=mock_discord_uploader
        )

        # Register commands
        novelai_commands.register_commands(self.registry)

        # Create mock context
        mock_ctx = MagicMock()
        mock_ctx.author.id = "123456789"
        mock_ctx.reply = AsyncMock()
        mock_ctx.channel = MagicMock()

        # Get wrapped command
        command_info = self.registry._commands["nai"]
        wrapped_command = self.registry._wrap_command_with_auth(command_info)

        # Execute command
        await wrapped_command(mock_ctx, args="beautiful landscape")

        # Verify workflow
        mock_image_generator.generate_image.assert_called_once()
        mock_discord_uploader.upload.assert_called_once()

    @pytest.mark.asyncio
    async def test_auth_command_full_workflow(self):
        """Test complete auth command workflow."""
        # Create mock auth manager
        mock_auth_manager = MagicMock()
        mock_auth_manager.auth_enabled = True
        mock_auth_manager.is_admin.return_value = True
        mock_auth_manager.get_stats.return_value = {
            "total_users": 5,
            "admin_users": 1,
            "full_access_users": 2,
            "module_access_users": 1,
            "no_access_users": 1
        }

        # Create auth commands
        auth_commands = AuthCommands(auth_manager=mock_auth_manager)

        # Register commands
        auth_commands.register_commands(self.registry)

        # Create mock context
        mock_ctx = MagicMock()
        mock_ctx.author.id = "999999999"  # Admin user
        mock_ctx.reply = AsyncMock()

        # Get the auth group
        group_calls = self.mock_bot.add_command.call_args_list
        auth_group = None
        for call in group_calls:
            command = call[0][0]
            if hasattr(command, 'name') and command.name == 'auth':
                auth_group = command
                break

        self.assertIsNotNone(auth_group)

        # Execute auth command (should show help)
        await auth_group.callback(mock_ctx)

        # Verify help was displayed
        mock_ctx.reply.assert_called_once()


class TestErrorHandlingIntegration(unittest.TestCase):
    """Test error handling across components."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_bot = MagicMock()
        self.mock_bot.command_prefix = "!"
        self.mock_auth_manager = MagicMock()
        self.mock_auth_manager.is_authorized.return_value = True
        self.mock_unauthorized_handler = MagicMock()

        self.registry = CommandRegistry(
            bot=self.mock_bot,
            auth_manager=self.mock_auth_manager,
            unauthorized_handler=self.mock_unauthorized_handler
        )

    @pytest.mark.asyncio
    async def test_command_help_on_missing_arguments(self):
        """Test that help is shown when commands are called without arguments."""
        # Create mock MEGA commands
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

        # Create mock context
        mock_ctx = MagicMock()
        mock_ctx.author.id = "123456789"
        mock_ctx.bot.command_prefix = "!"
        mock_ctx.reply = AsyncMock()

        # Get wrapped command
        command_info = self.registry._commands["mega"]
        wrapped_command = self.registry._wrap_command_with_auth(command_info)

        # Execute command without arguments (should show help)
        await wrapped_command(mock_ctx)

        # Verify help was displayed
        mock_ctx.reply.assert_called_once()
        call_args = mock_ctx.reply.call_args

        # Should be an embed with help content
        if len(call_args) > 1 and 'embed' in call_args[1]:
            embed = call_args[1]['embed']
            self.assertIn("Help: !mega", embed.title)

    @pytest.mark.asyncio
    async def test_authorization_error_handling(self):
        """Test authorization error handling."""
        # Set up unauthorized user
        self.mock_auth_manager.is_authorized.return_value = False

        # Create mock commands
        mock_config = MagicMock()
        mega_commands = MegaCommands(
            config=mock_config,
            downloader=MagicMock(),
            converter=MagicMock(),
            catbox_uploader=MagicMock(),
            discord_uploader=MagicMock()
        )

        # Register commands
        mega_commands.register_commands(self.registry)

        # Create mock context
        mock_ctx = MagicMock()
        mock_ctx.author.id = "unauthorized_user"
        mock_ctx.reply = AsyncMock()

        # Get wrapped command
        command_info = self.registry._commands["mega"]
        wrapped_command = self.registry._wrap_command_with_auth(command_info)

        # Execute command (should be blocked)
        await wrapped_command(mock_ctx, "https://mega.nz/file/test")

        # Verify unauthorized handler was called
        self.mock_unauthorized_handler.handle_unauthorized_access.assert_called_once()

    @pytest.mark.asyncio
    async def test_cross_component_error_propagation(self):
        """Test that errors propagate correctly across components."""
        # Create mock dependencies with failures
        mock_config = MagicMock()
        mock_config.get_mega_upload_service.return_value = "catbox"

        mock_downloader = MagicMock()
        mock_downloader.is_valid_mega_link.return_value = True
        mock_downloader.download.return_value = (False, None, "Download failed")

        mega_commands = MegaCommands(
            config=mock_config,
            downloader=mock_downloader,
            converter=MagicMock(),
            catbox_uploader=MagicMock(),
            discord_uploader=MagicMock()
        )

        # Register commands
        mega_commands.register_commands(self.registry)

        # Create mock context
        mock_ctx = MagicMock()
        mock_ctx.author.id = "123456789"
        mock_ctx.reply = AsyncMock()

        # Get wrapped command
        command_info = self.registry._commands["mega"]
        wrapped_command = self.registry._wrap_command_with_auth(command_info)

        # Execute command (should handle download failure)
        await wrapped_command(mock_ctx, "https://mega.nz/file/test")

        # Verify error was handled
        mock_ctx.reply.assert_called()


if __name__ == "__main__":
    unittest.main()
