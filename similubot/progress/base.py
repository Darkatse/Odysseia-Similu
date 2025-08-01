"""Base progress tracking classes and interfaces."""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Callable, Dict, Any
from enum import Enum


class ProgressStatus(Enum):
    """Progress status enumeration."""
    STARTING = "starting"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ProgressInfo:
    """
    Container for progress information.

    Attributes:
        operation: Name of the operation (e.g., "download", "convert", "upload")
        status: Current status of the operation
        percentage: Progress percentage (0-100)
        current_size: Current size processed in bytes
        total_size: Total size in bytes (if known)
        speed: Current speed in bytes/second (if available)
        eta: Estimated time remaining in seconds (if available)
        message: Human-readable status message
        details: Additional operation-specific details
        timestamp: When this progress info was created
    """
    operation: str
    status: ProgressStatus
    percentage: float = 0.0
    current_size: Optional[int] = None
    total_size: Optional[int] = None
    speed: Optional[float] = None
    eta: Optional[float] = None
    message: str = ""
    details: Dict[str, Any] = None
    timestamp: float = None

    def __post_init__(self):
        """Initialize timestamp if not provided."""
        if self.timestamp is None:
            self.timestamp = time.time()
        if self.details is None:
            self.details = {}


# Type alias for progress callback functions
ProgressCallback = Callable[[ProgressInfo], None]


class ProgressTracker(ABC):
    """
    Abstract base class for progress tracking.

    Provides common functionality for tracking progress of long-running operations
    and notifying callbacks about progress updates.
    """

    def __init__(self, operation_name: str):
        """
        Initialize the progress tracker.

        Args:
            operation_name: Name of the operation being tracked
        """
        self.operation_name = operation_name
        self.callbacks: list[ProgressCallback] = []
        self.current_progress: Optional[ProgressInfo] = None
        self.start_time: Optional[float] = None

    def add_callback(self, callback: ProgressCallback) -> None:
        """
        Add a progress callback.

        Args:
            callback: Function to call when progress updates
        """
        self.callbacks.append(callback)

    def remove_callback(self, callback: ProgressCallback) -> None:
        """
        Remove a progress callback.

        Args:
            callback: Function to remove from callbacks
        """
        if callback in self.callbacks:
            self.callbacks.remove(callback)

    def _notify_callbacks(self, progress: ProgressInfo) -> None:
        """
        Notify all callbacks about progress update.

        Args:
            progress: Progress information to send to callbacks
        """
        self.current_progress = progress
        for callback in self.callbacks:
            try:
                callback(progress)
            except Exception as e:
                # Log error but don't let callback failures stop progress tracking
                import logging
                logger = logging.getLogger(f"similubot.progress.{self.operation_name}")
                logger.error(f"Progress callback failed: {e}", exc_info=True)

    def start(self) -> None:
        """Start tracking progress."""
        self.start_time = time.time()
        progress = ProgressInfo(
            operation=self.operation_name,
            status=ProgressStatus.STARTING,
            message=f"Starting {self.operation_name}..."
        )
        self._notify_callbacks(progress)

    def update(
        self,
        percentage: Optional[float] = None,
        current_size: Optional[int] = None,
        total_size: Optional[int] = None,
        speed: Optional[float] = None,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        eta: Optional[float] = None
    ) -> None:
        """
        Update progress information.

        Args:
            percentage: Progress percentage (0-100)
            current_size: Current size processed in bytes
            total_size: Total size in bytes
            speed: Current speed in bytes/second
            message: Human-readable status message
            details: Additional operation-specific details
            eta: Estimated time remaining in seconds (optional, calculated if not provided)
        """
        # Calculate ETA if not provided and we have speed and remaining size
        if eta is None and speed and speed > 0 and total_size and current_size:
            remaining_size = total_size - current_size
            if remaining_size > 0:
                eta = remaining_size / speed

        progress = ProgressInfo(
            operation=self.operation_name,
            status=ProgressStatus.IN_PROGRESS,
            percentage=percentage or 0.0,
            current_size=current_size,
            total_size=total_size,
            speed=speed,
            eta=eta,
            message=message or f"{self.operation_name} in progress...",
            details=details or {}
        )
        self._notify_callbacks(progress)

    def complete(self, message: Optional[str] = None) -> None:
        """
        Mark operation as completed.

        Args:
            message: Completion message
        """
        progress = ProgressInfo(
            operation=self.operation_name,
            status=ProgressStatus.COMPLETED,
            percentage=100.0,
            message=message or f"{self.operation_name} completed successfully"
        )
        self._notify_callbacks(progress)

    def fail(self, error_message: str) -> None:
        """
        Mark operation as failed.

        Args:
            error_message: Error message describing the failure
        """
        progress = ProgressInfo(
            operation=self.operation_name,
            status=ProgressStatus.FAILED,
            message=f"{self.operation_name} failed: {error_message}"
        )
        self._notify_callbacks(progress)

    def cancel(self, message: Optional[str] = None) -> None:
        """
        Mark operation as cancelled.

        Args:
            message: Cancellation message
        """
        progress = ProgressInfo(
            operation=self.operation_name,
            status=ProgressStatus.CANCELLED,
            message=message or f"{self.operation_name} was cancelled"
        )
        self._notify_callbacks(progress)

    @abstractmethod
    def parse_output(self, output_line: str) -> bool:
        """
        Parse a line of output from the operation.

        Args:
            output_line: Line of output to parse

        Returns:
            True if the line contained progress information, False otherwise
        """
        pass

    def get_current_progress(self) -> Optional[ProgressInfo]:
        """
        Get the current progress information.

        Returns:
            Current progress info or None if no progress has been reported
        """
        return self.current_progress
