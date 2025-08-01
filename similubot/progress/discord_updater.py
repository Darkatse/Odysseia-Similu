"""Discord progress updater for real-time progress display."""

import asyncio
import logging
import time
from typing import Optional, Dict, Any
import discord

from .base import ProgressInfo, ProgressStatus, ProgressCallback


class DiscordProgressUpdater:
    """
    Discord progress updater that displays real-time progress in Discord messages.

    Handles creating and updating Discord embeds with progress bars, status messages,
    and estimated completion times. Includes rate limiting to prevent Discord API abuse.
    """

    def __init__(
        self,
        message: discord.Message,
        update_interval: float = 5.0,
        progress_bar_length: int = 20
    ):
        """
        Initialize the Discord progress updater.

        Args:
            message: Discord message to update with progress
            update_interval: Minimum seconds between Discord message updates
            progress_bar_length: Length of the progress bar in characters
        """
        self.message = message
        self.update_interval = update_interval
        self.progress_bar_length = progress_bar_length
        self.logger = logging.getLogger("similubot.progress.discord")

        self.last_update_time = 0.0
        self.current_embed: Optional[discord.Embed] = None
        self.is_updating = False
        self.pending_update = False

        # Progress bar characters
        self.filled_char = "█"
        self.empty_char = "░"
        self.partial_chars = ["▏", "▎", "▍", "▌", "▋", "▊", "▉"]

    async def update_progress(self, progress: ProgressInfo) -> None:
        """
        Update Discord message with progress information.

        Args:
            progress: Progress information to display
        """
        current_time = time.time()

        # Rate limiting: only update if enough time has passed or if status changed significantly
        if (current_time - self.last_update_time < self.update_interval and
            progress.status == ProgressStatus.IN_PROGRESS and
            not self.pending_update):
            self.pending_update = True
            return

        # Prevent concurrent updates
        if self.is_updating:
            self.pending_update = True
            return

        self.is_updating = True
        self.pending_update = False

        try:
            embed = self._create_progress_embed(progress)
            await self.message.edit(embed=embed)
            self.current_embed = embed
            self.last_update_time = current_time

            self.logger.debug(f"Updated Discord progress: {progress.operation} - {progress.percentage:.1f}%")

        except discord.HTTPException as e:
            self.logger.warning(f"Failed to update Discord message: {e}")
        except Exception as e:
            self.logger.error(f"Error updating Discord progress: {e}", exc_info=True)
        finally:
            self.is_updating = False

            # If there's a pending update, schedule it
            if self.pending_update:
                asyncio.create_task(self._delayed_update())

    async def _delayed_update(self) -> None:
        """Schedule a delayed update for pending progress."""
        await asyncio.sleep(1.0)  # Small delay to batch updates
        if self.pending_update:
            # This will be handled by the next progress update
            pass

    def _create_progress_embed(self, progress: ProgressInfo) -> discord.Embed:
        """
        Create a Discord embed with progress information.

        Args:
            progress: Progress information to display

        Returns:
            Discord embed with progress visualization
        """
        # Choose embed color based on status
        color_map = {
            ProgressStatus.STARTING: 0x3498db,      # Blue
            ProgressStatus.IN_PROGRESS: 0xf39c12,   # Orange
            ProgressStatus.COMPLETED: 0x2ecc71,     # Green
            ProgressStatus.FAILED: 0xe74c3c,        # Red
            ProgressStatus.CANCELLED: 0x95a5a6      # Gray
        }

        color = color_map.get(progress.status, 0x3498db)
        embed = discord.Embed(color=color)

        # Set title based on operation and status
        if progress.status == ProgressStatus.COMPLETED:
            embed.title = f"✅ {progress.operation} Complete"
        elif progress.status == ProgressStatus.FAILED:
            embed.title = f"❌ {progress.operation} Failed"
        elif progress.status == ProgressStatus.CANCELLED:
            embed.title = f"⏹️ {progress.operation} Cancelled"
        else:
            embed.title = f"⏳ {progress.operation}"

        # Add progress bar for in-progress operations
        if progress.status == ProgressStatus.IN_PROGRESS and progress.percentage > 0:
            progress_bar = self._create_progress_bar(progress.percentage)
            embed.add_field(
                name="Progress",
                value=f"{progress_bar} {progress.percentage:.1f}%",
                inline=False
            )

        # Add status message
        if progress.message:
            embed.description = progress.message

        # Add detailed information
        fields_added = 0

        # File size information
        if progress.current_size is not None and progress.total_size is not None:
            current_str = self._format_size(progress.current_size)
            total_str = self._format_size(progress.total_size)
            embed.add_field(
                name="Size",
                value=f"{current_str} / {total_str}",
                inline=True
            )
            fields_added += 1

        # Speed information
        if progress.speed is not None:
            if progress.operation == "Audio Conversion":
                # For FFmpeg, speed is a multiplier
                speed_str = f"{progress.speed:.1f}x"
            else:
                # For downloads/uploads, speed is bytes/second
                speed_str = self._format_speed(progress.speed)
            embed.add_field(
                name="Speed",
                value=speed_str,
                inline=True
            )
            fields_added += 1

        # ETA information
        if progress.eta is not None and progress.eta > 0:
            eta_str = self._format_time(progress.eta)
            embed.add_field(
                name="ETA",
                value=eta_str,
                inline=True
            )
            fields_added += 1

        # Add empty field for alignment if needed
        if fields_added % 3 != 0:
            for _ in range(3 - (fields_added % 3)):
                embed.add_field(name="\u200b", value="\u200b", inline=True)

        # Add timestamp
        embed.timestamp = discord.utils.utcnow()

        return embed

    def _create_progress_bar(self, percentage: float) -> str:
        """
        Create a Unicode progress bar.

        Args:
            percentage: Progress percentage (0-100)

        Returns:
            Unicode progress bar string
        """
        if percentage < 0:
            percentage = 0
        elif percentage > 100:
            percentage = 100

        # Calculate filled and empty portions
        filled_length = (percentage / 100) * self.progress_bar_length
        filled_blocks = int(filled_length)
        partial_block = filled_length - filled_blocks

        # Build progress bar
        bar = self.filled_char * filled_blocks

        # Add partial block if needed
        if partial_block > 0 and filled_blocks < self.progress_bar_length:
            partial_index = min(int(partial_block * len(self.partial_chars)), len(self.partial_chars) - 1)
            bar += self.partial_chars[partial_index]
            filled_blocks += 1

        # Add empty blocks
        empty_blocks = self.progress_bar_length - filled_blocks
        bar += self.empty_char * empty_blocks

        return f"`{bar}`"

    def _format_size(self, size_bytes: int) -> str:
        """Format size in bytes to human-readable format."""
        if size_bytes >= 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
        elif size_bytes >= 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        elif size_bytes >= 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes} B"

    def _format_speed(self, speed_bytes_per_sec: float) -> str:
        """Format speed in bytes/second to human-readable format."""
        if speed_bytes_per_sec >= 1024 * 1024:
            return f"{speed_bytes_per_sec / (1024 * 1024):.1f} MB/s"
        elif speed_bytes_per_sec >= 1024:
            return f"{speed_bytes_per_sec / 1024:.1f} KB/s"
        else:
            return f"{speed_bytes_per_sec:.0f} B/s"

    def _format_time(self, seconds: float) -> str:
        """Format time in seconds to human-readable format."""
        if seconds >= 3600:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
        elif seconds >= 60:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            return f"{seconds:.0f}s"

    def create_callback(self) -> ProgressCallback:
        """
        Create a progress callback function for use with progress trackers.

        Returns:
            Async callback function that can be added to progress trackers
        """
        def callback(progress: ProgressInfo) -> None:
            # Schedule the async update safely
            try:
                # Try to get the current event loop
                loop = asyncio.get_running_loop()
                asyncio.create_task(self.update_progress(progress))
            except RuntimeError:
                # No running event loop, try to schedule for later
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Loop is running in another thread, use call_soon_threadsafe
                        asyncio.run_coroutine_threadsafe(self.update_progress(progress), loop)
                    else:
                        # No active loop, create a new task when loop starts
                        loop.create_task(self.update_progress(progress))
                except RuntimeError:
                    # Fallback: log the progress instead of updating Discord
                    import logging
                    logger = logging.getLogger("similubot.progress.discord")
                    logger.info(f"Progress update (no event loop): {progress.operation} - {progress.percentage:.1f}% - {progress.message}")

        return callback
