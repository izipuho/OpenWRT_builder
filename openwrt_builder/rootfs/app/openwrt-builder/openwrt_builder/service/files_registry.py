"""Registry helpers for uploaded files and their target directories."""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from openwrt_builder.service.models import (
    FileDescriptorModel,
    FileDescriptorsIndexModel,
    FileRowModel,
    validate_rel_dir,
    validate_rel_path,
)


def _normalize_rel_path(path: str) -> str:
    """Return a normalized relative file path or raise ``ValueError``."""
    return validate_rel_path(path)


def _normalize_rel_dir(path: str) -> str:
    """Return a normalized relative directory path or raise ``ValueError``."""
    return validate_rel_dir(path)


def _mtime_utc(path: Path) -> str:
    """Return file mtime in UTC (RFC3339-like)."""
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat().replace("+00:00", "Z")


class FilesRegistry:
    """Manage uploaded files and metadata (source_path/target_path)."""

    def __init__(self, files_dir: Path) -> None:
        self._files_dir = files_dir.resolve()
        self._descriptors_path = self._files_dir / ".descriptors.json"

    def _read_descriptors(self) -> list[dict]:
        """Load valid descriptor rows from disk."""
        if not self._descriptors_path.exists():
            return []
        try:
            with self._descriptors_path.open("r", encoding="utf-8") as fp:
                payload = json.load(fp)
        except (OSError, json.JSONDecodeError):
            return []

        items = payload.get("files") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            return []

        rows: list[dict] = []
        for item in items:
            try:
                rows.append(FileDescriptorModel.model_validate(item).model_dump())
            except ValidationError:
                continue
        return rows

    def _write_descriptors(self, rows: list[dict]) -> None:
        """Persist descriptors atomically."""
        self._files_dir.mkdir(parents=True, exist_ok=True)
        tmp = self._descriptors_path.with_suffix(".tmp")
        payload = FileDescriptorsIndexModel.model_validate({"schema_version": 1, "files": rows}).model_dump()
        with tmp.open("w", encoding="utf-8") as fp:
            json.dump(payload, fp, ensure_ascii=True, indent=2, sort_keys=True)
            fp.write("\n")
        tmp.replace(self._descriptors_path)

    def _sync(self) -> list[dict]:
        """Sync descriptor list against files currently present on disk."""
        self._files_dir.mkdir(parents=True, exist_ok=True)
        existing_sources = sorted(
            p.relative_to(self._files_dir).as_posix()
            for p in self._files_dir.rglob("*")
            if p.is_file() and p.name != self._descriptors_path.name
        )

        current_rows = self._read_descriptors()
        by_source: dict[str, dict] = {}
        for row in current_rows:
            source = row["source_path"]
            if source not in existing_sources or source in by_source:
                continue
            by_source[source] = row

        changed = False
        for source in existing_sources:
            if source in by_source:
                continue
            by_source[source] = {
                "source_path": source,
                "target_path": _normalize_rel_dir(Path(source).parent.as_posix()),
            }
            changed = True

        rows = [by_source[source] for source in existing_sources]
        if changed or rows != current_rows:
            self._write_descriptors(rows)
        return rows

    def _build_row(self, descriptor: dict) -> dict:
        source = descriptor["source_path"]
        abs_path = (self._files_dir / source).resolve()
        return FileRowModel.model_validate(
            {
                "source_path": source,
                "target_path": descriptor["target_path"],
                "size": abs_path.stat().st_size,
                "updated_at": _mtime_utc(abs_path),
            }
        ).model_dump()

    def list(self) -> list[dict]:
        """Return all file rows sorted by ``updated_at`` descending."""
        rows = [self._build_row(row) for row in self._sync()]
        rows.sort(key=lambda x: x["updated_at"], reverse=True)
        return rows

    def upload(self, file: Any, target_path: str | None = None) -> dict:
        """Store one uploaded file and return its descriptor row."""
        source = _normalize_rel_path(file.filename or "")
        default_dir = Path(source).parent.as_posix()
        target = _normalize_rel_dir(target_path if (target_path or "").strip() else default_dir)

        abs_path = (self._files_dir / source).resolve()
        if self._files_dir != abs_path and self._files_dir not in abs_path.parents:
            raise ValueError("invalid_path")

        self._files_dir.mkdir(parents=True, exist_ok=True)
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        with abs_path.open("wb") as fp:
            shutil.copyfileobj(file.file, fp)

        rows = self._sync()
        for row in rows:
            if row["source_path"] != source:
                continue
            row["target_path"] = target
            self._write_descriptors(rows)
            return self._build_row(row)
        raise FileNotFoundError("file_not_found")

    def update_meta(self, file_path: str, target_path: str) -> dict:
        """Update ``target_path`` for one descriptor by ``source_path``."""
        source = _normalize_rel_path(file_path)
        target = _normalize_rel_dir(target_path)

        rows = self._sync()
        for row in rows:
            if row["source_path"] != source:
                continue
            row["target_path"] = target
            self._write_descriptors(rows)
            return self._build_row(row)
        raise FileNotFoundError("file_not_found")

    def delete(self, file_path: str) -> dict:
        """Delete source file by relative path."""
        source = _normalize_rel_path(file_path)
        abs_path = (self._files_dir / source).resolve()
        if self._files_dir != abs_path and self._files_dir not in abs_path.parents:
            raise ValueError("invalid_path")
        if not abs_path.exists() or not abs_path.is_file():
            raise FileNotFoundError("file_not_found")

        abs_path.unlink()
        remaining = len(self._sync())
        return {"source_path": source, "deleted": True, "remaining": remaining}
