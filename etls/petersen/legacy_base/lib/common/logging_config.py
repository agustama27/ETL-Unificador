"""
Logging configuration module for ETL pipeline.

Supports configuration via YAML file or environment variables.
Default level is BASIC (minimal but informative).
Can be increased to INFO or DEBUG via configuration.
"""
import logging
import os
import yaml
from pathlib import Path
from typing import Optional

BASIC_LEVEL = 25


class BasicLevelFilter(logging.Filter):
    """Filter for BASIC level messages."""
    def filter(self, record):
        return record.levelno >= BASIC_LEVEL


def setup_logging(config_path: Optional[str] = None, log_level: Optional[str] = None) -> logging.Logger:
    """
    Setup logging configuration for ETL pipeline.
    
    Levels:
    - BASIC (default): Minimal but informative (start, end, bank processing, progress)
    - INFO: Detailed information (totals, parameters, paths, times)
    - DEBUG: Full debugging information
    
    Priority:
    1. log_level parameter (if provided)
    2. LOG_LEVEL environment variable
    3. logging.level in config file
    4. Default: BASIC
    
    Args:
        config_path: Path to YAML config file (optional)
        log_level: Log level override (BASIC, INFO, DEBUG, WARNING, ERROR)
    
    Returns:
        Configured logger instance
    """
    logging.addLevelName(BASIC_LEVEL, 'BASIC')
    
    def basic(self, message, *args, **kws):
        if self.isEnabledFor(BASIC_LEVEL):
            self._log(BASIC_LEVEL, message, args, **kws)
    
    logging.Logger.basic = basic
    
    logger = logging.getLogger('petersen_etl')
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    
    level_str = log_level
    
    if not level_str:
        level_str = os.getenv('LOG_LEVEL', '').upper()
    
    if not level_str and config_path:
        try:
            config_file = Path(config_path)
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    level_str = config.get('logging', {}).get('level', '').upper()
        except Exception:
            pass
    
    level_map = {
        'BASIC': BASIC_LEVEL,
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    
    level = level_map.get(level_str, BASIC_LEVEL)
    logger.setLevel(level)
    
    handler = logging.StreamHandler()
    handler.setLevel(level)
    
    if level <= logging.DEBUG:
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s')
    elif level <= logging.INFO:
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] - %(message)s')
    else:
        formatter = logging.Formatter('%(message)s')
    
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger

