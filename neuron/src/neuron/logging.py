"""Logging formatters shipped with Cerebro neuron."""

from __future__ import annotations

import json
import logging
from typing import Any


class JsonFormatter(logging.Formatter):
    """One JSON object per log line with fixed standard logging fields."""

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        asctime = self.formatTime(record, self.datefmt)
        payload: dict[str, Any] = {
            "asctime": asctime,
            "name": record.name,
            "levelname": record.levelname,
            "levelno": record.levelno,
            "message": record.message,
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        elif record.exc_text:
            payload["exc_info"] = record.exc_text
        try:
            return json.dumps(payload, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            return json.dumps(
                {
                    "asctime": asctime,
                    "name": record.name,
                    "levelname": record.levelname,
                    "levelno": record.levelno,
                    "message": record.message,
                    "exc_info": payload.get("exc_info"),
                    "note": "log_format_fallback",
                },
                ensure_ascii=False,
                default=str,
            )
