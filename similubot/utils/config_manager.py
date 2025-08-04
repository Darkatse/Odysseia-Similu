"""Configuration manager for SimiluBot."""
import logging
import os
from typing import Any, Dict, List, Optional
import yaml

class ConfigManager:
    """
    Configuration manager for SimiluBot.

    Handles loading and accessing configuration values from the config file.
    """

    def __init__(self, config_path: str = "config/config.yaml"):
        """
        Initialize the ConfigManager.

        Args:
            config_path: Path to the configuration file

        Raises:
            FileNotFoundError: If the configuration file does not exist
            yaml.YAMLError: If the configuration file is not valid YAML
        """
        self.logger = logging.getLogger("similubot.config")
        self.config_path = config_path
        self.config: Dict[str, Any] = {}

        self._load_config()

    def _load_config(self) -> None:
        """
        Load the configuration from the config file.

        Raises:
            FileNotFoundError: If the configuration file does not exist
            yaml.YAMLError: If the configuration file is not valid YAML
        """
        if not os.path.exists(self.config_path):
            example_path = f"{self.config_path}.example"
            if os.path.exists(example_path):
                self.logger.error(
                    f"Configuration file {self.config_path} not found. "
                    f"Please copy {example_path} to {self.config_path} and update it."
                )
            else:
                self.logger.error(f"Configuration file {self.config_path} not found.")
            raise FileNotFoundError(f"Configuration file {self.config_path} not found")

        try:
            with open(self.config_path, 'r', encoding='utf-8') as config_file:
                self.config = yaml.safe_load(config_file)
                self.logger.debug(f"Loaded configuration from {self.config_path}")
        except yaml.YAMLError as e:
            self.logger.error(f"Error parsing configuration file: {e}")
            raise

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: The configuration key (dot notation for nested keys)
            default: Default value to return if the key is not found

        Returns:
            The configuration value or the default value if not found
        """
        keys = key.split('.')
        value = self.config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                self.logger.debug(f"Configuration key '{key}' not found, using default: {default}")
                return default

        return value

    def get_discord_token(self) -> str:
        """
        Get the Discord bot token.

        Returns:
            The Discord bot token

        Raises:
            ValueError: If the Discord bot token is not set
        """
        token = self.get('discord.token')
        if not token or token == "YOUR_DISCORD_BOT_TOKEN_HERE":
            self.logger.error("Discord bot token not set in configuration")
            raise ValueError("Discord bot token not set in configuration")
        return token

    def get_download_temp_dir(self) -> str:
        """
        Get the temporary directory for downloads.

        Returns:
            The temporary directory path
        """
        return self.get('download.temp_dir', './temp')

    def get_log_level(self) -> str:
        """
        Get the logging level.

        Returns:
            The logging level
        """
        return self.get('logging.level', 'INFO')

    def get_log_file(self) -> Optional[str]:
        """
        Get the log file path.

        Returns:
            The log file path or None if not set
        """
        return self.get('logging.file', None)

    def get_log_max_size(self) -> int:
        """
        Get the maximum log file size.

        Returns:
            The maximum log file size in bytes
        """
        return self.get('logging.max_size', 10485760)  # 10 MB

    def get_log_backup_count(self) -> int:
        """
        Get the number of backup log files to keep.

        Returns:
            The number of backup log files
        """
        return self.get('logging.backup_count', 5)

    def is_auth_enabled(self) -> bool:
        """
        Check if the authorization system is enabled.

        Returns:
            True if authorization is enabled, False otherwise
        """
        return self.get('authorization.enabled', True)

    def get_admin_ids(self) -> list:
        """
        Get the list of administrator Discord IDs.

        Returns:
            List of administrator Discord IDs
        """
        return self.get('authorization.admin_ids', [])

    def get_auth_config_path(self) -> str:
        """
        Get the path to the authorization configuration file.

        Returns:
            Path to the authorization configuration file
        """
        return self.get('authorization.config_path', 'config/authorization.json')

    def should_notify_admins_on_unauthorized(self) -> bool:
        """
        Check if admins should be notified on unauthorized access attempts.

        Returns:
            True if admins should be notified, False otherwise
        """
        return self.get('authorization.notify_admins_on_unauthorized', True)

    # Music Configuration Methods
    def is_music_enabled(self) -> bool:
        """
        Check if music functionality is enabled.

        Returns:
            True if music is enabled, False otherwise
        """
        return self.get('music.enabled', True)

    def get_music_max_queue_size(self) -> int:
        """
        Get the maximum queue size for music.

        Returns:
            Maximum queue size
        """
        return self.get('music.max_queue_size', 100)

    def get_music_max_song_duration(self) -> int:
        """
        Get the maximum song duration in seconds.

        Returns:
            Maximum song duration in seconds
        """
        return self.get('music.max_song_duration', 3600)

    def get_music_auto_disconnect_timeout(self) -> int:
        """
        Get the auto-disconnect timeout in seconds.

        Returns:
            Auto-disconnect timeout in seconds
        """
        return self.get('music.auto_disconnect_timeout', 300)

    def get_music_volume(self) -> float:
        """
        Get the default music volume.

        Returns:
            Default volume (0.0-1.0)
        """
        return self.get('music.volume', 0.5)

    # YouTube PoToken Configuration Methods
    def is_youtube_auto_fallback_enabled(self) -> bool:
        """
        Check if automatic fallback on bot detection is enabled.

        Returns:
            True if auto fallback is enabled, False otherwise
        """
        return self.get('music.youtube.auto_fallback_on_bot_detection', True)

    def is_potoken_enabled(self) -> bool:
        """
        Check if PoToken functionality is enabled.

        Returns:
            True if PoToken is enabled, False otherwise
        """
        return self.get('music.youtube.potoken.enabled', False)

    def is_potoken_auto_generate_enabled(self) -> bool:
        """
        Check if automatic PoToken generation is enabled.

        Returns:
            True if auto generation is enabled, False otherwise
        """
        return self.get('music.youtube.potoken.auto_generate', True)

    def get_potoken_client(self) -> str:
        """
        Get the PoToken client type.

        Returns:
            Client type for PoToken usage
        """
        return self.get('music.youtube.potoken.client', 'WEB')

    def get_manual_visitor_data(self) -> str:
        """
        Get the manual visitor data for PoToken.

        Returns:
            Manual visitor data string
        """
        return self.get('music.youtube.potoken.manual.visitor_data', '')

    def get_manual_po_token(self) -> str:
        """
        Get the manual PoToken.

        Returns:
            Manual PoToken string
        """
        return self.get('music.youtube.potoken.manual.po_token', '')

    def is_potoken_cache_enabled(self) -> bool:
        """
        Check if PoToken caching is enabled.

        Returns:
            True if caching is enabled, False otherwise
        """
        return self.get('music.youtube.potoken.cache_enabled', True)

    def is_fallback_web_client_enabled(self) -> bool:
        """
        Check if WEB client fallback is enabled.

        Returns:
            True if WEB client fallback is enabled, False otherwise
        """
        return self.get('music.youtube.fallback.use_web_client', True)

    def is_manual_potoken_prompt_enabled(self) -> bool:
        """
        Check if manual PoToken prompting is enabled.

        Returns:
            True if manual prompting is enabled, False otherwise
        """
        return self.get('music.youtube.fallback.prompt_for_manual_potoken', False)

    # Playback Event Configuration Methods
    def is_notify_absent_users_enabled(self) -> bool:
        """
        Check if notifications to absent users are enabled.

        When enabled, the bot will send "your song is next" notifications
        to users who are not in the voice channel when their song is about to play.

        Returns:
            True if absent user notifications are enabled, False otherwise
        """
        return self.get('playback.notify_absent_users', True)

    # Skip Voting Configuration Methods
    def is_skip_voting_enabled(self) -> bool:
        """
        Check if democratic skip voting is enabled.

        Returns:
            True if skip voting is enabled, False otherwise (direct skip)
        """
        return self.get('music.skip_voting.enabled', True)

    def get_skip_voting_threshold(self) -> str:
        """
        Get the skip voting threshold configuration.

        Returns:
            Threshold value as string (supports both numbers and percentages)
            Examples: "5", "50%"
        """
        threshold = self.get('music.skip_voting.threshold', 5)
        return str(threshold)

    def get_skip_voting_timeout(self) -> int:
        """
        Get the skip voting timeout in seconds.

        Returns:
            Timeout in seconds for voting polls
        """
        return self.get('music.skip_voting.timeout', 60)

    def get_skip_voting_min_voters(self) -> int:
        """
        Get the minimum number of voters required for voting.

        When voice channel has fewer users than this, direct skip is allowed.

        Returns:
            Minimum number of voters required
        """
        return self.get('music.skip_voting.min_voters', 2)
