"""Tests for core/shutdown.py — shared shutdown event."""
import threading
import pytest

from core.shutdown import _shutdown_event


@pytest.mark.unit
class TestShutdownEvent:
    """Verify the shared shutdown event behaves correctly."""

    def setup_method(self):
        _shutdown_event.clear()

    def test_event_is_threading_event(self):
        assert isinstance(_shutdown_event, threading.Event)

    def test_not_set_by_default(self):
        assert not _shutdown_event.is_set()

    def test_set_and_check(self):
        _shutdown_event.set()
        assert _shutdown_event.is_set()

    def test_clear_resets(self):
        _shutdown_event.set()
        _shutdown_event.clear()
        assert not _shutdown_event.is_set()

    def test_wait_returns_immediately_when_set(self):
        _shutdown_event.set()
        result = _shutdown_event.wait(timeout=0.01)
        assert result is True

    def test_wait_times_out_when_not_set(self):
        result = _shutdown_event.wait(timeout=0.01)
        assert result is False
