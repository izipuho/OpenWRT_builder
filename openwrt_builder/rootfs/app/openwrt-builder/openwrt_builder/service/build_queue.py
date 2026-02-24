"""Persistent FIFO queue for build IDs."""
from __future__ import annotations

import fcntl
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from openwrt_builder.service.profiles_registry import BaseRegistry


class BuildQueue:
    """File-backed FIFO queue for build identifiers."""

    def __init__(self, queue_path: Path) -> None:
        """Initialize queue storage and create an empty queue file if needed."""
        self._path = queue_path
        self._lock_path = self._path.with_name(f"{self._path.name}.lock")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._locked():
            if not self._path.exists():
                self._write({"items": [], "updated_at": BaseRegistry._now_z()})

    @contextmanager
    def _locked(self) -> Iterator[None]:
        """Acquire inter-process exclusive lock for queue operations."""
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock_path.open("a+", encoding="utf-8") as lock_fp:
            fcntl.flock(lock_fp.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_fp.fileno(), fcntl.LOCK_UN)

    def _read(self) -> dict:
        """Load queue payload from disk and normalize malformed content."""
        try:
            with self._path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            data = {"items": [], "updated_at": BaseRegistry._now_z()}
        if not isinstance(data, dict):
            data = {"items": [], "updated_at": BaseRegistry._now_z()}
        items = data.get("items")
        if not isinstance(items, list):
            items = []
        data["items"] = [x for x in items if isinstance(x, str) and x]
        if not isinstance(data.get("updated_at"), str):
            data["updated_at"] = BaseRegistry._now_z()
        return data

    def _write(self, data: dict) -> None:
        """Atomically write queue payload with refreshed update timestamp."""
        data["updated_at"] = BaseRegistry._now_z()
        BaseRegistry._atomic_write_json(self._path, data)

    def list(self) -> list[str]:
        """Return current queued build IDs (FIFO order)."""
        with self._locked():
            return list(self._read()["items"])

    def enqueue(self, build_id: str) -> bool:
        """Enqueue build_id if not already present. Returns True if added."""
        if not isinstance(build_id, str) or not build_id:
            raise ValueError("build_id")
        with self._locked():
            data = self._read()
            items: list[str] = data["items"]
            if build_id in items:
                return False
            items.append(build_id)
            self._write(data)
            return True

    def dequeue(self) -> str | None:
        """Dequeue next build_id (FIFO). Returns None if empty."""
        with self._locked():
            data = self._read()
            items: list[str] = data["items"]
            if not items:
                return None
            build_id = items.pop(0)
            self._write(data)
            return build_id

    def remove(self, build_id: str) -> bool:
        """Remove build_id from queue. Returns True if removed."""
        if not isinstance(build_id, str) or not build_id:
            raise ValueError("build_id")
        with self._locked():
            data = self._read()
            items: list[str] = data["items"]
            before = len(items)
            items[:] = [x for x in items if x != build_id]
            removed = len(items) != before
            if removed:
                self._write(data)
            return removed
