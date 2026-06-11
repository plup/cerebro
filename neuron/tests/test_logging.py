"""JSON logging formatter tests."""

import io
import json
import logging
import logging.config
import unittest

from neuron.logging import JsonFormatter


class JsonFormatterTest(unittest.TestCase):
    def test_json_formatter_emits_fixed_fields(self) -> None:
        record = logging.LogRecord(
            "neuron.test",
            logging.INFO,
            __file__,
            1,
            "hello %s",
            ("world",),
            None,
        )
        parsed = json.loads(JsonFormatter().format(record))
        self.assertEqual(
            set(parsed),
            {"asctime", "name", "levelname", "levelno", "message"},
        )
        self.assertEqual(parsed["name"], "neuron.test")
        self.assertEqual(parsed["levelname"], "INFO")
        self.assertEqual(parsed["levelno"], logging.INFO)
        self.assertEqual(parsed["message"], "hello world")

    def test_dict_config_can_load_json_formatter(self) -> None:
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
                            "class": "neuron.logging.JsonFormatter",
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
            logging.getLogger("neuron.test").info("hello")
        finally:
            root.handlers.clear()
            root.handlers.extend(old_handlers)
            root.setLevel(old_level)

        parsed = json.loads(buf.getvalue().strip())
        self.assertEqual(parsed["name"], "neuron.test")
        self.assertEqual(parsed["levelname"], "INFO")
        self.assertEqual(parsed["message"], "hello")


if __name__ == "__main__":
    unittest.main()
