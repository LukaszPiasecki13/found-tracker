"""Application logging setup.

Configured once at startup so every module can use ``logging.getLogger(__name__)``
without caring about handlers or formatting.
"""

import json
import logging
import sys
import time
from typing import Any

_CONFIGURED = False

# Keys from LogRecord that should not appear in JSON output
_RESERVED_RECORD_KEYS = frozenset(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__
)


class JsonFormatter(logging.Formatter):
    """One JSON object per line, for log aggregation in hosted environments."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key not in _RESERVED_RECORD_KEYS:
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO", json_output: bool = False) -> None:
    """Install a single stdout handler on the root logger. Idempotent."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    handler = logging.StreamHandler(sys.stdout)
    formatter: logging.Formatter
    if json_output:
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s UTC %(levelname)-8s %(name)s: %(message)s"
        )
    # `asctime`/`timestamp` default to the process's local time, which silently
    # matches UTC only as long as the host's TZ happens to be UTC. Pinning the
    # converter makes every log line unambiguous regardless of where it runs.
    formatter.converter = time.gmtime
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Uvicorn installs its own handlers; let records propagate to ours instead.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True

    _CONFIGURED = True
