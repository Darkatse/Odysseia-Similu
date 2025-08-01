"""Music queue management for SimiluBot."""

import logging
import asyncio
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
import discord
from .youtube_client import AudioInfo
from .audio_source import UnifiedAudioInfo
from typing import Union


@dataclass
class Song:
    """Represents a song in the music queue."""
    audio_info: Union[AudioInfo, UnifiedAudioInfo]
    requester: discord.Member
    added_at: datetime = field(default_factory=datetime.now)

    @property
    def title(self) -> str:
        """Get song title."""
        return self.audio_info.title

    @property
    def duration(self) -> int:
        """Get song duration in seconds."""
        return self.audio_info.duration

    @property
    def url(self) -> str:
        """Get song URL."""
        return self.audio_info.url

    @property
    def uploader(self) -> str:
        """Get song uploader."""
        return self.audio_info.uploader


class QueueManager:
    """
    Manages the music queue for a Discord guild.
    
    Provides thread-safe queue operations with position tracking,
    song metadata management, and queue persistence.
    """

    def __init__(self, guild_id: int):
        """
        Initialize the queue manager.
        
        Args:
            guild_id: Discord guild ID
        """
        self.logger = logging.getLogger("similubot.music.queue_manager")
        self.guild_id = guild_id
        self._queue: List[Song] = []
        self._current_song: Optional[Song] = None
        self._lock = asyncio.Lock()
        
        self.logger.debug(f"Queue manager initialized for guild {guild_id}")

    async def add_song(self, audio_info: Union[AudioInfo, UnifiedAudioInfo], requester: discord.Member) -> int:
        """
        Add a song to the queue.
        
        Args:
            audio_info: Audio information
            requester: User who requested the song
            
        Returns:
            Position in queue (1-indexed)
        """
        async with self._lock:
            song = Song(audio_info=audio_info, requester=requester)
            self._queue.append(song)
            position = len(self._queue)
            
            self.logger.info(f"Added song to queue: {song.title} (position {position})")
            return position

    async def get_next_song(self) -> Optional[Song]:
        """
        Get the next song from the queue.
        
        Returns:
            Next song or None if queue is empty
        """
        async with self._lock:
            if not self._queue:
                return None
            
            song = self._queue.pop(0)
            self._current_song = song
            
            self.logger.info(f"Retrieved next song: {song.title}")
            return song

    async def skip_current_song(self) -> Optional[Song]:
        """
        Skip the current song and get the next one.
        
        Returns:
            Next song or None if queue is empty
        """
        async with self._lock:
            if self._current_song:
                self.logger.info(f"Skipping current song: {self._current_song.title}")
                self._current_song = None
            
            return await self.get_next_song()

    async def jump_to_position(self, position: int) -> Optional[Song]:
        """
        Jump to a specific position in the queue.
        
        Args:
            position: Queue position (1-indexed)
            
        Returns:
            Song at position or None if invalid position
        """
        async with self._lock:
            if position < 1 or position > len(self._queue):
                return None
            
            # Remove songs before the target position
            songs_to_remove = position - 1
            for _ in range(songs_to_remove):
                if self._queue:
                    removed_song = self._queue.pop(0)
                    self.logger.debug(f"Removed song during jump: {removed_song.title}")
            
            # Get the target song
            if self._queue:
                song = self._queue.pop(0)
                self._current_song = song
                self.logger.info(f"Jumped to position {position}: {song.title}")
                return song
            
            return None

    async def clear_queue(self) -> int:
        """
        Clear the entire queue.
        
        Returns:
            Number of songs removed
        """
        async with self._lock:
            count = len(self._queue)
            self._queue.clear()
            self._current_song = None
            
            self.logger.info(f"Cleared queue: {count} songs removed")
            return count

    async def get_queue_info(self) -> Dict[str, Any]:
        """
        Get comprehensive queue information.
        
        Returns:
            Dictionary with queue details
        """
        async with self._lock:
            total_duration = sum(song.duration for song in self._queue)
            
            return {
                "current_song": self._current_song,
                "queue": self._queue.copy(),
                "queue_length": len(self._queue),
                "total_duration": total_duration,
                "is_empty": len(self._queue) == 0
            }

    async def get_current_song(self) -> Optional[Song]:
        """
        Get the currently playing song.
        
        Returns:
            Current song or None if nothing is playing
        """
        async with self._lock:
            return self._current_song

    async def remove_song_at_position(self, position: int) -> Optional[Song]:
        """
        Remove a song at a specific position.
        
        Args:
            position: Queue position (1-indexed)
            
        Returns:
            Removed song or None if invalid position
        """
        async with self._lock:
            if position < 1 or position > len(self._queue):
                return None
            
            removed_song = self._queue.pop(position - 1)
            self.logger.info(f"Removed song at position {position}: {removed_song.title}")
            return removed_song

    async def get_queue_display(self, max_songs: int = 10) -> List[Dict[str, Any]]:
        """
        Get formatted queue information for display.
        
        Args:
            max_songs: Maximum number of songs to include
            
        Returns:
            List of song display information
        """
        async with self._lock:
            display_songs = []
            
            for i, song in enumerate(self._queue[:max_songs], 1):
                display_songs.append({
                    "position": i,
                    "title": song.title,
                    "duration": self._format_duration(song.duration),
                    "uploader": song.uploader,
                    "requester": song.requester.display_name,
                    "url": song.url
                })
            
            return display_songs

    def _format_duration(self, seconds: int) -> str:
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

    async def get_queue_summary(self) -> str:
        """
        Get a brief queue summary.
        
        Returns:
            Summary string
        """
        async with self._lock:
            if not self._queue:
                return "Queue is empty"
            
            total_duration = sum(song.duration for song in self._queue)
            duration_str = self._format_duration(total_duration)
            
            return f"{len(self._queue)} songs in queue ({duration_str} total)"
