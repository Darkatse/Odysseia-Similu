"""
Catbox audio file client for SimiluBot.

This client includes User-Agent spoofing and browser-like headers to prevent
HTTP errors like "Server disconnected" that may occur when making requests
to Catbox servers. The client mimics a real Chrome browser to avoid anti-bot
detection measures.
"""

import logging
import re
import asyncio
import aiohttp
import time
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass
from urllib.parse import urlparse
import os

from similubot.progress.base import ProgressTracker, ProgressInfo, ProgressStatus, ProgressCallback


class CatboxProgressTracker(ProgressTracker):
    """
    Progress tracker for Catbox audio file processing.

    Handles progress updates for Catbox file validation and metadata extraction.
    """

    def __init__(self):
        """Initialize the Catbox progress tracker."""
        super().__init__("Catbox Audio Processing")
        self.logger = logging.getLogger("similubot.progress.catbox")

    def parse_output(self, output_line: str) -> bool:
        """
        Parse output line (not used for Catbox processing).

        Args:
            output_line: Output line to parse

        Returns:
            False (Catbox progress comes from direct updates, not output parsing)
        """
        return False


@dataclass
class CatboxAudioInfo:
    """Information about a Catbox audio file."""
    title: str
    duration: int  # Duration in seconds (estimated or 0 if unknown)
    file_path: str  # URL for streaming
    url: str
    uploader: str
    file_size: Optional[int] = None  # File size in bytes
    file_format: Optional[str] = None  # Audio format (mp3, wav, etc.)
    thumbnail_url: Optional[str] = None


