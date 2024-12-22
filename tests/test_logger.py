import logging
import pytest
from mobility_db_api.logger import setup_logger
from io import StringIO
import sys

@pytest.fixture
def capture_logs():
    """Fixture to capture log output"""
    string_io = StringIO()
    handler = logging.StreamHandler(string_io)
    handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
    
    previous_handlers = []
    
    def _capture_logs(logger_name="mobility_db_api"):
        logger = logging.getLogger(logger_name)
        # Store and remove existing handlers
        previous_handlers.extend(logger.handlers)
        logger.handlers.clear()
        # Add our capturing handler
        logger.addHandler(handler)
        return string_io
    
    yield _capture_logs
    
    # Restore previous handlers
    logger = logging.getLogger("mobility_db_api")
    logger.handlers.clear()
    for h in previous_handlers:
        logger.addHandler(h)

def test_default_logger():
    """Test logger with default settings"""
    logger = setup_logger()
    assert logger.name == "mobility_db_api"
    assert logger.level == logging.INFO
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0], logging.StreamHandler)
    assert logger.handlers[0].stream == sys.stdout

def test_custom_name():
    """Test logger with custom name"""
    logger = setup_logger(name="test_logger")
    assert logger.name == "test_logger"

def test_custom_level():
    """Test logger with custom level"""
    logger = setup_logger(level="DEBUG")
    assert logger.level == logging.DEBUG
    
    logger = setup_logger(level="WARNING")
    assert logger.level == logging.WARNING

def test_invalid_level():
    """Test logger with invalid level"""
    with pytest.raises(ValueError):
        setup_logger(level="INVALID")

def test_multiple_loggers():
    """Test creating multiple logger instances"""
    logger1 = setup_logger(name="logger1")
    logger2 = setup_logger(name="logger2")
    
    assert logger1.name == "logger1"
    assert logger2.name == "logger2"
    assert logger1 != logger2

def test_same_logger_reuse():
    """Test that getting the same logger name returns the same instance"""
    logger1 = setup_logger(name="test_logger")
    logger2 = setup_logger(name="test_logger")
    
    assert logger1 is logger2
    # Should not add another handler
    assert len(logger1.handlers) == 1

def test_log_levels(capture_logs):
    """Test that different log levels work correctly"""
    output = capture_logs()
    logger = setup_logger(level="DEBUG")
    
    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")
    
    logs = output.getvalue().strip().split('\n')
    assert len(logs) == 4
    assert "DEBUG - Debug message" in logs[0]
    assert "INFO - Info message" in logs[1]
    assert "WARNING - Warning message" in logs[2]
    assert "ERROR - Error message" in logs[3]

def test_log_filtering(capture_logs):
    """Test that log level filtering works"""
    output = capture_logs()
    logger = setup_logger(level="WARNING")
    
    logger.debug("Debug message")  # Should not appear
    logger.info("Info message")    # Should not appear
    logger.warning("Warning message")
    logger.error("Error message")
    
    logs = output.getvalue().strip().split('\n')
    assert len(logs) == 2
    assert "WARNING - Warning message" in logs[0]
    assert "ERROR - Error message" in logs[1]

def test_handler_formatter():
    """Test that log formatter is properly configured"""
    logger = setup_logger()
    formatter = logger.handlers[0].formatter
    
    # Test format string components
    assert "%(asctime)s" in formatter._fmt
    assert "%(name)s" in formatter._fmt
    assert "%(levelname)s" in formatter._fmt
    assert "%(message)s" in formatter._fmt
    
    # Test datetime format
    assert formatter.datefmt == "%Y-%m-%d %H:%M:%S" 