"""
Structured logging for the Obsidian Archive pipeline.

Usage:
    from core.log import get_logger
    logger = get_logger(__name__)
    logger.info("Stage complete", stage=5, elapsed=12.3)

All pipeline print() calls should migrate to this module.
Outputs structured JSON lines to outputs/pipeline.log with rotation,
and human-readable lines to stderr (for terminal visibility).
"""
from __future__ import annotations

import json
import logging
import os
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
_BASE_DIR = Path(__file__).resolve().parent.parent
_LOG_DIR = _BASE_DIR / "outputs"
_LOG_FILE = _LOG_DIR / "pipeline.log"
_MAX_LOG_BYTES = 10 * 1024 * 1024  # 10 MB before rotation

_setup_lock = threading.Lock()
_initialized = False


# ── JSON Formatter ───────────────────────────────────────────────────────────

class _JsonFormatter(logging.Formatter):
    """Emit one JSON object per log line for machine parsing."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Merge extra structured fields (set via logger.info("msg", extra={...}))
        for key in ("stage", "elapsed", "component", "detail"):
            val = getattr(record, key, None)
            if val is not None:
                entry[key] = val
        if record.exc_info and record.exc_info[0] is not None:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


# ── Console Formatter ────────────────────────────────────────────────────────

class _ConsoleFormatter(logging.Formatter):
    """Human-readable format matching the existing [Pipeline] prefix style."""

    def format(self, record: logging.LogRecord) -> str:
        return record.getMessage()


class _LazyStdoutHandler(logging.StreamHandler):
    """StreamHandler that always writes to the *current* sys.stdout.

    Standard StreamHandler captures sys.stdout at creation time, which breaks
    pytest's capsys (capsys temporarily replaces sys.stdout).  This handler
    resolves sys.stdout on every emit() so captured output works correctly.
    """

    def __init__(self) -> None:
        super().__init__()

    def emit(self, record: logging.LogRecord) -> None:
        self.stream = sys.stdout
        super().emit(record)


# ── Setup ────────────────────────────────────────────────────────────────────

def _ensure_setup() -> None:
    """One-time setup of root 'obsidian' logger with file + console handlers."""
    global _initialized
    if _initialized:
        return
    with _setup_lock:
        if _initialized:
            return

        _LOG_DIR.mkdir(parents=True, exist_ok=True)

        root = logging.getLogger("obsidian")
        root.setLevel(logging.DEBUG)
        root.propagate = False

        # File handler — JSON lines with rotation
        from logging.handlers import RotatingFileHandler
        fh = RotatingFileHandler(
            str(_LOG_FILE), maxBytes=_MAX_LOG_BYTES, backupCount=2,
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(_JsonFormatter())
        root.addHandler(fh)

        # Console handler — human-readable, matches existing print() output
        # Uses _LazyStdoutHandler so pytest capsys can capture output
        ch = _LazyStdoutHandler()
        level_name = os.environ.get("OBSIDIAN_LOG_LEVEL", "INFO").upper()
        ch.setLevel(getattr(logging, level_name, logging.INFO))
        ch.setFormatter(_ConsoleFormatter())
        root.addHandler(ch)

        _initialized = True


# ── Public API ───────────────────────────────────────────────────────────────

def get_logger(name: str) -> logging.Logger:
    """Get a namespaced logger under the 'obsidian' hierarchy.

    Args:
        name: Module name, typically __name__. Gets prefixed with 'obsidian.'.

    Returns:
        A configured logging.Logger instance.
    """
    _ensure_setup()
    # Strip common prefixes to keep names short
    short = name.replace("pipeline.", "").replace("core.", "")
    return logging.getLogger(f"obsidian.{short}")


def _reset_for_tests() -> None:
    """Reset logging state — only for test teardown."""
    global _initialized
    root = logging.getLogger("obsidian")
    for h in root.handlers[:]:
        root.removeHandler(h)
        h.close()
    _initialized = False