class CatboxClient:
    """
    Catbox audio file client for SimiluBot.

    Handles validation, metadata extraction, and streaming preparation
    for audio files hosted on Catbox.
    """

    # Supported audio formats
    SUPPORTED_FORMATS = {
        'mp3', 'wav', 'ogg', 'm4a', 'flac', 'aac', 'opus', 'wma'
    }

    # User-Agent string to mimic a real browser and avoid anti-bot measures
    # Using Chrome on Windows 10 - one of the most common browser/OS combinations
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    def __init__(self, temp_dir: str = "./temp"):
        """
        Initialize the Catbox client.

        Args:
            temp_dir: Directory for temporary files (not used for streaming)
        """
        self.logger = logging.getLogger("similubot.music.catbox_client")
        self.temp_dir = temp_dir

        # HTTP session for requests
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """
        Get or create HTTP session with browser-like headers.

        Returns:
            aiohttp ClientSession configured with realistic headers
        """
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30, connect=10)

            # Headers to make requests appear more browser-like
            headers = {
                'User-Agent': self.USER_AGENT,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',  # Do Not Track
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Cache-Control': 'max-age=0'
            }

            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers=headers,
                connector=aiohttp.TCPConnector(
                    limit=10,  # Connection pool limit
                    limit_per_host=5,  # Per-host connection limit
                    ttl_dns_cache=300,  # DNS cache TTL
                    use_dns_cache=True,
                )
            )

            self.logger.debug(f"Created HTTP session with User-Agent: {self.USER_AGENT}")
        return self._session

    def _get_request_headers(self, url: str) -> Dict[str, str]:
        """
        Get additional headers for specific requests to make them more browser-like.

        Args:
            url: The URL being requested

        Returns:
            Dictionary of additional headers
        """
        return {
            'Referer': 'https://catbox.moe/',  # Make it look like we came from the main site
            'Origin': 'https://catbox.moe',
            'Sec-Fetch-User': '?1',
            'Pragma': 'no-cache',
        }

    async def _make_head_request_with_retry(self, url: str, max_retries: int = 2) -> Optional[aiohttp.ClientResponse]:
        """
        Make a HEAD request with retry logic for better reliability.

        Args:
            url: URL to request
            max_retries: Maximum number of retry attempts

        Returns:
            Response object if successful, None if all retries failed
        """
        session = await self._get_session()
        additional_headers = self._get_request_headers(url)

        for attempt in range(max_retries + 1):
            try:
                self.logger.debug(f"HEAD request attempt {attempt + 1}/{max_retries + 1} to {url}")

                async with session.head(url, headers=additional_headers) as response:
                    self.logger.debug(f"Response: HTTP {response.status}")

                    # Return response for any status - let caller handle status codes
                    return response

            except aiohttp.ClientError as e:
                self.logger.warning(f"Request attempt {attempt + 1} failed: {e}")
                if attempt < max_retries:
                    # Wait a bit before retrying (exponential backoff)
                    wait_time = 2 ** attempt
                    self.logger.debug(f"Waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)
                else:
                    self.logger.error(f"All {max_retries + 1} attempts failed for {url}")

        return None

    def is_catbox_url(self, url: str) -> bool:
        """
        Check if a URL is a valid Catbox audio file URL.

        Args:
            url: URL to validate

        Returns:
            True if valid Catbox audio URL, False otherwise
        """
        try:
            # Parse URL
            parsed = urlparse(url)

            # Check domain
            if parsed.netloc.lower() != 'files.catbox.moe':
                return False

            # Check if it has a file extension
            path = parsed.path.lower()
            if not path or '.' not in path:
                return False

            # Extract file extension
            file_extension = path.split('.')[-1]

            # Check if it's a supported audio format
            return file_extension in self.SUPPORTED_FORMATS

        except Exception as e:
            self.logger.debug(f"Error parsing URL {url}: {e}")
            return False

    def _extract_filename_from_url(self, url: str) -> str:
        """
        Extract filename from Catbox URL.

        Args:
            url: Catbox URL

        Returns:
            Filename without extension
        """
        try:
            parsed = urlparse(url)
            filename = os.path.basename(parsed.path)

            # Remove extension for title
            if '.' in filename:
                return "Catbox - " + filename.rsplit('.', 1)[0]
            return "Catbox - " + filename
        except Exception:
            return "Unknown Audio File"

    def _get_file_format_from_url(self, url: str) -> Optional[str]:
        """
        Extract file format from Catbox URL.

        Args:
            url: Catbox URL

        Returns:
            File format (extension) or None
        """
        try:
            parsed = urlparse(url)
            path = parsed.path.lower()
            if '.' in path:
                return path.split('.')[-1]
        except Exception:
            pass
        return None

    async def extract_audio_info(self, url: str) -> Optional[CatboxAudioInfo]:
        """
        Extract audio information from a Catbox URL.

        Args:
            url: Catbox URL

        Returns:
            CatboxAudioInfo object if successful, None otherwise
        """
        if not self.is_catbox_url(url):
            self.logger.error(f"Invalid Catbox URL: {url}")
            return None

        try:
            self.logger.debug(f"Extracting info from Catbox URL: {url}")

            # Use retry logic for better reliability
            response = await self._make_head_request_with_retry(url)
            if not response:
                self.logger.error(f"Failed to get response from Catbox URL after retries: {url}")
                return None

            self.logger.debug(f"Response status: {response.status}, headers: {dict(response.headers)}")

            if response.status != 200:
                self.logger.error(f"Catbox file not accessible: {url} (HTTP {response.status})")
                if response.status == 403:
                    self.logger.warning("HTTP 403 - Possible anti-bot detection despite User-Agent spoofing")
                elif response.status == 429:
                    self.logger.warning("HTTP 429 - Rate limited by Catbox servers")
                return None

            # Extract metadata from headers
            content_length = response.headers.get('content-length')
            file_size = int(content_length) if content_length else None

            # Extract filename and format
            filename = self._extract_filename_from_url(url)
            file_format = self._get_file_format_from_url(url)

            return CatboxAudioInfo(
                title=filename,
                duration=0,  # Cannot determine duration without downloading
                file_path=url,  # Use URL directly for streaming
                url=url,
                uploader="Catbox",
                file_size=file_size,
                file_format=file_format,
                thumbnail_url=None
            )

        except aiohttp.ClientError as e:
            self.logger.error(f"Network error accessing Catbox URL {url}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error extracting info from {url}: {e}", exc_info=True)
            return None

    async def validate_audio_file(
        self,
        url: str,
        progress_callback: Optional[ProgressCallback] = None
    ) -> Tuple[bool, Optional[CatboxAudioInfo], Optional[str]]:
        """
        Validate a Catbox audio file URL and extract metadata.

        Args:
            url: Catbox URL
            progress_callback: Optional progress callback function

        Returns:
            Tuple of (success, CatboxAudioInfo, error_message)
        """
        if not self.is_catbox_url(url):
            return False, None, f"Invalid Catbox URL: {url}"

        # Initialize progress tracker
        progress_tracker = CatboxProgressTracker()
        if progress_callback:
            progress_tracker.add_callback(progress_callback)

        try:
            self.logger.info(f"Validating Catbox audio file: {url}")
            
            # Start progress tracking
            progress_tracker.start()
            progress_tracker.update(
                percentage=25.0,
                message="Validating Catbox URL..."
            )

            # Extract audio info
            audio_info = await self.extract_audio_info(url)
            if not audio_info:
                progress_tracker.fail("Failed to extract audio information")
                return False, None, "Failed to extract audio information from Catbox URL"

            progress_tracker.update(
                percentage=75.0,
                message="Checking file accessibility..."
            )

            # Verify file is accessible with browser-like headers and retry logic
            self.logger.debug(f"Validating Catbox file accessibility: {url}")
            response = await self._make_head_request_with_retry(url)
            if not response:
                error_msg = "Failed to connect to Catbox server after retries"
                progress_tracker.fail(error_msg)
                return False, None, error_msg

            self.logger.debug(f"Validation response status: {response.status}")

            if response.status != 200:
                error_msg = f"Catbox file not accessible (HTTP {response.status})"
                if response.status == 403:
                    error_msg += " - Possible anti-bot detection"
                    self.logger.warning("HTTP 403 during validation - anti-bot measures may be active")
                elif response.status == 429:
                    error_msg += " - Rate limited"
                    self.logger.warning("HTTP 429 during validation - rate limited by server")
                elif response.status == 404:
                    error_msg += " - File not found"

                progress_tracker.fail(error_msg)
                return False, None, error_msg

            # Complete progress tracking
            file_size_mb = audio_info.file_size / (1024 * 1024) if audio_info.file_size else 0
            progress_tracker.complete(
                f"Catbox audio file validated: {audio_info.title} ({file_size_mb:.1f} MB)"
            )

            self.logger.info(f"Catbox audio file validated: {audio_info.title}")
            return True, audio_info, None

        except Exception as e:
            error_msg = f"Error validating Catbox URL {url}: {e}"
            self.logger.error(error_msg, exc_info=True)
            progress_tracker.fail(error_msg)
            return False, None, error_msg

    def format_file_size(self, size_bytes: Optional[int]) -> str:
        """
        Format file size in bytes to human-readable format.

        Args:
            size_bytes: File size in bytes

        Returns:
            Formatted file size string
        """
        if not size_bytes:
            return "Unknown size"
        
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

    async def cleanup(self) -> None:
        """Clean up HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self.logger.debug("Catbox client session closed")
