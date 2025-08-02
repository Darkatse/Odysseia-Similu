"""Music playback progress tracking for real-time Discord updates."""

import asyncio
import logging
import time
from typing import Optional, Dict, Any, List
import discord

from .base import ProgressTracker, ProgressInfo, ProgressStatus, ProgressCallback
from similubot.lyrics import LyricsManager, LyricLine


class MusicProgressTracker(ProgressTracker):
    """
    Progress tracker for music playback operations.

    Extends the base ProgressTracker to provide music-specific progress tracking
    with timing calculations and playback state management.
    """

    def __init__(self, operation_name: str = "Music Playback"):
        """
        Initialize the music progress tracker.

        Args:
            operation_name: Name of the operation being tracked
        """
        super().__init__(operation_name)
        self.logger = logging.getLogger("similubot.progress.music")

        # Music-specific timing tracking
        self._playback_start_time: Optional[float] = None
        self._total_paused_duration: float = 0.0
        self._pause_start_time: Optional[float] = None
        self._song_duration: Optional[float] = None

    def parse_output(self, output_line: str) -> bool:
        """
        Parse output for progress information.

        This method is required by the abstract base class but not used
        for music playback tracking since we track timing directly.

        Args:
            output_line: Output line to parse (unused for music tracking)

        Returns:
            False (music progress tracking doesn't use output parsing)
        """
        # Music progress tracking doesn't use output parsing
        # Progress is tracked through timing and playback state
        return False

    def start_playback(self, song_duration: float) -> None:
        """
        Start tracking music playback progress.

        Args:
            song_duration: Total duration of the song in seconds
        """
        self._playback_start_time = time.time()
        self._total_paused_duration = 0.0
        self._pause_start_time = None
        self._song_duration = song_duration

        # Notify callbacks of playback start
        progress = ProgressInfo(
            operation=self.operation_name,
            status=ProgressStatus.IN_PROGRESS,
            percentage=0.0,
            message="音乐播放已开始",
            details={
                "song_duration": song_duration,
                "current_position": 0.0,
                "playback_state": "playing"
            }
        )
        self._notify_callbacks(progress)

    def pause_playback(self) -> None:
        """Mark playback as paused."""
        if self._playback_start_time and not self._pause_start_time:
            self._pause_start_time = time.time()

            current_position = self.get_current_position()
            percentage = (current_position / self._song_duration * 100) if self._song_duration else 0.0

            progress = ProgressInfo(
                operation=self.operation_name,
                status=ProgressStatus.IN_PROGRESS,
                percentage=percentage,
                message="音乐播放已暂停",
                details={
                    "song_duration": self._song_duration,
                    "current_position": current_position,
                    "playback_state": "paused"
                }
            )
            self._notify_callbacks(progress)

    def resume_playback(self) -> None:
        """Resume playback after a pause."""
        if self._pause_start_time:
            pause_duration = time.time() - self._pause_start_time
            self._total_paused_duration += pause_duration
            self._pause_start_time = None

            current_position = self.get_current_position()
            percentage = (current_position / self._song_duration * 100) if self._song_duration else 0.0

            progress = ProgressInfo(
                operation=self.operation_name,
                status=ProgressStatus.IN_PROGRESS,
                percentage=percentage,
                message="音乐播放已恢复",
                details={
                    "song_duration": self._song_duration,
                    "current_position": current_position,
                    "playback_state": "playing"
                }
            )
            self._notify_callbacks(progress)

    def update_playback_position(self) -> None:
        """Update the current playback position and notify callbacks."""
        if not self._playback_start_time or not self._song_duration:
            return

        current_position = self.get_current_position()
        percentage = min((current_position / self._song_duration * 100), 100.0)

        # Determine playback state
        playback_state = "paused" if self._pause_start_time else "playing"

        progress = ProgressInfo(
            operation=self.operation_name,
            status=ProgressStatus.IN_PROGRESS,
            percentage=percentage,
            message=f"播放中: {self.format_time(current_position)}/{self.format_time(self._song_duration)}",
            details={
                "song_duration": self._song_duration,
                "current_position": current_position,
                "playback_state": playback_state
            }
        )
        self._notify_callbacks(progress)

    def stop_playback(self) -> None:
        """Stop playback tracking."""
        if self._playback_start_time:
            progress = ProgressInfo(
                operation=self.operation_name,
                status=ProgressStatus.COMPLETED,
                percentage=100.0,
                message="音乐播放已完成",
                details={
                    "song_duration": self._song_duration,
                    "current_position": self._song_duration or 0.0,
                    "playback_state": "stopped"
                }
            )
            self._notify_callbacks(progress)

        # Reset state
        self._playback_start_time = None
        self._total_paused_duration = 0.0
        self._pause_start_time = None
        self._song_duration = None

    def get_current_position(self) -> float:
        """
        Get the current playback position in seconds.

        Returns:
            Current position in seconds, or 0.0 if not playing
        """
        if not self._playback_start_time:
            return 0.0

        current_time = time.time()
        elapsed = current_time - self._playback_start_time

        # Subtract paused duration
        total_paused = self._total_paused_duration

        # If currently paused, add current pause duration
        if self._pause_start_time:
            current_pause_duration = current_time - self._pause_start_time
            total_paused += current_pause_duration

        position = max(0.0, elapsed - total_paused)

        # Don't exceed song duration
        if self._song_duration:
            position = min(position, self._song_duration)

        return position

    def seek_to_position(self, target_seconds: float) -> None:
        """
        Update progress tracking after a seek operation.

        Args:
            target_seconds: Position that was seeked to in seconds
        """
        if not self._playback_start_time or not self._song_duration:
            self.logger.warning("Cannot seek: playback not started or no song duration")
            return

        current_time = time.time()

        # Adjust the start time to account for the seek position
        # New start time = current time - target position
        self._playback_start_time = current_time - target_seconds

        # Reset paused duration tracking
        self._total_paused_duration = 0.0

        # Clear any existing pause state
        self._pause_start_time = None

        # Calculate percentage for the new position
        percentage = min((target_seconds / self._song_duration * 100), 100.0)

        # Notify callbacks of seek operation
        progress = ProgressInfo(
            operation=self.operation_name,
            status=ProgressStatus.IN_PROGRESS,
            percentage=percentage,
            message=f"已跳转到: {self.format_time(target_seconds)}/{self.format_time(self._song_duration)}",
            details={
                "song_duration": self._song_duration,
                "current_position": target_seconds,
                "playback_state": "playing"
            }
        )
        self._notify_callbacks(progress)

        self.logger.debug(f"Seek completed: updated timing to position {target_seconds}s")

    @staticmethod
    def format_time(seconds: float) -> str:
        """
        Format time in seconds to MM:SS or HH:MM:SS format.

        Args:
            seconds: Time in seconds

        Returns:
            Formatted time string
        """
        seconds = int(seconds)

        if seconds < 3600:  # Less than 1 hour
            minutes, secs = divmod(seconds, 60)
            return f"{minutes:02d}:{secs:02d}"
        else:  # 1 hour or more
            hours, remainder = divmod(seconds, 3600)
            minutes, secs = divmod(remainder, 60)
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class MusicProgressUpdater:
    """
    Discord progress updater specialized for music playback.

    Creates and maintains elegant Discord embeds with visual progress bars
    that update in real-time to show current playback position.
    """

    def __init__(self, music_player, update_interval: float = 5.0, progress_bar_length: int = 12):
        """
        Initialize the music progress updater.

        Args:
            music_player: Music player instance for accessing playback state
            update_interval: Update interval in seconds
            progress_bar_length: Length of the progress bar in characters
        """
        self.logger = logging.getLogger("similubot.progress.music_updater")
        self.music_player = music_player
        self.update_interval = update_interval
        self.progress_bar_length = progress_bar_length

        # Active progress bar tracking
        self._active_progress_bars: Dict[int, asyncio.Task] = {}

        # Lyrics functionality
        self.lyrics_manager = LyricsManager()

        # Track last update positions to catch missed lyrics during fast sections
        self._last_update_positions: Dict[int, float] = {}

    def create_progress_bar(self, current_seconds: float, total_seconds: float) -> str:
        """
        Create a visual progress bar using Unicode characters.

        Args:
            current_seconds: Current playback position in seconds
            total_seconds: Total song duration in seconds

        Returns:
            Unicode progress bar string
        """
        if total_seconds <= 0:
            return "▬" * self.progress_bar_length

        # Calculate progress percentage
        progress = min(current_seconds / total_seconds, 1.0)

        # Calculate position of the progress indicator
        filled_length = int(progress * self.progress_bar_length)

        # Create the progress bar
        if filled_length == 0:
            # At the beginning
            bar = "🔘" + "▬" * (self.progress_bar_length - 1)
        elif filled_length >= self.progress_bar_length:
            # At the end
            bar = "▬" * (self.progress_bar_length - 1) + "🔘"
        else:
            # In the middle
            bar = "▬" * filled_length + "🔘" + "▬" * (self.progress_bar_length - filled_length - 1)

        return bar

    @staticmethod
    def format_time(seconds: float) -> str:
        """
        Format time in seconds to MM:SS or HH:MM:SS format.

        Args:
            seconds: Time in seconds

        Returns:
            Formatted time string
        """
        return MusicProgressTracker.format_time(seconds)

    def get_playback_status_icon(self, guild_id: int) -> str:
        """
        Get the appropriate playback status icon.

        Args:
            guild_id: Discord guild ID

        Returns:
            Status icon (▶, ⏸, ⏹)
        """
        if self.music_player.voice_manager.is_playing(guild_id):
            return "▶"
        elif self.music_player.voice_manager.is_paused(guild_id):
            return "⏸"
        else:
            return "⏹"

    async def get_song_lyrics(self, song) -> Optional[List[LyricLine]]:
        """
        获取歌曲的歌词，使用歌词管理器

        Args:
            song: 包含标题和上传者信息的歌曲对象

        Returns:
            LyricLine对象列表，如果未找到歌词则返回None
        """
        try:
            self.logger.debug(f"获取歌词: {song.title} by {song.uploader}")

            # 使用歌词管理器获取歌词
            lyrics_data = await self.lyrics_manager.get_lyrics(song.title, song.uploader)

            if not lyrics_data:
                self.logger.debug(f"未找到歌词: {song.title}")
                return None

            # 检查是否为器乐曲
            if self.lyrics_manager.is_instrumental_track(lyrics_data):
                self.logger.debug(f"器乐曲或无有效歌词: {song.title}")
                return None

            self.logger.info(f"成功获取歌词: {song.title} ({len(lyrics_data.lyrics)} 行)")
            return lyrics_data.lyrics

        except Exception as e:
            self.logger.error(f"获取歌词时出错 '{song.title}': {e}", exc_info=True)
            return None

    def create_progress_embed(self, guild_id: int, song, lyrics: Optional[List[LyricLine]] = None) -> Optional[discord.Embed]:
        """
        Create a Discord embed with the current progress bar and synchronized lyrics.

        Args:
            guild_id: Discord guild ID
            song: Current song object
            lyrics: Optional list of parsed lyrics

        Returns:
            Discord embed with progress bar and lyrics, or None if not playing
        """
        try:
            # Get current playback position
            current_position = self.music_player.get_current_playback_position(guild_id)
            if current_position is None:
                return None

            # Get playback status
            status_icon = self.get_playback_status_icon(guild_id)

            # Create progress bar
            progress_bar = self.create_progress_bar(current_position, song.duration)

            # Format times
            current_time = self.format_time(current_position)
            total_time = self.format_time(song.duration)

            # Create embed
            embed = discord.Embed(
                title="🎵 正在播放",
                color=discord.Color.green()
            )

            # Song title and artist
            embed.add_field(
                name="歌曲",
                value=f"**{song.title}**",
                inline=False
            )

            # Progress bar with time
            progress_text = f"{status_icon} {progress_bar} [{current_time}/{total_time}] 🔊"
            embed.add_field(
                name="进度",
                value=progress_text,
                inline=False
            )

            # Add synchronized lyrics if available
            if lyrics:
                lyric_text = self._get_current_lyric_display(lyrics, current_position, guild_id)
                if lyric_text:
                    embed.add_field(
                        name="🎤 歌词",
                        value=lyric_text,
                        inline=False
                    )

            # Additional info
            embed.add_field(
                name="艺术家",
                value=song.uploader,
                inline=True
            )

            embed.add_field(
                name="点歌人",
                value=song.requester.display_name,
                inline=True
            )

            # Add thumbnail if available
            if song.audio_info.thumbnail_url:
                embed.set_thumbnail(url=song.audio_info.thumbnail_url)

            # Add timestamp
            embed.timestamp = discord.utils.utcnow()

            return embed

        except Exception as e:
            self.logger.error(f"Error creating progress embed: {e}", exc_info=True)
            return None

    def _get_current_lyric_display(self, lyrics: List[LyricLine], current_position: float, guild_id: int) -> str:
        """
        Get the current lyric display text based on playback position.

        Enhanced to catch lyrics that may have been missed during fast-paced sections
        by showing all lyrics that occurred within the update interval as current lyrics.

        Args:
            lyrics: List of parsed lyric lines
            current_position: Current playback position in seconds
            guild_id: Discord guild ID for tracking last update position

        Returns:
            Formatted lyric text for display
        """
        try:
            # Get last update position for this guild
            last_position = self._last_update_positions.get(guild_id, 0.0)

            # Update the last position for next time
            self._last_update_positions[guild_id] = current_position

            # Get lyrics that occurred since last update (for fast-paced sections)
            interval_lyrics = []
            if last_position > 0 and current_position > last_position:
                interval_lyrics = self.lyrics_manager.parser.get_lyrics_since_last_update(
                    lyrics, last_position, current_position, max_lines=4
                )

            # Get current lyric context
            context = self.lyrics_manager.parser.get_lyric_context(lyrics, current_position, context_lines=1)
            current_line = context.get('current')
            next_lines = context.get('next', [])

            # Build display parts
            display_parts = []

            # Collect all current lyrics (interval + current)
            current_lyrics = []

            # Add lyrics from the interval (missed during fast sections)
            if interval_lyrics:
                current_lyrics.extend(interval_lyrics)
                self.logger.debug(f"Including {len(interval_lyrics)} interval lyrics for guild {guild_id}")

            # Add the current line if it's not already in interval_lyrics
            if current_line:
                # Check if current line is already in interval_lyrics to avoid duplicates
                if not any(lyric.timestamp == current_line.timestamp for lyric in interval_lyrics):
                    current_lyrics.append(current_line)

            # Display all current lyrics as bold
            if current_lyrics:
                for lyric in current_lyrics:
                    lyric_text = self.lyrics_manager.format_lyric_display(lyric, show_translation=True)
                    if lyric_text:
                        display_parts.append(f"**{lyric_text}**")
            elif next_lines:
                # Show upcoming lyric if no current lyrics
                upcoming_line = next_lines[0]
                formatted_text = self.lyrics_manager.format_lyric_display(upcoming_line)
                display_parts.append(f"*即将播放:*\n{formatted_text}")
            else:
                return "*此时暂无歌词*"

            # Show next line as preview if available and we have current lyrics
            if current_lyrics and next_lines:
                next_line = next_lines[0]
                # Make sure the next line isn't already displayed as current
                if not any(lyric.timestamp == next_line.timestamp for lyric in current_lyrics):
                    next_text = self.lyrics_manager.format_lyric_display(next_line, show_translation=False)
                    if next_text:
                        display_parts.append(f"*{next_text}*")

            # Combine parts
            if display_parts:
                result = "\n".join(display_parts)
                # Limit length to avoid Discord embed limits
                if len(result) > 200:
                    result = result[:197] + "..."
                return result
            else:
                return "*♪ 纯音乐 ♪*"

        except Exception as e:
            self.logger.error(f"Error formatting lyric display: {e}", exc_info=True)
            return "*歌词显示错误*"

    async def start_progress_updates(
        self,
        message: discord.Message,
        guild_id: int,
        song,
        update_interval: Optional[float] = None
    ) -> None:
        """
        Start real-time progress bar updates with synchronized lyrics for a message.

        Args:
            message: Discord message to update
            guild_id: Discord guild ID
            song: Current song object
            update_interval: Update interval in seconds (uses default if None)
        """
        interval = update_interval or self.update_interval

        try:
            self.logger.info(f"Starting progress updates with lyrics for guild {guild_id}")

            # Fetch lyrics for the song (async, non-blocking)
            lyrics = None
            try:
                lyrics = await self.get_song_lyrics(song)
                if lyrics:
                    self.logger.info(f"Loaded {len(lyrics)} lyric lines for: {song.title}")
                else:
                    self.logger.debug(f"No lyrics available for: {song.title}")
            except Exception as e:
                self.logger.warning(f"Failed to load lyrics for '{song.title}': {e}")

            update_count = 0
            max_updates = 120  # Maximum 10 minutes of updates (120 * 5 seconds)

            while update_count < max_updates:
                # Check if song is still playing
                current_song = self.music_player.get_queue_manager(guild_id).get_current_song()
                if not current_song or current_song.url != song.url:
                    self.logger.debug(f"Song changed or stopped, ending progress updates for guild {guild_id}")
                    break

                # Check if voice client is still connected and playing
                if not self.music_player.voice_manager.is_connected(guild_id):
                    self.logger.debug(f"Voice client disconnected, ending progress updates for guild {guild_id}")
                    break

                # Create updated embed with lyrics
                embed = self.create_progress_embed(guild_id, song, lyrics)
                if not embed:
                    self.logger.debug(f"Could not create progress embed, ending updates for guild {guild_id}")
                    break

                # Update the message
                try:
                    await message.edit(embed=embed)
                    self.logger.debug(f"Updated progress bar for guild {guild_id} (update #{update_count + 1})")
                except discord.NotFound:
                    self.logger.debug(f"Message deleted, ending progress updates for guild {guild_id}")
                    break
                except discord.HTTPException as e:
                    if e.status == 429:  # Rate limited
                        self.logger.warning(f"Rate limited, slowing down updates for guild {guild_id}")
                        await asyncio.sleep(10)  # Wait longer if rate limited
                    else:
                        self.logger.error(f"HTTP error updating progress: {e}")
                        break

                # Wait for next update
                await asyncio.sleep(interval)
                update_count += 1

            self.logger.info(f"Progress updates ended for guild {guild_id} after {update_count} updates")

        except asyncio.CancelledError:
            self.logger.debug(f"Progress updates cancelled for guild {guild_id}")
        except Exception as e:
            self.logger.error(f"Error in progress updates for guild {guild_id}: {e}", exc_info=True)
        finally:
            # Clean up
            if guild_id in self._active_progress_bars:
                del self._active_progress_bars[guild_id]
            if guild_id in self._last_update_positions:
                del self._last_update_positions[guild_id]

    async def show_progress_bar(self, message: discord.Message, guild_id: int) -> bool:
        """
        Show a real-time progress bar for the current song.

        Args:
            message: Discord message to update with progress bar
            guild_id: Discord guild ID

        Returns:
            True if progress bar started successfully, False otherwise
        """
        try:
            # Get current song
            current_song = self.music_player.get_queue_manager(guild_id).get_current_song()
            if not current_song:
                return False

            # Check if already showing progress for this guild
            if guild_id in self._active_progress_bars:
                # Cancel existing progress updates
                self._active_progress_bars[guild_id].cancel()
                del self._active_progress_bars[guild_id]

            # Fetch lyrics for initial display
            lyrics = None
            try:
                lyrics = await self.get_song_lyrics(current_song)
            except Exception as e:
                self.logger.warning(f"Failed to load lyrics for initial display: {e}")

            # Create initial embed with lyrics
            embed = self.create_progress_embed(guild_id, current_song, lyrics)
            if not embed:
                return False

            # Update message with initial progress
            await message.edit(content=None, embed=embed)

            # Start progress updates
            task = asyncio.create_task(
                self.start_progress_updates(message, guild_id, current_song)
            )
            self._active_progress_bars[guild_id] = task

            return True

        except Exception as e:
            self.logger.error(f"Error showing progress bar for guild {guild_id}: {e}", exc_info=True)
            return False

    def stop_progress_updates(self, guild_id: int) -> None:
        """
        Stop progress updates for a guild.

        Args:
            guild_id: Discord guild ID
        """
        if guild_id in self._active_progress_bars:
            self._active_progress_bars[guild_id].cancel()
            del self._active_progress_bars[guild_id]
            self.logger.debug(f"Stopped progress updates for guild {guild_id}")

        # Clean up last update position tracking
        if guild_id in self._last_update_positions:
            del self._last_update_positions[guild_id]
            self.logger.debug(f"Cleaned up last update position for guild {guild_id}")

    async def cleanup_all_progress_bars(self) -> None:
        """Clean up all active progress bars."""
        self.logger.info("Cleaning up all progress bars")

        for guild_id in list(self._active_progress_bars.keys()):
            self.stop_progress_updates(guild_id)

        self._active_progress_bars.clear()
        self._last_update_positions.clear()


# Compatibility alias for existing code
MusicProgressBar = MusicProgressUpdater
