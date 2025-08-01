"""LRC format lyrics parser and synchronization logic."""

import logging
import re
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class LyricLine:
    """Represents a single line of lyrics with timestamp."""
    timestamp: float  # Time in seconds
    text: str  # Lyric text
    translated_text: Optional[str] = None  # Translated text if available


class LyricsParser:
    """
    Parser for LRC format lyrics with synchronization capabilities.

    Handles parsing of LRC timestamps and provides methods for
    finding the current lyric line based on playback position.
    """

    def __init__(self):
        """Initialize the lyrics parser."""
        self.logger = logging.getLogger("similubot.music.lyrics_parser")

        # LRC timestamp pattern: [mm:ss.xxx] or [mm:ss]
        self.timestamp_pattern = re.compile(r'\[(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\]')

        self.logger.debug("Lyrics parser initialized")

    def parse_lrc_lyrics(self, lrc_content: str, translated_lrc: str = "") -> List[LyricLine]:
        """
        Parse LRC format lyrics into a list of LyricLine objects.

        Args:
            lrc_content: LRC format lyrics content
            translated_lrc: Optional translated lyrics content

        Returns:
            List of LyricLine objects sorted by timestamp
        """
        try:
            if not lrc_content or not lrc_content.strip():
                self.logger.debug("Empty lyrics content provided")
                return []

            # Parse main lyrics
            main_lyrics = self._parse_single_lrc(lrc_content)

            # Parse translated lyrics if available
            translated_lyrics = {}
            if translated_lrc and translated_lrc.strip():
                translated_lines = self._parse_single_lrc(translated_lrc)
                # Create a mapping of timestamps to translated text
                for line in translated_lines:
                    translated_lyrics[line.timestamp] = line.text

            # Combine main and translated lyrics
            combined_lyrics = []
            for line in main_lyrics:
                translated_text = translated_lyrics.get(line.timestamp)
                combined_line = LyricLine(
                    timestamp=line.timestamp,
                    text=line.text,
                    translated_text=translated_text
                )
                combined_lyrics.append(combined_line)

            # Sort by timestamp
            combined_lyrics.sort(key=lambda x: x.timestamp)

            self.logger.info(f"Parsed {len(combined_lyrics)} lyric lines")
            return combined_lyrics

        except Exception as e:
            self.logger.error(f"Error parsing LRC lyrics: {e}", exc_info=True)
            return []

    def _parse_single_lrc(self, lrc_content: str) -> List[LyricLine]:
        """
        Parse a single LRC content string.

        Args:
            lrc_content: LRC format content

        Returns:
            List of LyricLine objects
        """
        lines = []

        for line in lrc_content.split('\n'):
            line = line.strip()
            if not line:
                continue

            # Find all timestamps in the line
            timestamps = self.timestamp_pattern.findall(line)
            if not timestamps:
                continue

            # Extract the text after the last timestamp
            text = self.timestamp_pattern.sub('', line).strip()

            # Skip empty text lines (but keep instrumental markers)
            if not text and not self._is_instrumental_marker(line):
                continue

            # Convert each timestamp and create lyric lines
            for timestamp_match in timestamps:
                try:
                    timestamp_seconds = self._convert_timestamp_to_seconds(timestamp_match)
                    lyric_line = LyricLine(timestamp=timestamp_seconds, text=text)
                    lines.append(lyric_line)
                except ValueError as e:
                    self.logger.warning(f"Invalid timestamp in line '{line}': {e}")
                    continue

        return lines

    def _convert_timestamp_to_seconds(self, timestamp_match: Tuple[str, str, str]) -> float:
        """
        Convert LRC timestamp to seconds.

        Args:
            timestamp_match: Tuple of (minutes, seconds, milliseconds)

        Returns:
            Time in seconds as float
        """
        minutes, seconds, milliseconds = timestamp_match

        try:
            total_seconds = int(minutes) * 60 + int(seconds)

            # Add milliseconds if present
            if milliseconds:
                # Pad or truncate to 3 digits
                ms_str = milliseconds.ljust(3, '0')[:3]
                total_seconds += int(ms_str) / 1000.0

            return total_seconds

        except ValueError as e:
            raise ValueError(f"Invalid timestamp format: {timestamp_match}") from e

    def _is_instrumental_marker(self, line: str) -> bool:
        """
        Check if a line is an instrumental marker.

        Args:
            line: LRC line to check

        Returns:
            True if the line appears to be an instrumental marker
        """
        # Common instrumental markers
        instrumental_patterns = [
            r'\[00:00\.000\]',  # Common start marker
            r'作词',  # Lyricist credit
            r'作曲',  # Composer credit
            r'编曲',  # Arranger credit
            r'制作',  # Producer credit
        ]

        for pattern in instrumental_patterns:
            if re.search(pattern, line):
                return True

        return False

    def get_current_lyric(self, lyrics: List[LyricLine], current_position: float) -> Optional[LyricLine]:
        """
        Get the current lyric line based on playback position.

        Args:
            lyrics: List of parsed lyric lines
            current_position: Current playback position in seconds

        Returns:
            Current LyricLine or None if no suitable line found
        """
        if not lyrics:
            return None

        # Find the most recent lyric line that has passed
        current_line = None

        for line in lyrics:
            if line.timestamp <= current_position:
                current_line = line
            else:
                break  # Lines are sorted by timestamp

        return current_line

    def get_upcoming_lyric(self, lyrics: List[LyricLine], current_position: float) -> Optional[LyricLine]:
        """
        Get the next upcoming lyric line.

        Args:
            lyrics: List of parsed lyric lines
            current_position: Current playback position in seconds

        Returns:
            Next LyricLine or None if no upcoming line
        """
        if not lyrics:
            return None

        for line in lyrics:
            if line.timestamp > current_position:
                return line

        return None

    def get_lyrics_since_last_update(
        self,
        lyrics: List[LyricLine],
        last_position: float,
        current_position: float,
        max_lines: int = 3
    ) -> List[LyricLine]:
        """
        Get lyrics that occurred between last update and current position.

        This method helps ensure no lyrics are skipped during fast-paced sections
        by returning all lyrics that should have been displayed since the last update.

        Args:
            lyrics: List of parsed lyric lines
            last_position: Playback position at last update (seconds)
            current_position: Current playback position (seconds)
            max_lines: Maximum number of lines to return

        Returns:
            List of LyricLine objects that occurred in the time interval
        """
        if not lyrics or current_position <= last_position:
            return []

        # Find lyrics that occurred between last_position and current_position
        interval_lyrics = []

        for line in lyrics:
            # Include lyrics that started after last_position and before/at current_position
            if last_position < line.timestamp <= current_position:
                interval_lyrics.append(line)

        # Limit to max_lines to avoid overwhelming display
        if len(interval_lyrics) > max_lines:
            # Keep the most recent lines
            interval_lyrics = interval_lyrics[-max_lines:]

        self.logger.debug(f"Found {len(interval_lyrics)} lyrics between {last_position:.1f}s and {current_position:.1f}s")
        return interval_lyrics

    def get_lyric_context(
        self,
        lyrics: List[LyricLine],
        current_position: float,
        context_lines: int = 1
    ) -> Dict[str, Any]:
        """
        Get lyric context including current, previous, and next lines.

        Args:
            lyrics: List of parsed lyric lines
            current_position: Current playback position in seconds
            context_lines: Number of context lines before/after current

        Returns:
            Dictionary with lyric context information
        """
        if not lyrics:
            return {
                'current': None,
                'previous': [],
                'next': [],
                'progress': 0.0
            }

        # Find current line index
        current_index = -1
        for i, line in enumerate(lyrics):
            if line.timestamp <= current_position:
                current_index = i
            else:
                break

        # Get current line
        current_line = lyrics[current_index] if current_index >= 0 else None

        # Get previous lines
        previous_lines = []
        if current_index > 0:
            start_idx = max(0, current_index - context_lines)
            previous_lines = lyrics[start_idx:current_index]

        # Get next lines
        next_lines = []
        if current_index >= 0 and current_index < len(lyrics) - 1:
            end_idx = min(len(lyrics), current_index + 1 + context_lines)
            next_lines = lyrics[current_index + 1:end_idx]

        # Calculate progress within current line
        progress = 0.0
        if current_line and current_index < len(lyrics) - 1:
            next_line = lyrics[current_index + 1]
            line_duration = next_line.timestamp - current_line.timestamp
            if line_duration > 0:
                elapsed = current_position - current_line.timestamp
                progress = min(1.0, max(0.0, elapsed / line_duration))

        return {
            'current': current_line,
            'previous': previous_lines,
            'next': next_lines,
            'progress': progress,
            'total_lines': len(lyrics),
            'current_index': current_index
        }

    def is_instrumental_track(self, lyrics: List[LyricLine]) -> bool:
        """
        Determine if the track appears to be instrumental.

        Args:
            lyrics: List of parsed lyric lines

        Returns:
            True if the track appears to be instrumental
        """
        if not lyrics:
            return True

        # Check if all lines are empty or contain only metadata
        text_lines = 0
        for line in lyrics:
            if line.text and line.text.strip():
                # Skip common metadata patterns
                if not any(pattern in line.text for pattern in ['作词', '作曲', '编曲', '制作']):
                    text_lines += 1

        # Consider instrumental if less than 3 actual lyric lines
        return text_lines < 3

    def format_lyric_display(self, lyric_line: LyricLine, show_translation: bool = True) -> str:
        """
        Format a lyric line for display.

        Args:
            lyric_line: LyricLine to format
            show_translation: Whether to include translation if available

        Returns:
            Formatted lyric string
        """
        if not lyric_line or not lyric_line.text:
            return ""

        display_parts = [lyric_line.text]

        # Add translation if available and requested
        if show_translation and lyric_line.translated_text:
            display_parts.append(f"*{lyric_line.translated_text}*")

        return "\n".join(display_parts)

    @staticmethod
    def format_time(seconds: float) -> str:
        """
        Format time in seconds to MM:SS format.

        Args:
            seconds: Time in seconds

        Returns:
            Formatted time string
        """
        seconds = int(seconds)
        minutes, secs = divmod(seconds, 60)
        return f"{minutes:02d}:{secs:02d}"
