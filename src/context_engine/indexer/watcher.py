"""File watcher with debouncing using watchdog."""
import asyncio
import threading
import time
from pathlib import Path
from typing import Callable, Coroutine
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent


class _DebouncedHandler(FileSystemEventHandler):
    def __init__(self, on_change, debounce_ms, ignore_patterns, loop):
        self._on_change = on_change
        self._debounce_s = debounce_ms / 1000.0
        self._ignore_patterns = ignore_patterns
        self._loop = loop
        self._pending: dict[str, float] = {}
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None

    def _should_ignore(self, path: str) -> bool:
        for pattern in self._ignore_patterns:
            if pattern in path:
                return True
        return False

    def on_any_event(self, event):
        if event.is_directory:
            return
        path = event.src_path
        if self._should_ignore(path):
            return
        with self._lock:
            self._pending[path] = time.time()
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(self._debounce_s, self._flush)
            self._timer.start()

    def _flush(self):
        with self._lock:
            paths = list(self._pending.keys())
            self._pending.clear()
        for path in paths:
            asyncio.run_coroutine_threadsafe(self._on_change(path), self._loop)


class FileWatcher:
    def __init__(self, watch_dir, on_change, debounce_ms=500, ignore_patterns=None):
        self._watch_dir = watch_dir
        self._on_change = on_change
        self._debounce_ms = debounce_ms
        self._ignore_patterns = ignore_patterns or []
        self._observer = None
        self._handler = None

    def start(self):
        # Get the running loop at start() time, since we're called from within
        # an async context (pytest-asyncio), so the loop is already running.
        loop = asyncio.get_event_loop()
        self._handler = _DebouncedHandler(
            on_change=self._on_change,
            debounce_ms=self._debounce_ms,
            ignore_patterns=self._ignore_patterns,
            loop=loop,
        )
        self._observer = Observer()
        self._observer.schedule(self._handler, self._watch_dir, recursive=True)
        self._observer.start()

    def stop(self):
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=2)
