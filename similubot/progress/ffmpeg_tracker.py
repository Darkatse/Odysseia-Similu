"""FFmpeg conversion progress tracker."""

import re
import logging
from typing import Optional, Dict, Any

from .base import ProgressTracker


class FFmpegProgressTracker(ProgressTracker):
    """
    Progress tracker for FFmpeg conversions.
    
    Parses FFmpeg output to extract conversion progress information.
    Expected format: size=   66816kB time=00:45:47.11 bitrate= 199.2kbits/s speed=29.7x
    """
    
    # Regex patterns for parsing FFmpeg output
    PROGRESS_PATTERN = re.compile(
        r'size=\s*(\d+(?:\.\d+)?)(kB|MB|GB)?\s+'
        r'time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})\s+'
        r'bitrate=\s*(\d+(?:\.\d+)?)(kbits/s|Mbits/s)?\s+'
        r'speed=\s*(\d+(?:\.\d+)?)x'
    )
    
    TIME_PATTERN = re.compile(r'time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})')
    SIZE_PATTERN = re.compile(r'size=\s*(\d+(?:\.\d+)?)(kB|MB|GB)?')
    SPEED_PATTERN = re.compile(r'speed=\s*(\d+(?:\.\d+)?)x')
    BITRATE_PATTERN = re.compile(r'bitrate=\s*(\d+(?:\.\d+)?)(kbits/s|Mbits/s)?')
    
    # Duration pattern for input file analysis
    DURATION_PATTERN = re.compile(r'Duration:\s*(\d{2}):(\d{2}):(\d{2})\.(\d{2})')
    
    def __init__(self, total_duration: Optional[float] = None):
        """
        Initialize the FFmpeg progress tracker.
        
        Args:
            total_duration: Total duration of the input file in seconds (if known)
        """
        super().__init__("Audio Conversion")
        self.logger = logging.getLogger("similubot.progress.ffmpeg")
        self.total_duration = total_duration
        self.input_analyzed = False
        
    def parse_output(self, output_line: str) -> bool:
        """
        Parse a line of FFmpeg output for progress information.
        
        Args:
            output_line: Line of output from FFmpeg
            
        Returns:
            True if progress information was found and parsed, False otherwise
        """
        line = output_line.strip()
        
        # First, try to get duration from input analysis
        if not self.input_analyzed and "Duration:" in line:
            duration_match = self.DURATION_PATTERN.search(line)
            if duration_match:
                hours, minutes, seconds, centiseconds = map(int, duration_match.groups())
                self.total_duration = hours * 3600 + minutes * 60 + seconds + centiseconds / 100
                self.input_analyzed = True
                self.logger.debug(f"Detected input duration: {self.total_duration:.2f} seconds")
                
                # Update with initial message
                self.update(message="Analyzing input file...")
                return True
        
        # Look for progress information
        progress_match = self.PROGRESS_PATTERN.search(line)
        if progress_match:
            try:
                (size_val, size_unit, time_h, time_m, time_s, time_cs, 
                 bitrate_val, bitrate_unit, speed_val) = progress_match.groups()
                
                # Parse current time
                current_time = (int(time_h) * 3600 + int(time_m) * 60 + 
                               int(time_s) + int(time_cs) / 100)
                
                # Parse output size
                size_bytes = self._parse_size(size_val, size_unit or 'kB')
                
                # Parse speed
                speed_multiplier = float(speed_val) if speed_val else 1.0
                
                # Calculate percentage if we know total duration
                percentage = 0.0
                eta = None
                if self.total_duration and self.total_duration > 0:
                    percentage = min((current_time / self.total_duration) * 100, 100.0)
                    
                    # Calculate ETA based on speed
                    if speed_multiplier > 0:
                        remaining_time = self.total_duration - current_time
                        eta = remaining_time / speed_multiplier
                
                # Format time
                time_str = self._format_time(current_time)
                total_time_str = self._format_time(self.total_duration) if self.total_duration else "unknown"
                
                # Create progress message
                message = f"Converting: {time_str}/{total_time_str}"
                if percentage > 0:
                    message += f" ({percentage:.1f}%)"
                if speed_multiplier != 1.0:
                    message += f" - {speed_multiplier:.1f}x speed"
                
                # Update progress
                self.update(
                    percentage=percentage,
                    current_size=size_bytes,
                    speed=speed_multiplier,  # Using speed multiplier as "speed"
                    eta=eta,
                    message=message,
                    details={
                        'current_time': current_time,
                        'total_duration': self.total_duration,
                        'output_size': size_bytes,
                        'bitrate': f"{bitrate_val} {bitrate_unit}" if bitrate_val else None,
                        'speed_multiplier': speed_multiplier
                    }
                )
                
                self.logger.debug(f"Parsed FFmpeg progress: {percentage:.1f}% ({time_str})")
                return True
                
            except (ValueError, IndexError) as e:
                self.logger.warning(f"Failed to parse FFmpeg progress line: {line} - {e}")
                return False
        
        # Look for simpler patterns if full pattern doesn't match
        time_match = self.TIME_PATTERN.search(line)
        if time_match and self.total_duration:
            try:
                hours, minutes, seconds, centiseconds = map(int, time_match.groups())
                current_time = hours * 3600 + minutes * 60 + seconds + centiseconds / 100
                percentage = min((current_time / self.total_duration) * 100, 100.0)
                
                time_str = self._format_time(current_time)
                total_time_str = self._format_time(self.total_duration)
                message = f"Converting: {time_str}/{total_time_str} ({percentage:.1f}%)"
                
                self.update(
                    percentage=percentage,
                    message=message,
                    details={'current_time': current_time}
                )
                return True
            except (ValueError, IndexError):
                pass
        
        # Check for completion or error messages
        if "video:" in line and "audio:" in line and "subtitle:" in line:
            # This is typically the final summary line
            self.complete("Conversion completed successfully")
            return True
        elif "error" in line.lower() or "failed" in line.lower():
            self.fail(f"Conversion error: {line}")
            return True
        elif "Press [q] to stop" in line:
            self.update(message="Starting conversion...")
            return True
            
        return False
    
    def _parse_size(self, value_str: str, unit: str) -> int:
        """
        Parse size value with unit to bytes.
        
        Args:
            value_str: Size value as string
            unit: Size unit (kB, MB, GB)
            
        Returns:
            Size in bytes
        """
        try:
            value = float(value_str)
            unit_multipliers = {
                'B': 1,
                'kB': 1024,
                'MB': 1024 * 1024,
                'GB': 1024 * 1024 * 1024
            }
            return int(value * unit_multipliers.get(unit, 1024))  # Default to kB
        except ValueError:
            return 0
    
    def _format_time(self, seconds: Optional[float]) -> str:
        """
        Format time in seconds to HH:MM:SS format.
        
        Args:
            seconds: Time in seconds
            
        Returns:
            Formatted time string
        """
        if seconds is None:
            return "00:00:00"
            
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def set_total_duration(self, duration: float) -> None:
        """
        Set the total duration of the input file.
        
        Args:
            duration: Total duration in seconds
        """
        self.total_duration = duration
        self.logger.debug(f"Set total duration: {duration:.2f} seconds")
