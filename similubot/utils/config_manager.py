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

    # NetEase Proxy Configuration Methods
    def is_netease_proxy_enabled(self) -> bool:
        """
        检查是否启用了网易云音乐反向代理功能

        Returns:
            如果启用反向代理则返回True
        """
        return self.get('netease_proxy.enabled', False)

    def get_netease_proxy_domain(self) -> Optional[str]:
        """
        获取网易云音乐反向代理域名

        Returns:
            代理域名，如果未配置则返回None
        """
        domain = self.get('netease_proxy.proxy_domain', '')
        return domain.strip() if domain else None

    def should_use_https_for_proxy(self) -> bool:
        """
        检查代理请求是否应该使用HTTPS

        Returns:
            如果应该使用HTTPS则返回True
        """
        return self.get('netease_proxy.use_https', False)

    def get_netease_domain_mapping(self) -> Dict[str, str]:
        """
        获取网易云音乐域名映射配置

        Returns:
            域名映射字典，键为原始域名，值为目标域名
        """
        mapping = self.get('netease_proxy.domain_mapping', {})
        if not isinstance(mapping, dict):
            self.logger.warning("域名映射配置格式错误，使用默认配置")
            return {}

        # 过滤掉空值，使用默认代理域名
        proxy_domain = self.get_netease_proxy_domain()
        result = {}

        for original_domain, target_domain in mapping.items():
            if target_domain and target_domain.strip():
                result[original_domain] = target_domain.strip()
            elif proxy_domain:
                result[original_domain] = proxy_domain

        return result

    def should_preserve_referer(self) -> bool:
        """
        检查是否应该保持原始Referer头

        Returns:
            如果应该保持原始Referer则返回True
        """
        return self.get('netease_proxy.headers.preserve_referer', True)

    def should_preserve_host(self) -> bool:
        """
        检查是否应该保持原始Host头

        Returns:
            如果应该保持原始Host则返回True
        """
        return self.get('netease_proxy.headers.preserve_host', False)

    def get_netease_proxy_custom_headers(self) -> Dict[str, str]:
        """
        获取自定义代理请求头

        Returns:
            自定义请求头字典
        """
        headers = self.get('netease_proxy.headers.custom_headers', {})
        if not isinstance(headers, dict):
            self.logger.warning("自定义请求头配置格式错误，使用空字典")
            return {}
        return headers

    def should_log_domain_replacement(self) -> bool:
        """
        检查是否应该记录域名替换的详细日志

        Returns:
            如果应该记录域名替换日志则返回True
        """
        return self.get('netease_proxy.debug.log_domain_replacement', True)

    def should_log_proxy_requests(self) -> bool:
        """
        检查是否应该记录代理请求的详细信息

        Returns:
            如果应该记录代理请求日志则返回True
        """
        return self.get('netease_proxy.debug.log_proxy_requests', False)

    # NetEase Member Authentication Configuration Methods
    def is_netease_member_enabled(self) -> bool:
        """
        检查是否启用了网易云音乐会员认证功能

        Returns:
            如果启用会员认证则返回True
        """
        return self.get('netease_member.enabled', False)

    def get_netease_member_music_u(self) -> Optional[str]:
        """
        获取网易云音乐会员MUSIC_U Cookie

        Returns:
            MUSIC_U Cookie值，如果未配置则返回None
        """
        music_u = self.get('netease_member.cookies.MUSIC_U', '')
        return music_u.strip() if music_u else None

    def get_netease_member_csrf_token(self) -> Optional[str]:
        """
        获取网易云音乐会员CSRF令牌

        Returns:
            CSRF令牌，如果未配置则返回None
        """
        csrf = self.get('netease_member.cookies.__csrf', '')
        return csrf.strip() if csrf else None

    def get_netease_member_additional_cookies(self) -> Dict[str, str]:
        """
        获取网易云音乐会员额外Cookie

        Returns:
            额外Cookie字典
        """
        cookies = self.get('netease_member.cookies.additional_cookies', {})
        if not isinstance(cookies, dict):
            self.logger.warning("额外Cookie配置格式错误，使用空字典")
            return {}
        return cookies

    def get_netease_member_default_quality(self) -> str:
        """
        获取网易云音乐会员默认音频质量等级

        Returns:
            音频质量等级字符串
        """
        return self.get('netease_member.audio_quality.default_level', 'exhigh')

    def get_netease_member_preferred_format(self) -> str:
        """
        获取网易云音乐会员偏好音频格式

        Returns:
            音频格式字符串
        """
        return self.get('netease_member.audio_quality.preferred_format', 'aac')

    def should_netease_member_auto_fallback(self) -> bool:
        """
        检查是否应该自动降级音质

        Returns:
            如果应该自动降级则返回True
        """
        return self.get('netease_member.audio_quality.auto_fallback', True)

    def get_netease_member_validity_check_interval(self) -> int:
        """
        获取Cookie有效性检查间隔

        Returns:
            检查间隔秒数
        """
        return self.get('netease_member.authentication.validity_check_interval', 3600)

    def should_netease_member_auto_disable_on_invalid(self) -> bool:
        """
        检查是否在Cookie失效时自动禁用会员功能

        Returns:
            如果应该自动禁用则返回True
        """
        return self.get('netease_member.authentication.auto_disable_on_invalid', True)

    def get_netease_member_max_retry_attempts(self) -> int:
        """
        获取会员API调用最大重试次数

        Returns:
            最大重试次数
        """
        return self.get('netease_member.authentication.max_retry_attempts', 3)

    def get_netease_member_retry_interval(self) -> int:
        """
        获取会员API调用重试间隔

        Returns:
            重试间隔秒数
        """
        return self.get('netease_member.authentication.retry_interval', 2)

    def is_netease_member_cache_enabled(self) -> bool:
        """
        检查是否启用会员信息缓存

        Returns:
            如果启用缓存则返回True
        """
        return self.get('netease_member.cache.enabled', True)

    def get_netease_member_cache_expiry_time(self) -> int:
        """
        获取会员信息缓存过期时间

        Returns:
            缓存过期时间秒数
        """
        return self.get('netease_member.cache.expiry_time', 1800)

    def should_netease_member_cache_audio_urls(self) -> bool:
        """
        检查是否缓存音频URL

        Returns:
            如果应该缓存音频URL则返回True
        """
        return self.get('netease_member.cache.cache_audio_urls', True)

    def get_netease_member_audio_url_expiry(self) -> int:
        """
        获取音频URL缓存过期时间

        Returns:
            音频URL缓存过期时间秒数
        """
        return self.get('netease_member.cache.audio_url_expiry', 300)

    def should_log_netease_member_authentication(self) -> bool:
        """
        检查是否记录会员认证相关日志

        Returns:
            如果应该记录认证日志则返回True
        """
        return self.get('netease_member.debug.log_authentication', True)

    def should_log_netease_member_quality_selection(self) -> bool:
        """
        检查是否记录音频质量选择过程

        Returns:
            如果应该记录质量选择日志则返回True
        """
        return self.get('netease_member.debug.log_quality_selection', True)

    def should_log_netease_member_cookie_usage(self) -> bool:
        """
        检查是否记录Cookie使用情况

        Returns:
            如果应该记录Cookie使用日志则返回True
        """
        return self.get('netease_member.debug.log_cookie_usage', False)

    def should_mask_netease_member_sensitive_data(self) -> bool:
        """
        检查是否在日志中隐藏敏感信息

        Returns:
            如果应该隐藏敏感信息则返回True
        """
        return self.get('netease_member.debug.mask_sensitive_data', True)

    def should_netease_member_fallback_to_free(self) -> bool:
        """
        检查是否与免费用户功能兼容

        Returns:
            如果应该回退到免费模式则返回True
        """
        return self.get('netease_member.compatibility.fallback_to_free', True)

    def get_netease_member_error_handling(self) -> str:
        """
        获取错误处理策略

        Returns:
            错误处理策略字符串 (silent/notify/strict)
        """
        return self.get('netease_member.compatibility.error_handling', 'notify')

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
