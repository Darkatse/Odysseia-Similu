"""Seek functionality manager for music playback."""

import logging
import re
from typing import Optional, Tuple, Union
from dataclasses import dataclass


@dataclass
class SeekResult:
    """Result of a seek operation."""
    success: bool
    target_position: Optional[float] = None
    error_message: Optional[str] = None


class SeekManager:
    """
    Manages seek functionality for music playback.
    
    Handles parsing of seek time formats, validation of seek positions,
    and provides utilities for time-based navigation in audio tracks.
    """

    # Regex patterns for different time formats
    TIME_ABSOLUTE_PATTERN = re.compile(r'^(?:(\d{1,2}):)?(\d{1,2}):(\d{2})$')  # [hh:]mm:ss
    TIME_RELATIVE_PATTERN = re.compile(r'^([+-])(?:(\d{1,2}):)?(\d{1,2}):(\d{2})$')  # +/-[hh:]mm:ss
    TIME_SECONDS_ONLY_PATTERN = re.compile(r'^([+-])?(\d+)$')  # [+/-]seconds

    def __init__(self):
        """Initialize the seek manager."""
        self.logger = logging.getLogger("similubot.music.seek_manager")

    def parse_seek_time(self, time_str: str) -> SeekResult:
        """
        Parse a seek time string into seconds.

        Supports the following formats:
        - mm:ss (absolute position)
        - hh:mm:ss (absolute position)
        - +mm:ss (relative forward)
        - -mm:ss (relative backward)
        - +seconds (relative forward)
        - -seconds (relative backward)

        Args:
            time_str: Time string to parse

        Returns:
            SeekResult with parsed time in seconds or error message
        """
        time_str = time_str.strip()
        
        if not time_str:
            return SeekResult(False, error_message="Empty time string")

        self.logger.debug(f"Parsing seek time: '{time_str}'")

        # Try relative time with full format (+/-[hh:]mm:ss)
        match = self.TIME_RELATIVE_PATTERN.match(time_str)
        if match:
            sign, hours, minutes, seconds = match.groups()
            return self._parse_time_components(sign, hours, minutes, seconds, is_relative=True)

        # Try absolute time format ([hh:]mm:ss)
        match = self.TIME_ABSOLUTE_PATTERN.match(time_str)
        if match:
            hours, minutes, seconds = match.groups()
            return self._parse_time_components(None, hours, minutes, seconds, is_relative=False)

        # Try seconds only format ([+/-]seconds)
        match = self.TIME_SECONDS_ONLY_PATTERN.match(time_str)
        if match:
            sign, seconds_str = match.groups()
            try:
                seconds = int(seconds_str)
                if sign == '-':
                    seconds = -seconds
                elif sign == '+':
                    pass  # Keep positive
                # If no sign, treat as absolute
                is_relative = sign is not None
                
                self.logger.debug(f"Parsed seconds only: {seconds} (relative: {is_relative})")
                return SeekResult(True, target_position=float(seconds))
            except ValueError:
                return SeekResult(False, error_message=f"Invalid seconds value: {seconds_str}")

        return SeekResult(False, error_message=f"Invalid time format: {time_str}")

    def _parse_time_components(
        self, 
        sign: Optional[str], 
        hours: Optional[str], 
        minutes: str, 
        seconds: str,
        is_relative: bool
    ) -> SeekResult:
        """
        Parse time components into total seconds.

        Args:
            sign: '+' or '-' for relative seeks, None for absolute
            hours: Hours component (optional)
            minutes: Minutes component
            seconds: Seconds component
            is_relative: Whether this is a relative seek

        Returns:
            SeekResult with parsed time in seconds
        """
        try:
            # Parse components
            h = int(hours) if hours else 0
            m = int(minutes)
            s = int(seconds)

            # Validate ranges
            if m >= 60:
                return SeekResult(False, error_message=f"Minutes must be less than 60: {m}")
            if s >= 60:
                return SeekResult(False, error_message=f"Seconds must be less than 60: {s}")
            if h < 0 or m < 0 or s < 0:
                return SeekResult(False, error_message="Time components cannot be negative")

            # Calculate total seconds
            total_seconds = h * 3600 + m * 60 + s

            # Apply sign for relative seeks
            if is_relative and sign == '-':
                total_seconds = -total_seconds

            self.logger.debug(f"Parsed time components: {h}h {m}m {s}s = {total_seconds}s (relative: {is_relative})")
            return SeekResult(True, target_position=float(total_seconds))

        except ValueError as e:
            return SeekResult(False, error_message=f"Invalid time components: {e}")

    def validate_seek_position(
        self, 
        target_seconds: float, 
        current_position: float, 
        song_duration: float,
        is_relative: bool = False
    ) -> SeekResult:
        """
        Validate a seek position against song boundaries.

        Args:
            target_seconds: Target position in seconds (or offset if relative)
            current_position: Current playback position in seconds
            song_duration: Total song duration in seconds
            is_relative: Whether target_seconds is a relative offset

        Returns:
            SeekResult with validated position or error message
        """
        if is_relative:
            # Calculate absolute position from relative offset
            absolute_position = current_position + target_seconds
        else:
            absolute_position = target_seconds

        # Validate boundaries
        if absolute_position < 0:
            return SeekResult(
                False, 
                error_message=f"Cannot seek to negative position: {self.format_time(absolute_position)}"
            )

        if absolute_position > song_duration:
            return SeekResult(
                False,
                error_message=f"Cannot seek beyond song duration: {self.format_time(absolute_position)} > {self.format_time(song_duration)}"
            )

        self.logger.debug(f"Validated seek position: {absolute_position}s (duration: {song_duration}s)")
        return SeekResult(True, target_position=absolute_position)

    def is_relative_seek(self, time_str: str) -> bool:
        """
        Check if a time string represents a relative seek.

        Args:
            time_str: Time string to check

        Returns:
            True if the time string is a relative seek (+/- prefix)
        """
        time_str = time_str.strip()
        return (
            self.TIME_RELATIVE_PATTERN.match(time_str) is not None or
            (self.TIME_SECONDS_ONLY_PATTERN.match(time_str) is not None and 
             time_str.startswith(('+', '-')))
        )

    @staticmethod
    def format_time(seconds: float) -> str:
        """
        Format time in seconds to HH:MM:SS or MM:SS format.

        Args:
            seconds: Time in seconds

        Returns:
            Formatted time string
        """
        if seconds < 0:
            return f"-{SeekManager.format_time(-seconds)}"

        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"

    def get_seek_examples(self) -> list[str]:
        """
        Get example seek command formats for help display.

        Returns:
            List of example seek commands
        """
        return [
            "!music seek 1:30 - Jump to 1 minute 30 seconds",
            "!music seek 2:15:45 - Jump to 2 hours 15 minutes 45 seconds", 
            "!music seek +30 - Skip forward 30 seconds",
            "!music seek -1:00 - Go back 1 minute",
            "!music seek +10:30 - Skip forward 10 minutes 30 seconds"
        ]
