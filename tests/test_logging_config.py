"""Tests for the centralized logging configuration."""

from __future__ import annotations

import json
import logging

from tax_estimator.logging_config import (
    DevFormatter,
    JSONFormatter,
    request_id_var,
    setup_logging,
)


class TestJSONFormatter:
    """Tests for the JSON log formatter."""

    def test_produces_valid_json(self) -> None:
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Hello %s",
            args=("world",),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test.logger"
        assert parsed["message"] == "Hello world"
        assert "timestamp" in parsed

    def test_includes_request_id(self) -> None:
        formatter = JSONFormatter()
        token = request_id_var.set("abc-123-def")
        try:
            record = logging.LogRecord(
                name="test", level=logging.INFO, pathname="", lineno=0,
                msg="test", args=None, exc_info=None,
            )
            parsed = json.loads(formatter.format(record))
            assert parsed["request_id"] == "abc-123-def"
        finally:
            request_id_var.reset(token)

    def test_default_request_id_is_dash(self) -> None:
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="test", args=None, exc_info=None,
        )
        parsed = json.loads(formatter.format(record))
        assert parsed["request_id"] == "-"

    def test_includes_exception(self) -> None:
        formatter = JSONFormatter()
        try:
            raise ValueError("boom")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname="", lineno=0,
            msg="error", args=None, exc_info=exc_info,
        )
        parsed = json.loads(formatter.format(record))
        assert "exception" in parsed
        assert "ValueError: boom" in parsed["exception"]


class TestDevFormatter:
    """Tests for the development log formatter."""

    def test_human_readable_output(self) -> None:
        formatter = DevFormatter()
        record = logging.LogRecord(
            name="tax_estimator.access", level=logging.INFO, pathname="",
            lineno=0, msg="GET /health 200 1.5ms", args=None, exc_info=None,
        )
        output = formatter.format(record)
        assert "INFO" in output
        assert "tax_estimator.access" in output
        assert "GET /health 200 1.5ms" in output

    def test_truncates_request_id(self) -> None:
        formatter = DevFormatter()
        token = request_id_var.set("abcdefgh-1234-5678-9abc-def012345678")
        try:
            record = logging.LogRecord(
                name="test", level=logging.INFO, pathname="", lineno=0,
                msg="test", args=None, exc_info=None,
            )
            output = formatter.format(record)
            assert "[abcdefgh]" in output
        finally:
            request_id_var.reset(token)


class TestSetupLogging:
    """Tests for setup_logging function."""

    def _restore_logging(self) -> None:
        """Restore root logger to default state."""
        root = logging.getLogger()
        root.handlers.clear()
        root.setLevel(logging.WARNING)

    def test_debug_mode_uses_dev_formatter(self) -> None:
        try:
            setup_logging(debug=True)
            root = logging.getLogger()
            assert len(root.handlers) == 1
            assert isinstance(root.handlers[0].formatter, DevFormatter)
        finally:
            self._restore_logging()

    def test_production_mode_uses_json_formatter(self) -> None:
        try:
            setup_logging(debug=False)
            root = logging.getLogger()
            assert len(root.handlers) == 1
            assert isinstance(root.handlers[0].formatter, JSONFormatter)
        finally:
            self._restore_logging()

    def test_respects_log_level(self) -> None:
        try:
            setup_logging(debug=True, log_level="DEBUG")
            root = logging.getLogger()
            assert root.level == logging.DEBUG
        finally:
            self._restore_logging()
