"""Structured JSON logging setup.

All ingestion runs are unattended (scheduled CI jobs), so logs are the only
observability surface. Every log line is emitted as one JSON object per line
to make them greppable and machine-parseable in CI log viewers, rather than
free-form text.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

from pythonjsonlogger import jsonlogger

_CONFIGURED = False


class _RunContextFilter(logging.Filter):
    """Attaches a shared context (e.g. run_id, source) to every log record."""

    def __init__(self) -> None:
        super().__init__()
        self.context: dict[str, Any] = {}

    def filter(self, record: logging.LogRecord) -> bool:
        for key, value in self.context.items():
            setattr(record, key, value)
        return True


_run_context_filter = _RunContextFilter()


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger for structured JSON output. Safe to call more than once."""
    global _CONFIGURED
    root = logging.getLogger()
    root.setLevel(level.upper())

    if _CONFIGURED:
        return

    handler = logging.StreamHandler(stream=sys.stdout)
    formatter = jsonlogger.JsonFormatter(  # type: ignore[no-untyped-call]
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level"},
    )
    handler.setFormatter(formatter)
    handler.addFilter(_run_context_filter)
    root.handlers = [handler]
    _CONFIGURED = True


def set_run_context(**context: Any) -> None:
    """Attach fields (e.g. ingestion_run_id, source) to every subsequent log line."""
    _run_context_filter.context.update(context)


def clear_run_context() -> None:
    _run_context_filter.context.clear()


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
