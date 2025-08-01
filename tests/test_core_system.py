"""Comprehensive tests for core SimiluBot system functionality."""
import unittest
import tempfile
import os
import sys
from unittest.mock import MagicMock, patch, AsyncMock
import pytest

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from similubot.utils.config_manager import ConfigManager
from similubot.uploaders.catbox_uploader import CatboxUploader
from similubot.uploaders.discord_uploader import DiscordUploader


class TestConfigurationManagement(unittest.TestCase):
    """Test configuration management functionality."""

    def test_config_manager_initialization(self):
        """Test configuration manager initialization."""
        with patch('similubot.utils.config_manager.ConfigManager.load_config', return_value={}):
            config = ConfigManager("test_config.json")
            self.assertIsNotNone(config)

    def test_config_file_not_found(self):
        """Test handling of missing configuration file."""
        with patch('similubot.utils.config_manager.os.path.exists', return_value=False):
            with self.assertRaises(FileNotFoundError):
                ConfigManager("nonexistent_config.json")

    def test_config_value_retrieval(self):
        """Test configuration value retrieval."""
        config_data = {
            "mega": {"enabled": True, "default_bitrate": 128, "upload_service": "catbox"},
            "novelai": {"upload_service": "discord"}
        }

        with patch('similubot.utils.config_manager.ConfigManager.load_config', return_value=config_data):
            config = ConfigManager("test_config.json")

            # Test basic config loading
            self.assertIsNotNone(config)

    def test_mega_enabled_configuration(self):
        """Test MEGA enabled configuration option."""
        # Test with MEGA enabled
        config_data = {"mega": {"enabled": True}}
        with patch('similubot.utils.config_manager.ConfigManager._load_config'):
            config = ConfigManager("test_config.json")
            config.config = config_data
            self.assertTrue(config.is_mega_enabled())

        # Test with MEGA disabled
        config_data = {"mega": {"enabled": False}}
        with patch('similubot.utils.config_manager.ConfigManager._load_config'):
            config = ConfigManager("test_config.json")
            config.config = config_data
            self.assertFalse(config.is_mega_enabled())

        # Test with MEGA config missing (should default to True for backward compatibility)
        config_data = {}
        with patch('similubot.utils.config_manager.ConfigManager._load_config'):
            config = ConfigManager("test_config.json")
            config.config = config_data
            self.assertTrue(config.is_mega_enabled())


class TestUploaders(unittest.TestCase):
    """Test upload service functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.catbox_uploader = CatboxUploader()
        self.discord_uploader = DiscordUploader()

    def test_catbox_uploader_initialization(self):
        """Test CatBox uploader initialization."""
        self.assertIsNotNone(self.catbox_uploader)

    @patch('similubot.uploaders.catbox_uploader.requests.post')
    def test_catbox_upload_success(self, mock_post):
        """Test successful CatBox upload."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "https://files.catbox.moe/test.aac"
        mock_post.return_value = mock_response

        # Test upload
        with tempfile.NamedTemporaryFile(suffix='.aac') as test_file:
            success, url, error = self.catbox_uploader.upload(test_file.name)

            self.assertTrue(success)
            self.assertEqual(url, "https://files.catbox.moe/test.aac")
            self.assertIsNone(error)

    @patch('similubot.uploaders.catbox_uploader.requests.post')
    def test_catbox_upload_failure(self, mock_post):
        """Test CatBox upload failure."""
        # Mock failed response
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Server error"
        mock_post.return_value = mock_response

        # Test upload failure
        with tempfile.NamedTemporaryFile(suffix='.aac') as test_file:
            success, url, error = self.catbox_uploader.upload(test_file.name)

            self.assertFalse(success)
            self.assertIsNone(url)
            self.assertIsNotNone(error)

    def test_discord_uploader_initialization(self):
        """Test Discord uploader initialization."""
        self.assertIsNotNone(self.discord_uploader)

    @pytest.mark.asyncio
    async def test_discord_upload_success(self):
        """Test successful Discord upload."""
        # Mock Discord channel
        mock_channel = MagicMock()
        mock_message = MagicMock()
        mock_channel.send.return_value = mock_message

        # Test upload
        with tempfile.NamedTemporaryFile(suffix='.aac') as test_file:
            success, message, error = await self.discord_uploader.upload(
                test_file.name, mock_channel, "Test upload"
            )

            self.assertTrue(success)
            self.assertEqual(message, mock_message)
            self.assertIsNone(error)

    @pytest.mark.asyncio
    async def test_discord_upload_failure(self):
        """Test Discord upload failure."""
        # Mock Discord channel with failure
        mock_channel = MagicMock()
        mock_channel.send.side_effect = Exception("Discord error")

        # Test upload failure
        with tempfile.NamedTemporaryFile(suffix='.aac') as test_file:
            success, message, error = await self.discord_uploader.upload(
                test_file.name, mock_channel, "Test upload"
            )

            self.assertFalse(success)
            self.assertIsNone(message)
            self.assertIsNotNone(error)


if __name__ == "__main__":
    unittest.main()
