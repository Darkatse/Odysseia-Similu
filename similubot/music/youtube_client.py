"""YouTube audio extraction client using pytubefix."""

import logging
import os
import re
import asyncio
import time
from typing import Optional, Tuple, Callable, Dict, Any
from dataclasses import dataclass
from pytubefix import YouTube
from pytubefix.exceptions import PytubeFixError

from similubot.progress.base import ProgressTracker, ProgressInfo, ProgressStatus, ProgressCallback
from similubot.utils.config_manager import ConfigManager


class YouTubeProgressTracker(ProgressTracker):
    """
    Progress tracker for YouTube downloads using pytubefix.

    Handles progress updates from pytubefix download callbacks and
    converts them to the standard ProgressInfo format.
    """

    def __init__(self):
        """Initialize the YouTube progress tracker."""
        super().__init__("YouTube Download")
        self.logger = logging.getLogger("similubot.progress.youtube")
        self.total_size: Optional[int] = None
        self.start_time: Optional[float] = None

    def set_total_size(self, total_size: int) -> None:
        """
        Set the total file size for progress calculation.

        Args:
            total_size: Total file size in bytes
        """
        self.total_size = total_size
        self.start_time = time.time()

    def update_download_progress(self, downloaded: int, total_size: int) -> None:
        """
        Update download progress from pytubefix callback.

        Args:
            downloaded: Bytes downloaded so far
            total_size: Total file size in bytes
        """
        if total_size <= 0:
            return

        # Calculate percentage
        percentage = (downloaded / total_size) * 100

        # Calculate speed and ETA
        speed = None
        eta = None
        if self.start_time:
            elapsed = time.time() - self.start_time
            if elapsed > 0:
                speed = downloaded / elapsed  # bytes per second
                if speed > 0:
                    remaining_bytes = total_size - downloaded
                    eta = remaining_bytes / speed

        # Format message
        downloaded_mb = downloaded / (1024 * 1024)
        total_mb = total_size / (1024 * 1024)
        message = f"Downloading: {downloaded_mb:.1f}/{total_mb:.1f} MB ({percentage:.1f}%)"

        if speed:
            if speed >= 1024 * 1024:
                speed_msg = f"{speed / (1024 * 1024):.1f} MB/s"
            elif speed >= 1024:
                speed_msg = f"{speed / 1024:.1f} KB/s"
            else:
                speed_msg = f"{speed:.0f} B/s"
            message += f" - {speed_msg}"

        # Update progress
        self.update(
            percentage=percentage,
            current_size=downloaded,
            total_size=total_size,
            speed=speed,
            eta=eta,
            message=message,
            details={
                'downloaded_mb': downloaded_mb,
                'total_mb': total_mb,
                'speed_mbps': speed / (1024 * 1024) if speed else None
            }
        )

    def parse_output(self, output_line: str) -> bool:
        """
        Parse output line (not used for YouTube downloads).

        Args:
            output_line: Output line to parse

        Returns:
            False (YouTube progress comes from callbacks, not output parsing)
        """
        return False


@dataclass
class AudioInfo:
    """Information about extracted audio."""
    title: str
    duration: int  # Duration in seconds
    file_path: str
    url: str
    uploader: str
    thumbnail_url: Optional[str] = None


