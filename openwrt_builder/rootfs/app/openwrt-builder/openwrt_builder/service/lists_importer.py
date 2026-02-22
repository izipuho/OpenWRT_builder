"""Helpers for importing package lists from external ImageBuilder list folders."""
from __future__ import annotations

import json
import re
from collections import OrderedDict
from pathlib import Path
from typing import Any

PACKAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.+-]*$")


def slugify(value: str) -> str:
    """Convert a string to a filesystem-safe list id."""
    raw = value.strip().lower()
    raw = re.sub(r"[^a-z0-9]+", "-", raw)
    raw = re.sub(r"-{2,}", "-", raw).strip("-")
    return raw or "list"


def human_name(value: str) -> str:
    """Build a readable list name from a slug/file stem."""
    parts = re.split(r"[-_.\s]+", value.strip())
    words = [part for part in parts if part]
    if not words:
        return "Imported list"
    return " ".join(word.capitalize() for word in words)


def uniq_keep_order(items: list[str]) -> list[str]:
    """Return unique values preserving first appearance order."""
    return list(OrderedDict.fromkeys(items))


def sanitize_pkg(token: str, source: Path) -> str | None:
    """Validate one package token."""
    value = token.strip()
    if not value:
        return None
    if not PACKAGE_RE.match(value):
        raise ValueError(f"{source}: invalid package token '{value}'")
    return value


def split_inline_comment(line: str) -> str:
    """Trim and strip comment tail from a source line."""
    value = line.strip()
    if not value:
        return ""
    if value.startswith("#"):
        return ""
    if " #" in value:
        value = value.split(" #", 1)[0].strip()
    return value


def _list_from_json_value(raw: Any, source: Path) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"{source}: expected array, got {type(raw).__name__}")
    out: list[str] = []
    for item in raw:
        token = sanitize_pkg(str(item), source)
        if token:
            out.append(token)
    return uniq_keep_order(out)


def parse_text_list(path: Path) -> tuple[list[str], list[str]]:
    """Parse text-style list files into include/exclude arrays."""
    include: list[str] = []
    exclude: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = split_inline_comment(raw_line)
        if not line:
            continue

        if line.startswith("include:"):
            token = sanitize_pkg(line.split(":", 1)[1], path)
            if token:
                include.append(token)
            continue
        if line.startswith("exclude:"):
            token = sanitize_pkg(line.split(":", 1)[1], path)
            if token:
                exclude.append(token)
            continue

        for chunk in line.split():
            value = chunk.strip()
            if not value:
                continue
            if value.startswith("+"):
                token = sanitize_pkg(value[1:], path)
                if token:
                    include.append(token)
                continue
            if value.startswith("-") or value.startswith("!"):
                token = sanitize_pkg(value[1:], path)
                if token:
                    exclude.append(token)
                continue
            token = sanitize_pkg(value, path)
            if token:
                include.append(token)

    return uniq_keep_order(include), uniq_keep_order(exclude)


def parse_json_list(path: Path) -> tuple[list[str], list[str], str | None]:
    """Parse JSON-style list files into include/exclude arrays and optional name."""
    payload = json.loads(path.read_text(encoding="utf-8"))

    if isinstance(payload, dict):
        nested = payload.get("list")
        if isinstance(nested, dict):
            include = _list_from_json_value(nested.get("include"), path)
            exclude = _list_from_json_value(nested.get("exclude"), path)
            name = payload.get("name")
            return include, exclude, str(name).strip() if isinstance(name, str) else None

        include = _list_from_json_value(
            payload.get("include") if "include" in payload else payload.get("packages"),
            path,
        )
        exclude = _list_from_json_value(
            payload.get("exclude") if "exclude" in payload else payload.get("packages_exclude"),
            path,
        )
        name = payload.get("name")
        return include, exclude, str(name).strip() if isinstance(name, str) else None

    if isinstance(payload, list):
        include = _list_from_json_value(payload, path)
        return include, [], None

    raise ValueError(f"{path}: unsupported JSON root type {type(payload).__name__}")


def parse_source(path: Path) -> tuple[list[str], list[str], str | None]:
    """Parse one source list file into include/exclude arrays and optional name."""
    if path.suffix.lower() == ".json":
        return parse_json_list(path)
    include, exclude = parse_text_list(path)
    return include, exclude, None


def collect_sources(source_dir: Path) -> list[Path]:
    """Collect all regular files recursively."""
    out: list[Path] = []
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file():
            continue
        out.append(path)
    return out


def build_output_payload(name: str, include: list[str], exclude: list[str]) -> dict[str, Any]:
    """Build a project-compatible list payload."""
    return {
        "name": name,
        "schema_version": 1,
        "list": {
            "include": include,
            "exclude": exclude,
        },
    }


def unique_id(base: str, used: set[str]) -> str:
    """Create a unique list id by appending numeric suffix when needed."""
    candidate = base
    n = 2
    while candidate in used:
        candidate = f"{base}-{n}"
        n += 1
    used.add(candidate)
    return candidate
