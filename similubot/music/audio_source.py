"""Unified audio source interface for SimiluBot music system."""

from enum import Enum
from typing import Union, Optional
from dataclasses import dataclass

from .youtube_client import AudioInfo
from .catbox_client import CatboxAudioInfo


class AudioSourceType(Enum):
    """Enumeration of supported audio source types."""
    YOUTUBE = "youtube"
    CATBOX = "catbox"


@dataclass
class UnifiedAudioInfo:
    """
    Unified audio information that works with different source types.
    
    This class provides a common interface for audio information
    regardless of whether it comes from YouTube or Catbox.
    """
    title: str
    duration: int  # Duration in seconds
    file_path: str  # Local file path or streaming URL
    url: str  # Original URL
    uploader: str
    source_type: AudioSourceType
    thumbnail_url: Optional[str] = None
    
    # Catbox-specific fields
    file_size: Optional[int] = None  # File size in bytes
    file_format: Optional[str] = None  # Audio format (mp3, wav, etc.)

    @classmethod
    def from_youtube_info(cls, youtube_info: AudioInfo) -> 'UnifiedAudioInfo':
        """
        Create UnifiedAudioInfo from YouTube AudioInfo.

        Args:
            youtube_info: YouTube AudioInfo object

        Returns:
            UnifiedAudioInfo instance
        """
        return cls(
            title=youtube_info.title,
            duration=youtube_info.duration,
            file_path=youtube_info.file_path,
            url=youtube_info.url,
            uploader=youtube_info.uploader,
            source_type=AudioSourceType.YOUTUBE,
            thumbnail_url=youtube_info.thumbnail_url,
            file_size=None,
            file_format=None
        )

    @classmethod
    def from_catbox_info(cls, catbox_info: CatboxAudioInfo) -> 'UnifiedAudioInfo':
        """
        Create UnifiedAudioInfo from Catbox CatboxAudioInfo.

        Args:
            catbox_info: Catbox CatboxAudioInfo object

        Returns:
            UnifiedAudioInfo instance
        """
        return cls(
            title=catbox_info.title,
            duration=catbox_info.duration,
            file_path=catbox_info.file_path,
            url=catbox_info.url,
            uploader=catbox_info.uploader,
            source_type=AudioSourceType.CATBOX,
            thumbnail_url=catbox_info.thumbnail_url,
            file_size=catbox_info.file_size,
            file_format=catbox_info.file_format
        )

    def is_youtube(self) -> bool:
        """Check if this is a YouTube audio source."""
        return self.source_type == AudioSourceType.YOUTUBE

    def is_catbox(self) -> bool:
        """Check if this is a Catbox audio source."""
        return self.source_type == AudioSourceType.CATBOX

    def is_streaming(self) -> bool:
        """Check if this audio source uses streaming (vs local file)."""
        return self.is_catbox()

    def get_display_info(self) -> dict:
        """
        Get formatted display information for Discord embeds.

        Returns:
            Dictionary with formatted display information
        """
        info = {
            'title': self.title,
            'uploader': self.uploader,
            'duration': self.format_duration(self.duration),
            'source': self.source_type.value.title(),
            'url': self.url
        }

        if self.is_catbox() and self.file_size:
            info['file_size'] = self.format_file_size(self.file_size)
        
        if self.is_catbox() and self.file_format:
            info['format'] = self.file_format.upper()

        return info

    def format_duration(self, seconds: int) -> str:
        """
        Format duration in seconds to MM:SS or HH:MM:SS format.

        Args:
            seconds: Duration in seconds

        Returns:
            Formatted duration string
        """
        if seconds <= 0:
            return "Unknown"
        
        if seconds < 3600:  # Less than 1 hour
            minutes, secs = divmod(seconds, 60)
            return f"{minutes:02d}:{secs:02d}"
        else:  # 1 hour or more
            hours, remainder = divmod(seconds, 3600)
            minutes, secs = divmod(remainder, 60)
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def format_file_size(self, size_bytes: int) -> str:
        """
        Format file size in bytes to human-readable format.

        Args:
            size_bytes: File size in bytes

        Returns:
            Formatted file size string
        """
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


# Type alias for backward compatibility
AudioSourceInfo = Union[AudioInfo, CatboxAudioInfo, UnifiedAudioInfo]
