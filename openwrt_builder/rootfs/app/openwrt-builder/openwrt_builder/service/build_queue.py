"""Persistent queue for build IDs.

Stores the queue on disk as JSON to survive process restarts.
"""
from __future__ import annotations

import json
from pathlib import Path

from openwrt_builder.service.profiles_registry import BaseRegistry


class BuildQueue:
    """File-backed queue with simple list semantics.

    Each operation reads the JSON payload, mutates the list of build IDs,
    and writes it back atomically.
    """

    def __init__(self, path: Path) -> None:
        """Create a queue bound to the given JSON file path."""
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> dict:
        """Load the current queue payload, initializing defaults if missing."""
        if not self._path.exists():
            return {"items": [], "updated_at": BaseRegistry._now_z()}
        with self._path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _write(self, payload: dict) -> None:
        """Persist the queue payload atomically."""
        BaseRegistry._atomic_write_json(self._path, payload)

    def enqueue(self, build_id: str) -> bool:
        """Add a build ID to the queue if not already present."""
        data = self._read()
        items = list(data.get("items") or [])
        if build_id in items:
            return False
        items.append(build_id)
        data["items"] = items
        data["updated_at"] = BaseRegistry._now_z()
        self._write(data)
        return True

    def dequeue(self) -> str | None:
        """Pop the next build ID or return None when empty."""
        data = self._read()
        items = list(data.get("items") or [])
        if not items:
            return None
        build_id = items.pop(0)
        data["items"] = items
        data["updated_at"] = BaseRegistry._now_z()
        self._write(data)
        return build_id

    def remove(self, build_id: str) -> bool:
        """Remove a build ID from the queue if it exists."""
        data = self._read()
        items = list(data.get("items") or [])
        if build_id not in items:
            return False
        items = [item for item in items if item != build_id]
        data["items"] = items
        data["updated_at"] = BaseRegistry._now_z()
        self._write(data)
        return True

    def list(self) -> list[str]:
        """Return the current queued build IDs in order."""
        data = self._read()
        return list(data.get("items") or [])
