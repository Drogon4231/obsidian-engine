"""Tests for core/log.py — structured logging system."""
import json
import logging
import os
import sys
import pytest
from unittest.mock import patch

from core.log import (
    get_logger,
    _reset_for_tests,
    _JsonFormatter,
    _ConsoleFormatter,
    _LazyStdoutHandler,
)


@pytest.fixture(autouse=True)
def reset_logging():
    """Reset logging state before and after each test."""
    _reset_for_tests()
    yield
    _reset_for_tests()


@pytest.mark.unit
class TestGetLogger:
    """Test the get_logger public API."""

    def test_returns_logger_instance(self):
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)

    def test_logger_name_prefixed_with_obsidian(self):
        logger = get_logger("my_module")
        assert logger.name == "obsidian.my_module"

    def test_strips_pipeline_prefix(self):
        logger = get_logger("pipeline.convert")
        assert logger.name == "obsidian.convert"

    def test_strips_core_prefix(self):
        logger = get_logger("core.quality_gates")
        assert logger.name == "obsidian.quality_gates"

    def test_same_name_returns_same_logger(self):
        a = get_logger("same")
        b = get_logger("same")
        assert a is b

    def test_root_obsidian_logger_configured(self):
        get_logger("trigger_setup")
        root = logging.getLogger("obsidian")
        assert root.level == logging.DEBUG
        assert root.propagate is False
        assert len(root.handlers) >= 2  # file + console


@pytest.mark.unit
class TestJsonFormatter:
    """Test JSON log line formatting."""

    def test_basic_format(self):
        fmt = _JsonFormatter()
        record = logging.LogRecord(
            name="obsidian.test", level=logging.INFO,
            pathname="", lineno=0, msg="hello", args=(), exc_info=None,
        )
        line = fmt.format(record)
        parsed = json.loads(line)
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "obsidian.test"
        assert parsed["msg"] == "hello"
        assert "ts" in parsed

    def test_extra_fields_included(self):
        fmt = _JsonFormatter()
        record = logging.LogRecord(
            name="obsidian.test", level=logging.INFO,
            pathname="", lineno=0, msg="stage done", args=(), exc_info=None,
        )
        record.stage = 5
        record.elapsed = 12.3
        line = fmt.format(record)
        parsed = json.loads(line)
        assert parsed["stage"] == 5
        assert parsed["elapsed"] == 12.3

    def test_exception_info_included(self):
        fmt = _JsonFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            record = logging.LogRecord(
                name="obsidian.test", level=logging.ERROR,
                pathname="", lineno=0, msg="fail", args=(),
                exc_info=sys.exc_info(),
            )
        line = fmt.format(record)
        parsed = json.loads(line)
        assert "exception" in parsed
        assert "ValueError" in parsed["exception"]


@pytest.mark.unit
class TestConsoleFormatter:
    """Test human-readable console formatting."""

    def test_returns_message_only(self):
        fmt = _ConsoleFormatter()
        record = logging.LogRecord(
            name="obsidian.test", level=logging.INFO,
            pathname="", lineno=0, msg="[Pipeline] Stage 5 complete", args=(), exc_info=None,
        )
        assert fmt.format(record) == "[Pipeline] Stage 5 complete"


@pytest.mark.unit
class TestLazyStdoutHandler:
    """Test that handler uses current sys.stdout on each emit."""

    def test_resolves_stdout_on_emit(self, capsys):
        handler = _LazyStdoutHandler()
        handler.setFormatter(_ConsoleFormatter())
        record = logging.LogRecord(
            name="obsidian.test", level=logging.INFO,
            pathname="", lineno=0, msg="captured", args=(), exc_info=None,
        )
        handler.emit(record)
        captured = capsys.readouterr()
        assert "captured" in captured.out


@pytest.mark.unit
class TestLogLevel:
    """Test OBSIDIAN_LOG_LEVEL env var controls console handler."""

    def test_default_level_is_info(self):
        get_logger("trigger")
        root = logging.getLogger("obsidian")
        console_handlers = [h for h in root.handlers if isinstance(h, _LazyStdoutHandler)]
        assert console_handlers
        assert console_handlers[0].level == logging.INFO

    def test_custom_level_from_env(self):
        with patch.dict(os.environ, {"OBSIDIAN_LOG_LEVEL": "WARNING"}):
            _reset_for_tests()
            get_logger("trigger")
            root = logging.getLogger("obsidian")
            console_handlers = [h for h in root.handlers if isinstance(h, _LazyStdoutHandler)]
            assert console_handlers
            assert console_handlers[0].level == logging.WARNING
