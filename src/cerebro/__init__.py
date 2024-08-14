"""Configure logging."""
import logging
import json
from os import environ

class JsonFormatter(logging.Formatter):
    """Format output message in JSON."""
    def format(self, record: logging.LogRecord) -> str:
        super().format(record)
        output = {k: str(v) for k, v in record.__dict__.items()}
        return json.dumps(output)

try:
    if environ.get('CEREBRO_LOG_FORMAT') == 'json':
        # apply the formatter to the root logger
        stream = logging.StreamHandler()
        stream.setFormatter(JsonFormatter())
        logging.getLogger().addHandler(stream)
except:
    logging.error('Error when configuring the logger')
