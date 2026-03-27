"""Shared shutdown event for graceful thread termination."""
import threading

_shutdown_event = threading.Event()
