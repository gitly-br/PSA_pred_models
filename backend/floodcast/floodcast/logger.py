import logging
import sys

_debug_mode = False  # Module-level variable

def configure_logging(debug=False):
    """Configure logging level globally"""
    global _debug_mode
    _debug_mode = debug
    
    # Set level for all existing loggers in this module
    for logger_name in logging.Logger.manager.loggerDict:
        if logger_name.startswith('floodcast'):
            logger = logging.getLogger(logger_name)
            logger.setLevel(logging.DEBUG if debug else logging.INFO)

def get_logger(name=None):
    logger_name = name or "floodcast"
    logger = logging.getLogger(logger_name)
    
    if not logger.handlers:
        # Use global debug setting
        level = logging.DEBUG if _debug_mode else logging.INFO
        logger.setLevel(level)
        
        formatter = logging.Formatter("%(asctime)s %(levelname)-8s FLOODCAST %(message)s")
        
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        logger.propagate = False
    
    return logger
