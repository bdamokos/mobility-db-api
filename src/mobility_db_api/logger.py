import logging
import sys
from typing import Optional

def setup_logger(name: str = "mobility_db_api", level: str = "INFO") -> logging.Logger:
    """Set up and configure logger.
    
    Args:
        name: Logger name, defaults to 'mobility_db_api'
        level: Logging level, defaults to 'INFO'. Must be one of:
               DEBUG, INFO, WARNING, ERROR, CRITICAL
    
    Returns:
        Configured logger instance
    
    Raises:
        ValueError: If the specified log level is invalid
    """
    # Create logger
    logger = logging.getLogger(name)
    
    # Validate and set log level
    try:
        log_level = getattr(logging, level.upper())
        logger.setLevel(log_level)
    except AttributeError:
        valid_levels = "DEBUG, INFO, WARNING, ERROR, CRITICAL"
        raise ValueError(f"Invalid log level: {level}. Must be one of: {valid_levels}")

    # Only add handler if the logger doesn't already have handlers
    if not logger.handlers:
        # Create console handler and set level
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)  # Handler should accept all messages

        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Add formatter to handler
        handler.setFormatter(formatter)
        
        # Add handler to logger
        logger.addHandler(handler)

    return logger 