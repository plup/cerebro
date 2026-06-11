"""JSON logging formatter tests."""

import io
import json
import logging
import logging.config

from cerebro.logging import JsonFormatter


def test_json_formatter_emits_fixed_fields() -> None:
    record = logging.LogRecord(
        "cerebro.test",
        logging.INFO,
        __file__,
        1,
        "hello %s",
        ("world",),
        None,
    )
    parsed = json.loads(JsonFormatter().format(record))
    assert set(parsed) == {"asctime", "name", "levelname", "levelno", "message"}
    assert parsed["name"] == "cerebro.test"
    assert parsed["levelname"] == "INFO"
    assert parsed["levelno"] == logging.INFO
    assert parsed["message"] == "hello world"


def test_dict_config_can_load_json_formatter() -> None:
    buf = io.StringIO()
    root = logging.getLogger()
    old_handlers = list(root.handlers)
    old_level = root.level
    try:
        logging.config.dictConfig(
            {
                "version": 1,
                "disable_existing_loggers": False,
                "formatters": {
                    "json": {
                        "format": "%(asctime)s %(name)s %(levelname)s %(levelno)s %(message)s",
                        "class": "cerebro.logging.JsonFormatter",
                    }
                },
                "handlers": {
                    "console": {
                        "class": "logging.StreamHandler",
                        "formatter": "json",
                        "stream": buf,
                    }
                },
                "root": {
                    "level": "INFO",
                    "handlers": ["console"],
                },
            }
        )
        logging.getLogger("cerebro.test").info("hello")
    finally:
        root.handlers.clear()
        root.handlers.extend(old_handlers)
        root.setLevel(old_level)

    parsed = json.loads(buf.getvalue().strip())
    assert parsed["name"] == "cerebro.test"
    assert parsed["levelname"] == "INFO"
    assert parsed["message"] == "hello"
