"""Core music player for SimiluBot."""

import logging
import asyncio
import os
import time
from typing import Optional, Dict, Callable, Any
import discord
from discord.ext import commands

from .youtube_client import YouTubeClient, AudioInfo
from .catbox_client import CatboxClient, CatboxAudioInfo
from .audio_source import UnifiedAudioInfo, AudioSourceType
from .queue_manager import QueueManager, Song
from .voice_manager import VoiceManager
from .seek_manager import SeekManager, SeekResult
from similubot.progress.base import ProgressCallback
from similubot.utils.config_manager import ConfigManager


class MusicPlayer:
    """
    Core music player that orchestrates YouTube downloading, queue management,
    and Discord voice playback.
    """

    def __init__(self, bot: commands.Bot, temp_dir: str = "./temp", config: Optional[ConfigManager] = None):
        """
        Initialize the music player.

        Args:
            bot: Discord bot instance
            temp_dir: Directory for temporary audio files
            config: Configuration manager for PoToken and other settings
        """
        self.logger = logging.getLogger("similubot.music.music_player")
        self.bot = bot
        self.temp_dir = temp_dir
        self.config = config

        # Initialize components with config support
        self.youtube_client = YouTubeClient(temp_dir, config)
        self.catbox_client = CatboxClient(temp_dir)
        self.voice_manager = VoiceManager(bot)
        self.seek_manager = SeekManager()

        # Guild-specific queue managers
        self._queue_managers: Dict[int, QueueManager] = {}

        # Playback state tracking
        self._playback_tasks: Dict[int, asyncio.Task] = {}
        self._current_audio_files: Dict[int, str] = {}

        # Playback timing tracking
        self._playback_start_times: Dict[int, float] = {}
        self._playback_paused_times: Dict[int, float] = {}
        self._total_paused_duration: Dict[int, float] = {}

        # Auto-disconnect inactivity tracking
        self._inactivity_timers: Dict[int, asyncio.Task] = {}
        self._last_activity_times: Dict[int, float] = {}

        self.logger.info("Music player initialized")

    def get_queue_manager(self, guild_id: int) -> QueueManager:
        """
        Get or create a queue manager for a guild.

        Args:
            guild_id: Discord guild ID

        Returns:
            QueueManager instance
        """
        if guild_id not in self._queue_managers:
            self._queue_managers[guild_id] = QueueManager(guild_id)
            self.logger.debug(f"Created queue manager for guild {guild_id}")

        return self._queue_managers[guild_id]

    def detect_audio_source_type(self, url: str) -> Optional[AudioSourceType]:
        """
        Detect the audio source type from a URL.

        Args:
            url: Audio URL to analyze

        Returns:
            AudioSourceType if detected, None if unsupported
        """
        if self.youtube_client.is_youtube_url(url):
            return AudioSourceType.YOUTUBE
        elif self.catbox_client.is_catbox_url(url):
            return AudioSourceType.CATBOX
        else:
            return None

    def is_supported_url(self, url: str) -> bool:
        """
        Check if a URL is supported by any audio client.

        Args:
            url: URL to check

        Returns:
            True if supported, False otherwise
        """
        return self.detect_audio_source_type(url) is not None

    async def add_song_to_queue(
        self,
        url: str,
        requester: discord.Member,
        progress_callback: Optional[ProgressCallback] = None
    ) -> tuple[bool, Optional[int], Optional[str]]:
        """
        Add a song to the queue and start playback if not already playing.

        Args:
            url: Audio URL (YouTube or Catbox)
            requester: User who requested the song
            progress_callback: Optional progress callback

        Returns:
            Tuple of (success, queue_position, error_message)
        """
        guild_id = requester.guild.id

        try:
            # Detect audio source type
            source_type = self.detect_audio_source_type(url)
            if not source_type:
                return False, None, "Unsupported URL format. Please provide a YouTube or Catbox audio file URL."

            # Extract audio info based on source type
            unified_audio_info = None

            if source_type == AudioSourceType.YOUTUBE:
                self.logger.debug(f"Processing YouTube URL: {url}")
                youtube_info = await self.youtube_client.extract_audio_info(url)
                if youtube_info:
                    unified_audio_info = UnifiedAudioInfo.from_youtube_info(youtube_info)

            elif source_type == AudioSourceType.CATBOX:
                self.logger.debug(f"Processing Catbox URL: {url}")
                catbox_info = await self.catbox_client.extract_audio_info(url)
                if catbox_info:
                    unified_audio_info = UnifiedAudioInfo.from_catbox_info(catbox_info)

            if not unified_audio_info:
                return False, None, "Failed to extract audio information from URL"

            # Add to queue
            queue_manager = self.get_queue_manager(guild_id)
            position = await queue_manager.add_song(unified_audio_info, requester)

            self.logger.info(f"Added {source_type.value} song to queue: {unified_audio_info.title} (position {position})")

            # Reset inactivity timer (activity detected)
            self._reset_inactivity_timer(guild_id)

            # Start playback if not already playing
            if not self.voice_manager.is_playing(guild_id):
                await self._start_playback(guild_id, progress_callback)

            return True, position, None

        except Exception as e:
            error_msg = f"Error adding song to queue: {e}"
            self.logger.error(error_msg, exc_info=True)
            return False, None, error_msg

    async def connect_to_user_channel(self, member: discord.Member) -> tuple[bool, Optional[str]]:
        """
        Connect to the voice channel the user is in.

        Args:
            member: Discord member

        Returns:
            Tuple of (success, error_message)
        """
        if not member.voice or not member.voice.channel:
            return False, "You must be in a voice channel to use music commands"

        # Check if it's a voice channel (not stage channel)
        if not isinstance(member.voice.channel, discord.VoiceChannel):
            return False, "Bot can only connect to voice channels, not stage channels"

        voice_client = await self.voice_manager.connect_to_voice_channel(member.voice.channel)
        if not voice_client:
            return False, "Failed to connect to voice channel"

        # Reset inactivity timer when connecting (activity detected)
        guild_id = member.guild.id
        self._reset_inactivity_timer(guild_id)

        return True, None

    async def skip_current_song(self, guild_id: int) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Skip the current song.

        Args:
            guild_id: Discord guild ID

        Returns:
            Tuple of (success, skipped_song_title, error_message)
        """
        try:
            queue_manager = self.get_queue_manager(guild_id)
            current_song = await queue_manager.get_current_song()

            if not current_song:
                return False, None, "No song is currently playing"

            # Stop current playback
            self.voice_manager.stop_audio(guild_id)

            # Clean up current audio file
            await self._cleanup_current_audio(guild_id)

            self.logger.info(f"Skipped song: {current_song.title}")
            return True, current_song.title, None

        except Exception as e:
            error_msg = f"Error skipping song: {e}"
            self.logger.error(error_msg, exc_info=True)
            return False, None, error_msg

    async def stop_playback(self, guild_id: int) -> tuple[bool, Optional[str]]:
        """
        Stop playback and clear the queue.

        Args:
            guild_id: Discord guild ID

        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Stop audio playback
            self.voice_manager.stop_audio(guild_id)

            # Clear queue
            queue_manager = self.get_queue_manager(guild_id)
            cleared_count = await queue_manager.clear_queue()

            # Clean up all guild state (includes timers, audio files, etc.)
            await self._cleanup_guild_state(guild_id)

            # Disconnect from voice
            await self.voice_manager.disconnect_from_guild(guild_id)

            self.logger.info(f"Stopped playback and cleared {cleared_count} songs from queue")
            return True, None

        except Exception as e:
            error_msg = f"Error stopping playback: {e}"
            self.logger.error(error_msg, exc_info=True)
            return False, error_msg

    async def jump_to_position(self, guild_id: int, position: int) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Jump to a specific position in the queue.

        Args:
            guild_id: Discord guild ID
            position: Queue position (1-indexed)

        Returns:
            Tuple of (success, song_title, error_message)
        """
        try:
            queue_manager = self.get_queue_manager(guild_id)

            # Stop current playback
            self.voice_manager.stop_audio(guild_id)

            # Clean up current audio file
            await self._cleanup_current_audio(guild_id)

            # Jump to position
            song = await queue_manager.jump_to_position(position)
            if not song:
                return False, None, f"Invalid queue position: {position}"

            self.logger.info(f"Jumped to position {position}: {song.title}")
            return True, song.title, None

        except Exception as e:
            error_msg = f"Error jumping to position {position}: {e}"
            self.logger.error(error_msg, exc_info=True)
            return False, None, error_msg

    async def get_queue_info(self, guild_id: int) -> Dict[str, Any]:
        """
        Get comprehensive queue information.

        Args:
            guild_id: Discord guild ID

        Returns:
            Dictionary with queue details
        """
        queue_manager = self.get_queue_manager(guild_id)
        queue_info = await queue_manager.get_queue_info()

        # Add voice connection info
        voice_info = self.voice_manager.get_connection_info(guild_id)
        queue_info.update(voice_info)

        return queue_info

    def get_current_playback_position(self, guild_id: int) -> Optional[float]:
        """
        Get the current playback position in seconds.

        Args:
            guild_id: Discord guild ID

        Returns:
            Current position in seconds, or None if not playing
        """
        if guild_id not in self._playback_start_times:
            return None

        start_time = self._playback_start_times[guild_id]
        current_time = time.time()

        # Calculate elapsed time
        elapsed = current_time - start_time

        # Subtract any paused duration
        total_paused = self._total_paused_duration.get(guild_id, 0.0)

        # If currently paused, add the current pause duration
        if guild_id in self._playback_paused_times:
            current_pause_duration = current_time - self._playback_paused_times[guild_id]
            total_paused += current_pause_duration

        return max(0.0, elapsed - total_paused)

    def _start_playback_timing(self, guild_id: int) -> None:
        """
        Start tracking playback timing for a guild.

        Args:
            guild_id: Discord guild ID
        """
        self._playback_start_times[guild_id] = time.time()
        self._total_paused_duration[guild_id] = 0.0

        # Clear any existing pause state
        if guild_id in self._playback_paused_times:
            del self._playback_paused_times[guild_id]

    def _pause_playback_timing(self, guild_id: int) -> None:
        """
        Mark playback as paused for timing calculations.

        Args:
            guild_id: Discord guild ID
        """
        if guild_id in self._playback_start_times and guild_id not in self._playback_paused_times:
            self._playback_paused_times[guild_id] = time.time()

    def _resume_playback_timing(self, guild_id: int) -> None:
        """
        Resume playback timing after a pause.

        Args:
            guild_id: Discord guild ID
        """
        if guild_id in self._playback_paused_times:
            pause_start = self._playback_paused_times[guild_id]
            pause_duration = time.time() - pause_start

            # Add to total paused duration
            self._total_paused_duration[guild_id] = self._total_paused_duration.get(guild_id, 0.0) + pause_duration

            # Remove from paused state
            del self._playback_paused_times[guild_id]

    def _stop_playback_timing(self, guild_id: int) -> None:
        """
        Stop tracking playback timing for a guild.

        Args:
            guild_id: Discord guild ID
        """
        # Clean up timing state
        if guild_id in self._playback_start_times:
            del self._playback_start_times[guild_id]
        if guild_id in self._playback_paused_times:
            del self._playback_paused_times[guild_id]
        if guild_id in self._total_paused_duration:
            del self._total_paused_duration[guild_id]

    async def seek_to_position(self, guild_id: int, time_str: str) -> tuple[bool, Optional[str]]:
        """
        Seek to a specific position in the currently playing song.

        Args:
            guild_id: Discord guild ID
            time_str: Time string (e.g., "1:30", "2:15:45", "+30", "-1:00")

        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Check if music is currently playing
            if not self.voice_manager.is_connected(guild_id):
                return False, "No active music playback"

            # Get current song
            queue_manager = self.get_queue_manager(guild_id)
            current_song = await queue_manager.get_current_song()
            if not current_song:
                return False, "No song currently playing"

            # Parse seek time
            seek_result = self.seek_manager.parse_seek_time(time_str)
            if not seek_result.success or seek_result.target_position is None:
                return False, seek_result.error_message or "Failed to parse seek time"

            # Get current position and song duration
            current_position = self.get_current_playback_position(guild_id) or 0.0
            song_duration = float(current_song.duration)

            # Validate seek position
            is_relative = self.seek_manager.is_relative_seek(time_str)
            validation_result = self.seek_manager.validate_seek_position(
                seek_result.target_position,
                current_position,
                song_duration,
                is_relative
            )

            if not validation_result.success or validation_result.target_position is None:
                return False, validation_result.error_message or "Invalid seek position"

            target_position = validation_result.target_position

            # Perform the seek operation
            success = await self._perform_seek(guild_id, target_position, current_song)
            if not success:
                return False, "Failed to seek to position"

            self.logger.info(f"Successfully sought to {self.seek_manager.format_time(target_position)} in guild {guild_id}")
            return True, None

        except Exception as e:
            error_msg = f"Error seeking to position: {e}"
            self.logger.error(error_msg, exc_info=True)
            return False, error_msg

    async def _perform_seek(self, guild_id: int, target_seconds: float, song: Song) -> bool:
        """
        Perform the actual seek operation by recreating the audio source.

        Args:
            guild_id: Discord guild ID
            target_seconds: Target position in seconds
            song: Current song object

        Returns:
            True if seek was successful, False otherwise
        """
        try:
            # Get the audio file path
            audio_file_path = self._current_audio_files.get(guild_id)
            if not audio_file_path:
                self.logger.error(f"No audio file path available for seek in guild {guild_id}")
                return False

            # Stop current playback
            self.voice_manager.stop_audio(guild_id)

            # Create new audio source with seek position
            seek_options = f'-ss {target_seconds} -vn'
            audio_source = discord.FFmpegPCMAudio(
                audio_file_path,
                options=seek_options
            )

            # Update timing tracking for the new position
            self._update_timing_after_seek(guild_id, target_seconds)

            # Start playback from new position
            playback_finished = asyncio.Event()

            def after_playback(error):
                if error:
                    self.logger.error(f"Playback error after seek: {error}")
                playback_finished.set()

            success = await self.voice_manager.play_audio(
                guild_id, audio_source, after_playback
            )

            if success:
                self.logger.debug(f"Seek successful: started playback from {target_seconds}s")
            else:
                self.logger.error(f"Failed to start playback after seek in guild {guild_id}")

            return success

        except Exception as e:
            self.logger.error(f"Error performing seek operation: {e}", exc_info=True)
            return False

    def _update_timing_after_seek(self, guild_id: int, target_seconds: float) -> None:
        """
        Update playback timing tracking after a seek operation.

        Args:
            guild_id: Discord guild ID
            target_seconds: Position that was seeked to
        """
        current_time = time.time()

        # Adjust the start time to account for the seek position
        # New start time = current time - target position
        self._playback_start_times[guild_id] = current_time - target_seconds

        # Reset paused duration tracking
        self._total_paused_duration[guild_id] = 0.0

        # Clear any existing pause state
        if guild_id in self._playback_paused_times:
            del self._playback_paused_times[guild_id]

        self.logger.debug(f"Updated timing after seek: new start time accounts for {target_seconds}s offset")

    def _get_auto_disconnect_timeout(self) -> int:
        """
        Get the auto-disconnect timeout from configuration.

        Returns:
            Timeout in seconds (default: 300 = 5 minutes)
        """
        if self.config:
            return self.config.get_music_auto_disconnect_timeout()
        return 300  # Default 5 minutes

    def _reset_inactivity_timer(self, guild_id: int) -> None:
        """
        Reset the inactivity timer for a guild (activity detected).

        Args:
            guild_id: Discord guild ID
        """
        # Cancel existing timer if any
        if guild_id in self._inactivity_timers:
            self._inactivity_timers[guild_id].cancel()
            del self._inactivity_timers[guild_id]

        # Update last activity time
        self._last_activity_times[guild_id] = time.time()

        self.logger.debug(f"Reset inactivity timer for guild {guild_id}")

    def _start_inactivity_timer(self, guild_id: int) -> None:
        """
        Start the inactivity timer for a guild (no active playback).

        Args:
            guild_id: Discord guild ID
        """
        # Cancel existing timer if any
        if guild_id in self._inactivity_timers:
            self._inactivity_timers[guild_id].cancel()

        # Get timeout from config
        timeout_seconds = self._get_auto_disconnect_timeout()

        # Create new inactivity timer task
        timer_task = asyncio.create_task(
            self._inactivity_timer_task(guild_id, timeout_seconds)
        )
        self._inactivity_timers[guild_id] = timer_task

        self.logger.debug(f"Started inactivity timer for guild {guild_id} ({timeout_seconds}s)")

    async def _inactivity_timer_task(self, guild_id: int, timeout_seconds: int) -> None:
        """
        Inactivity timer task that disconnects after timeout.

        Args:
            guild_id: Discord guild ID
            timeout_seconds: Timeout duration in seconds
        """
        try:
            await asyncio.sleep(timeout_seconds)

            # Check if still connected and inactive
            if (self.voice_manager.is_connected(guild_id) and
                not self.voice_manager.is_playing(guild_id)):

                self.logger.info(f"Auto-disconnecting from guild {guild_id} after {timeout_seconds}s of inactivity")

                # Clean up any remaining state
                await self._cleanup_guild_state(guild_id)

                # Disconnect from voice channel
                await self.voice_manager.disconnect_from_guild(guild_id)

        except asyncio.CancelledError:
            self.logger.debug(f"Inactivity timer cancelled for guild {guild_id}")
        except Exception as e:
            self.logger.error(f"Error in inactivity timer for guild {guild_id}: {e}", exc_info=True)
        finally:
            # Clean up timer reference
            if guild_id in self._inactivity_timers:
                del self._inactivity_timers[guild_id]

    def _stop_inactivity_timer(self, guild_id: int) -> None:
        """
        Stop the inactivity timer for a guild.

        Args:
            guild_id: Discord guild ID
        """
        if guild_id in self._inactivity_timers:
            self._inactivity_timers[guild_id].cancel()
            del self._inactivity_timers[guild_id]
            self.logger.debug(f"Stopped inactivity timer for guild {guild_id}")

    async def _cleanup_guild_state(self, guild_id: int) -> None:
        """
        Clean up all state for a guild (playback, timers, etc.).

        Args:
            guild_id: Discord guild ID
        """
        # Cancel playback task
        if guild_id in self._playback_tasks:
            self._playback_tasks[guild_id].cancel()
            del self._playback_tasks[guild_id]

        # Clean up audio file
        await self._cleanup_current_audio(guild_id)

        # Stop timing tracking
        self._stop_playback_timing(guild_id)

        # Stop inactivity timer
        self._stop_inactivity_timer(guild_id)

        # Clear last activity time
        if guild_id in self._last_activity_times:
            del self._last_activity_times[guild_id]

        self.logger.debug(f"Cleaned up all state for guild {guild_id}")

    async def _start_playback(
        self,
        guild_id: int,
        progress_callback: Optional[ProgressCallback] = None
    ) -> None:
        """
        Start playback for a guild.

        Args:
            guild_id: Discord guild ID
            progress_callback: Optional progress callback
        """
        if guild_id in self._playback_tasks:
            return  # Already playing

        # Reset inactivity timer (activity detected)
        self._reset_inactivity_timer(guild_id)

        # Create playback task
        task = asyncio.create_task(self._playback_loop(guild_id, progress_callback))
        self._playback_tasks[guild_id] = task

    async def _playback_loop(
        self,
        guild_id: int,
        progress_callback: Optional[ProgressCallback] = None
    ) -> None:
        """
        Main playback loop for a guild.

        Args:
            guild_id: Discord guild ID
            progress_callback: Optional progress callback
        """
        queue_manager = self.get_queue_manager(guild_id)

        try:
            while True:
                # Get next song
                song = await queue_manager.get_next_song()
                if not song:
                    self.logger.debug(f"No more songs in queue for guild {guild_id}")
                    # Start inactivity timer when queue is empty
                    self._start_inactivity_timer(guild_id)
                    break

                # Handle audio based on source type
                audio_file_path = None

                if hasattr(song.audio_info, 'source_type'):
                    # New UnifiedAudioInfo format
                    if song.audio_info.is_youtube():
                        # Download YouTube audio
                        success, youtube_audio_info, error = await self.youtube_client.download_audio(
                            song.url, progress_callback
                        )
                        if not success or not youtube_audio_info:
                            self.logger.error(f"Failed to download YouTube audio for {song.title}: {error}")
                            continue
                        audio_file_path = youtube_audio_info.file_path

                    elif song.audio_info.is_catbox():
                        # Validate Catbox audio file
                        success, catbox_audio_info, error = await self.catbox_client.validate_audio_file(
                            song.url, progress_callback
                        )
                        if not success or not catbox_audio_info:
                            self.logger.error(f"Failed to validate Catbox audio for {song.title}: {error}")
                            continue
                        audio_file_path = catbox_audio_info.file_path  # This is the URL for streaming

                else:
                    # Legacy AudioInfo format (YouTube only)
                    success, youtube_audio_info, error = await self.youtube_client.download_audio(
                        song.url, progress_callback
                    )
                    if not success or not youtube_audio_info:
                        self.logger.error(f"Failed to download audio for {song.title}: {error}")
                        continue
                    audio_file_path = youtube_audio_info.file_path

                if not audio_file_path:
                    self.logger.error(f"No audio file path available for {song.title}")
                    continue

                # Store current audio file path (for cleanup)
                self._current_audio_files[guild_id] = audio_file_path

                # Create audio source (works for both local files and URLs)
                audio_source = discord.FFmpegPCMAudio(
                    audio_file_path,
                    options='-vn'  # No video
                )

                # Play audio
                playback_finished = asyncio.Event()

                def after_playback(error):
                    if error:
                        self.logger.error(f"Playback error: {error}")
                    playback_finished.set()

                success = await self.voice_manager.play_audio(
                    guild_id, audio_source, after_playback
                )

                if not success:
                    self.logger.error(f"Failed to start playback for {song.title}")
                    await self._cleanup_current_audio(guild_id)
                    continue

                # Start timing tracking
                self._start_playback_timing(guild_id)

                self.logger.info(f"Now playing: {song.title}")

                # Wait for playback to finish
                await playback_finished.wait()

                # Stop timing tracking
                self._stop_playback_timing(guild_id)

                # Clean up audio file
                await self._cleanup_current_audio(guild_id)

        except asyncio.CancelledError:
            self.logger.debug(f"Playback loop cancelled for guild {guild_id}")
        except Exception as e:
            self.logger.error(f"Error in playback loop for guild {guild_id}: {e}", exc_info=True)
        finally:
            # Clean up
            if guild_id in self._playback_tasks:
                del self._playback_tasks[guild_id]
            await self._cleanup_current_audio(guild_id)

    async def _cleanup_current_audio(self, guild_id: int) -> None:
        """
        Clean up the current audio file for a guild.

        Args:
            guild_id: Discord guild ID
        """
        if guild_id in self._current_audio_files:
            file_path = self._current_audio_files[guild_id]

            # Only clean up local files, not URLs
            if file_path and not file_path.startswith('http'):
                self.youtube_client.cleanup_file(file_path)

            del self._current_audio_files[guild_id]

    async def cleanup_all(self) -> None:
        """Clean up all resources."""
        self.logger.info("Cleaning up music player resources")

        # Cancel all playback tasks
        for task in self._playback_tasks.values():
            task.cancel()

        # Cancel all inactivity timers
        for timer_task in self._inactivity_timers.values():
            timer_task.cancel()

        # Wait for tasks to complete
        all_tasks = list(self._playback_tasks.values()) + list(self._inactivity_timers.values())
        if all_tasks:
            await asyncio.gather(*all_tasks, return_exceptions=True)

        # Clean up audio files
        for guild_id in list(self._current_audio_files.keys()):
            await self._cleanup_current_audio(guild_id)

        # Clean up voice connections
        await self.voice_manager.cleanup_all_connections()

        # Clean up HTTP sessions
        await self.catbox_client.cleanup()

        # Clear state
        self._playback_tasks.clear()
        self._current_audio_files.clear()
        self._queue_managers.clear()

        # Clear timing state
        self._playback_start_times.clear()
        self._playback_paused_times.clear()
        self._total_paused_duration.clear()

        # Clear inactivity tracking state
        self._inactivity_timers.clear()
        self._last_activity_times.clear()
