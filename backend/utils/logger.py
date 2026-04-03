import logging
import json
import sys

class StructuredLoggingFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "time": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "event": record.getMessage()
        }
        
        # Inject standard structural data if provided via extra kwargs
        for key in ["ship_id", "reason", "priority_score", "queue_position", "eta"]:
            if hasattr(record, key):
                log_obj[key] = getattr(record, key)
                
        return json.dumps(log_obj)

def get_engine_logger(name="DockingEngine"):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredLoggingFormatter())
        logger.addHandler(handler)
        
    return logger

logger = get_engine_logger()
