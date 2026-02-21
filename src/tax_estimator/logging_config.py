"""
Centralized logging configuration for the Tax Estimator.

Provides:
- JSON-formatted logs for production (machine-parseable)
- Human-readable logs for development
- Request context (request_id) injection via contextvars
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone

# Context variable for request_id — set by RequestIDMiddleware, read by formatters
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class JSONFormatter(logging.Formatter):
    """JSON log formatter for production environments."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, str] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get("-"),
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


class DevFormatter(logging.Formatter):
    """Human-readable log formatter for development."""

    def format(self, record: logging.LogRecord) -> str:
        rid = request_id_var.get("-")
        short_rid = rid[:8] if rid != "-" else "-"
        msg = record.getMessage()
        result = f"{record.levelname:<8} [{short_rid}] {record.name}: {msg}"
        if record.exc_info and record.exc_info[0] is not None:
            result += "\n" + self.formatException(record.exc_info)
        return result


def setup_logging(debug: bool = False, log_level: str = "INFO") -> None:
    """Configure logging for the application.

    Args:
        debug: If True, use human-readable formatter. If False, use JSON.
        log_level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    root = logging.getLogger()
    level = getattr(logging, log_level.upper(), logging.INFO)
    root.setLevel(level)

    # Remove existing handlers to avoid duplicates on re-init
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(DevFormatter() if debug else JSONFormatter())
    root.addHandler(handler)

    # Silence noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
