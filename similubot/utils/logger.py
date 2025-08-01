"""Logging utility for SimiluBot."""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from typing import Optional

def setup_logger(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    max_size: int = 10485760,  # 10 MB
    backup_count: int = 5
) -> None:
    """
    Set up the logger for the application.

    Args:
        log_level: The logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to the log file. If None, logs will only go to console
        max_size: Maximum size of log file before rotation (in bytes)
        backup_count: Number of backup log files to keep

    Raises:
        ValueError: If an invalid log level is provided
    """
    # Validate log level
    log_level = log_level.upper()
    if not hasattr(logging, log_level):
        raise ValueError(f"Invalid log level: {log_level}. Must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL")

    # Create logger
    logger = logging.getLogger("similubot")

    # Clear existing handlers to avoid duplicates
    logger.handlers.clear()

    # Set log level
    logger.setLevel(getattr(logging, log_level))

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Create file handler if log_file is specified
    if log_file:
        try:
            # Ensure log directory exists
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)

            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_size,
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setLevel(getattr(logging, log_level))
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

            # Log setup confirmation to file
            logger.debug(f"File logging enabled: {log_file}")

        except (OSError, IOError) as e:
            # If file logging fails, log to console only
            logger.warning(f"Failed to set up file logging to {log_file}: {e}")
            logger.warning("Continuing with console logging only")

    # Prevent propagation to root logger to avoid duplicate messages
    logger.propagate = False

    # Log debug message to confirm logger setup
    logger.debug(f"Logger initialized - Level: {log_level}, File: {log_file or 'Console only'}")
    logger.info("Logging system configured successfully")