class YouTubeClient:
    """
    YouTube audio extraction client using pytubefix.

    Handles downloading audio-only streams from YouTube videos
    with progress tracking, error handling, and PoToken support for bot detection bypass.
    """

    def __init__(self, temp_dir: str = "./temp", config: Optional[ConfigManager] = None):
        """
        Initialize the YouTube client.

        Args:
            temp_dir: Directory for temporary audio files
            config: Configuration manager for PoToken settings
        """
        self.logger = logging.getLogger("similubot.music.youtube_client")
        self.temp_dir = temp_dir
        self.config = config

        # Ensure temp directory exists
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
            self.logger.debug(f"Created temp directory: {temp_dir}")

        # PoToken configuration
        self._potoken_cache: Dict[str, Any] = {}
        self._last_successful_method: Optional[str] = None

        # Log PoToken configuration status
        if self.config:
            if self.config.is_potoken_enabled():
                self.logger.info("PoToken functionality enabled")
                if self.config.is_potoken_auto_generate_enabled():
                    self.logger.debug("Auto PoToken generation enabled")
                else:
                    self.logger.debug("Manual PoToken configuration enabled")
            else:
                self.logger.debug("PoToken functionality disabled")
        else:
            self.logger.debug("No configuration provided - PoToken functionality disabled")

    def is_youtube_url(self, url: str) -> bool:
        """
        Check if a URL is a valid YouTube URL.

        Args:
            url: URL to validate

        Returns:
            True if valid YouTube URL, False otherwise
        """
        youtube_patterns = [
            r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=[\w-]+',
            r'(?:https?://)?(?:www\.)?youtu\.be/[\w-]+',
            r'(?:https?://)?(?:www\.)?youtube\.com/embed/[\w-]+',
            r'(?:https?://)?(?:www\.)?youtube\.com/v/[\w-]+'
        ]

        return any(re.match(pattern, url) for pattern in youtube_patterns)

    def _is_bot_detection_error(self, error_message: str) -> bool:
        """
        Check if an error message indicates bot detection.

        Args:
            error_message: Error message to check

        Returns:
            True if the error indicates bot detection, False otherwise
        """
        bot_detection_indicators = [
            "detected as a bot",
            "Use `use_po_token=True`",
            "switch to WEB client",
            "bot detection",
            "HTTP Error 403"
        ]

        error_lower = error_message.lower()
        return any(indicator.lower() in error_lower for indicator in bot_detection_indicators)

    def _get_youtube_kwargs(self, url: str, attempt: int = 0) -> Dict[str, Any]:
        """
        Get YouTube constructor kwargs based on configuration and attempt number.

        Args:
            url: YouTube URL
            attempt: Attempt number (0 = first attempt, 1+ = fallback attempts)

        Returns:
            Dictionary of kwargs for YouTube constructor
        """
        kwargs = {}

        if not self.config:
            return kwargs

        # First attempt: use default settings
        if attempt == 0:
            if self.config.is_potoken_enabled() and self.config.is_potoken_auto_generate_enabled():
                # Use auto PoToken generation with configured client
                client = self.config.get_potoken_client()
                kwargs['client'] = client
                self.logger.debug(f"Using client '{client}' with auto PoToken generation")
            elif self.config.is_potoken_enabled():
                # Use manual PoToken if configured
                visitor_data = self.config.get_manual_visitor_data()
                po_token = self.config.get_manual_po_token()

                if visitor_data and po_token:
                    kwargs['use_po_token'] = True
                    # Note: pytubefix will prompt for these if not provided via po_token_verifier
                    self.logger.debug("Using manual PoToken configuration")
                else:
                    kwargs['use_po_token'] = True
                    self.logger.debug("Using PoToken with interactive input")
            return kwargs

        # Fallback attempts
        if self.config.is_youtube_auto_fallback_enabled():
            if attempt == 1 and self.config.is_fallback_web_client_enabled():
                # Try WEB client with auto PoToken
                kwargs['client'] = 'WEB'
                self.logger.info("Bot detection fallback: Trying WEB client with auto PoToken")
            elif attempt == 2:
                # Try manual PoToken
                kwargs['use_po_token'] = True
                self.logger.info("Bot detection fallback: Trying manual PoToken")

        return kwargs

    async def _create_youtube_object(self, url: str, on_progress_callback: Optional[Callable] = None, attempt: int = 0) -> Optional[YouTube]:
        """
        Create YouTube object with appropriate configuration and error handling.

        Args:
            url: YouTube URL
            on_progress_callback: Progress callback function
            attempt: Attempt number for fallback handling

        Returns:
            YouTube object if successful, None otherwise
        """
        kwargs = self._get_youtube_kwargs(url, attempt)

        if on_progress_callback:
            kwargs['on_progress_callback'] = on_progress_callback

        try:
            self.logger.debug(f"Creating YouTube object (attempt {attempt + 1}) with kwargs: {list(kwargs.keys())}")
            yt = await asyncio.to_thread(YouTube, url, **kwargs)

            # Cache successful method for future use
            if attempt > 0:
                self._last_successful_method = f"attempt_{attempt}"
                self.logger.info(f"Successfully bypassed bot detection using attempt {attempt + 1}")

            return yt

        except PytubeFixError as e:
            error_msg = str(e)
            self.logger.debug(f"YouTube object creation failed (attempt {attempt + 1}): {error_msg}")

            # Check if this is a bot detection error and we should try fallback
            if self._is_bot_detection_error(error_msg) and self.config and self.config.is_youtube_auto_fallback_enabled():
                if attempt < 2:  # Try up to 3 attempts (0, 1, 2)
                    self.logger.warning(f"Bot detection detected, trying fallback method {attempt + 2}")
                    return await self._create_youtube_object(url, on_progress_callback, attempt + 1)
                else:
                    self.logger.error("All bot detection fallback methods failed")

            raise e

    async def extract_audio_info(self, url: str) -> Optional[AudioInfo]:
        """
        Extract audio information from a YouTube URL without downloading.

        Args:
            url: YouTube URL

        Returns:
            AudioInfo object if successful, None otherwise
        """
        if not self.is_youtube_url(url):
            self.logger.error(f"Invalid YouTube URL: {url}")
            return None

        try:
            self.logger.debug(f"Extracting info from: {url}")

            # Create YouTube object with bot detection handling
            yt = await self._create_youtube_object(url)
            if not yt:
                self.logger.error(f"Failed to create YouTube object for: {url}")
                return None

            # Get audio stream info
            audio_stream = yt.streams.get_audio_only()
            if not audio_stream:
                self.logger.error(f"No audio stream found for: {url}")
                return None

            return AudioInfo(
                title=yt.title or "Unknown Title",
                duration=yt.length or 0,
                file_path="",  # Will be set during download
                url=url,
                uploader=yt.author or "Unknown",
                thumbnail_url=yt.thumbnail_url
            )

        except PytubeFixError as e:
            error_msg = str(e)
            if self._is_bot_detection_error(error_msg):
                self.logger.error(f"Bot detection error extracting info from {url}: {e}")
                self.logger.info("Consider enabling PoToken functionality in configuration to bypass bot detection")
            else:
                self.logger.error(f"PytubeFixError extracting info from {url}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error extracting info from {url}: {e}", exc_info=True)
            return None

    async def download_audio(
        self,
        url: str,
        progress_callback: Optional[ProgressCallback] = None
    ) -> Tuple[bool, Optional[AudioInfo], Optional[str]]:
        """
        Download audio from a YouTube URL.

        Args:
            url: YouTube URL
            progress_callback: Optional progress callback function

        Returns:
            Tuple of (success, AudioInfo, error_message)
        """
        if not self.is_youtube_url(url):
            return False, None, f"Invalid YouTube URL: {url}"

        # Initialize progress tracker outside try block
        progress_tracker = YouTubeProgressTracker()
        if progress_callback:
            progress_tracker.add_callback(progress_callback)

        try:
            self.logger.info(f"Starting audio download: {url}")

            # Start progress tracking
            progress_tracker.start()

            # Create progress wrapper for pytubefix
            def on_progress(stream, chunk, bytes_remaining):
                total_size = stream.filesize
                downloaded = total_size - bytes_remaining
                progress_tracker.update_download_progress(downloaded, total_size)

            # Create YouTube object with bot detection handling
            yt = await self._create_youtube_object(url, on_progress)
            if not yt:
                progress_tracker.fail("Failed to create YouTube object")
                return False, None, "Failed to create YouTube object"

            # Get best audio stream (prefer M4A format)
            audio_stream = yt.streams.filter(only_audio=True, file_extension='m4a').first()
            if not audio_stream:
                # Fallback to any audio stream
                audio_stream = yt.streams.get_audio_only()
                if not audio_stream:
                    progress_tracker.fail("No audio stream available")
                    return False, None, "No audio stream available"

            # Generate safe filename
            safe_title = self._sanitize_filename(yt.title or "audio")
            filename = f"{safe_title}.{audio_stream.subtype}"

            # Download audio
            self.logger.debug(f"Downloading to: {self.temp_dir}/{filename}")
            file_path = await asyncio.to_thread(
                audio_stream.download,
                output_path=self.temp_dir,
                filename=filename
            )

            # Complete progress tracking
            progress_tracker.complete(f"Download completed: {filename}")

            # Ensure file_path is not None
            if not file_path:
                return False, None, "Download failed: No file path returned"

            # Create AudioInfo object
            audio_info = AudioInfo(
                title=yt.title or "Unknown Title",
                duration=yt.length or 0,
                file_path=file_path,
                url=url,
                uploader=yt.author or "Unknown",
                thumbnail_url=yt.thumbnail_url
            )

            self.logger.info(f"Audio download completed: {file_path}")
            return True, audio_info, None

        except PytubeFixError as e:
            error_msg = str(e)
            if self._is_bot_detection_error(error_msg):
                full_error_msg = f"Bot detection error downloading {url}: {e}"
                self.logger.error(full_error_msg)
                self.logger.info("Consider enabling PoToken functionality in configuration to bypass bot detection")
                progress_tracker.fail("Bot detection error - consider enabling PoToken")
                return False, None, "Bot detection error - PoToken configuration may be required"
            else:
                full_error_msg = f"PytubeFixError downloading {url}: {e}"
                self.logger.error(full_error_msg)
                progress_tracker.fail(full_error_msg)
                return False, None, full_error_msg
        except Exception as e:
            error_msg = f"Unexpected error downloading {url}: {e}"
            self.logger.error(error_msg, exc_info=True)
            progress_tracker.fail(error_msg)
            return False, None, error_msg

    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename for safe file system usage.

        Args:
            filename: Original filename

        Returns:
            Sanitized filename
        """
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')

        # Limit length and strip whitespace
        filename = filename.strip()[:100]

        # Ensure filename is not empty
        if not filename:
            filename = "audio"

        return filename

    def cleanup_file(self, file_path: str) -> bool:
        """
        Clean up a downloaded audio file.

        Args:
            file_path: Path to file to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                self.logger.debug(f"Cleaned up file: {file_path}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error cleaning up file {file_path}: {e}")
            return False

    def format_duration(self, seconds: int) -> str:
        """
        Format duration in seconds to MM:SS or HH:MM:SS format.

        Args:
            seconds: Duration in seconds

        Returns:
            Formatted duration string
        """
        if seconds < 3600:  # Less than 1 hour
            minutes, secs = divmod(seconds, 60)
            return f"{minutes:02d}:{secs:02d}"
        else:  # 1 hour or more
            hours, remainder = divmod(seconds, 3600)
            minutes, secs = divmod(remainder, 60)
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
