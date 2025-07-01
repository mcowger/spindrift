"""
Shared logging configuration for the Spindrift CNC library.

Provides a consistent, colored logging format across all modules.
Format: [LEVEL] [HH:MM:SS] message
"""

import logging
import sys
from typing import Optional


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colored log levels and consistent formatting."""

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RECV": "\033[38;2;0;188;212m",  #
        "SEND": "\033[38;2;255;112;67m",  #
        "RESET": "\033[0m",  # Reset color
    }

    def format(self, record):
        """Format log record with colored level and consistent structure."""
        # Get the color for this log level
        color = self.COLORS.get(record.levelname, '')

        # Format: [LEVEL] [HH:MM:SS] message
        # With colored level and left-aligned, padded to 8 characters
        colored_level = f"{color}[{record.levelname:<8}]{self.COLORS['RESET']}"
        time_str = f"[{self.formatTime(record, '%H:%M:%S')}]"

        return f"{colored_level} {time_str} {record.getMessage()}"


def setup_logging(
    level: int = logging.INFO,
    logger_name: Optional[str] = None,
    stream=None
) -> logging.Logger:
    """
    Set up logging with the standard Spindrift format.

    Args:
        level: Logging level (e.g., logging.INFO, logging.DEBUG)
        logger_name: Name for the logger (defaults to calling module)
        stream: Output stream (defaults to sys.stdout)

    Returns:
        Configured logger instance
    """
    if stream is None:
        stream = sys.stdout

    # Get or create logger
    logger = logging.getLogger(logger_name)

    # Clear any existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create handler with colored formatter
    handler = logging.StreamHandler(stream)
    formatter = ColoredFormatter()
    handler.setFormatter(formatter)

    # Configure logger
    logger.addHandler(handler)
    logger.setLevel(level)

    # Prevent propagation to avoid duplicate messages
    logger.propagate = False

    return logger


def configure_root_logging(level: int = logging.INFO):
    """
    Configure the root logger with Spindrift formatting.

    This is useful for applications that want all logging to use
    the consistent format.

    Args:
        level: Logging level for root logger
    """
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    formatter = ColoredFormatter()
    handler.setFormatter(formatter)

    root_logger.addHandler(handler)
    root_logger.setLevel(level)
