"""Stub executor for builds (creates a fake artifact)."""
from __future__ import annotations

import time
from pathlib import Path


class StubExecutor:
    """Fake build executor producing a dummy artifact file."""

    def __init__(self, builds_dir: Path) -> None:
        self._builds_dir = builds_dir
        self._builds_dir.mkdir(parents=True, exist_ok=True)

    def __call__(self, build: dict) -> dict:
        build_id = str(build["build_id"])
        time.sleep(2.0)

        out_dir = self._builds_dir / build_id
        out_dir.mkdir(parents=True, exist_ok=True)

        artifact = out_dir / f"{build_id}.tar.gz"
        artifact.write_bytes(b"stub-artifact\n")

        return {"path": str(artifact)}
