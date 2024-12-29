import logging
import sys
from typing import Optional

# Custom formatter with colors
class ColorFormatter(logging.Formatter):
    """Custom formatter with colors for different log levels"""
    
    grey = "\x1b[38;21m"
    blue = "\x1b[38;5;39m"
    yellow = "\x1b[38;5;226m"
    red = "\x1b[38;5;196m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    FORMATS = {
        logging.DEBUG: grey + "%(asctime)s - %(name)s - %(levelname)s - %(message)s" + reset,
        logging.INFO: blue + "%(asctime)s - %(name)s - %(levelname)s - %(message)s" + reset,
        logging.WARNING: yellow + "%(asctime)s - %(name)s - %(levelname)s - %(message)s" + reset,
        logging.ERROR: red + "%(asctime)s - %(name)s - %(levelname)s - %(message)s" + reset,
        logging.CRITICAL: bold_red + "%(asctime)s - %(name)s - %(levelname)s - %(message)s" + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)

def setup_logger(name: Optional[str] = None) -> logging.Logger:
    """Setup and return a logger instance"""
    
    # Get or create logger
    logger = logging.getLogger(name or __name__)
    
    # Only add handler if the logger doesn't already have handlers
    if not logger.handlers:
        # Create console handler with color formatting
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(ColorFormatter())
        
        # Add handlers to logger
        logger.addHandler(console_handler)
        
        # Set level
        logger.setLevel(logging.INFO)
        
        # Prevent propagation to root logger
        logger.propagate = False
    
    return logger

# Create default logger instance
logger = setup_logger("api")