"""Single-runner lock based on fcntl locks."""
from __future__ import annotations

import os
from pathlib import Path

import fcntl


class RunnerLock:
    """Acquire an exclusive lock to ensure a single runner instance."""

    def __init__(self, runtime_dir: Path) -> None:
        self._runtime_dir = runtime_dir
        self._runtime_dir.mkdir(parents=True, exist_ok=True)
        self._lock_path = runtime_dir / "runner.lock"
        self._pid_path = runtime_dir / "runner.pid"
        self._file = None

    def acquire(self) -> bool:
        self._file = self._lock_path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(self._file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self._file.close()
            self._file = None
            return False
        self._pid_path.write_text(f"{os.getpid()}\n", encoding="utf-8")
        return True

    def release(self) -> None:
        if self._file is None:
            return
        try:
            fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
        finally:
            self._file.close()
            self._file = None
            if self._pid_path.exists():
                self._pid_path.unlink()
