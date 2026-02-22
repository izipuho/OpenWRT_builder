#!/usr/bin/env python3
"""Convert external ImageBuilder package lists into OpenWRT Builder list JSON files."""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Reuse existing project helpers from the backend package.
_APP_SRC = Path(__file__).resolve().parents[1] / "rootfs/app/openwrt-builder"
if str(_APP_SRC) not in sys.path:
    sys.path.insert(0, str(_APP_SRC))

try:
    from openwrt_builder.service.profiles_registry import BaseRegistry as _BaseRegistry
except Exception:
    _BaseRegistry = None


def now_z() -> str:
    if _BaseRegistry is not None:
        return _BaseRegistry._now_z()
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def slugify(value: str) -> str:
    if _BaseRegistry is not None:
        return _BaseRegistry._slug(value) or "list"
    raw = value.strip().lower()
    raw = re.sub(r"[^a-z0-9]+", "-", raw)
    raw = re.sub(r"-{2,}", "-", raw).strip("-")
    return raw or "list"


PACKAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.+-]*$")


def human_name(value: str) -> str:
    parts = re.split(r"[-_.\s]+", value.strip())
    words = [p for p in parts if p]
    if not words:
        return "Imported list"
    return " ".join(word.capitalize() for word in words)


def uniq_keep_order(items: list[str]) -> list[str]:
    return list(OrderedDict.fromkeys(items))


def sanitize_pkg(token: str, source: Path) -> str | None:
    value = token.strip()
    if not value:
        return None
    if not PACKAGE_RE.match(value):
        raise ValueError(f"{source}: invalid package token '{value}'")
    return value


def split_inline_comment(line: str) -> str:
    value = line.strip()
    if not value:
        return ""
    if value.startswith("#"):
        return ""
    if " #" in value:
        value = value.split(" #", 1)[0].strip()
    return value


def parse_text_list(path: Path) -> tuple[list[str], list[str]]:
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

        chunks = line.split()
        for chunk in chunks:
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


def parse_json_list(path: Path) -> tuple[list[str], list[str], str | None]:
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
    if path.suffix.lower() == ".json":
        return parse_json_list(path)
    include, exclude = parse_text_list(path)
    return include, exclude, None


def build_output_payload(name: str, include: list[str], exclude: list[str]) -> dict[str, Any]:
    return {
        "name": name,
        "schema_version": 1,
        "updated_at": now_z(),
        "list": {
            "include": include,
            "exclude": exclude,
        },
    }


def collect_sources(source_dir: Path) -> list[Path]:
    allowed = {".txt", ".list", ".lst", ".conf", ".cfg", ".json"}
    out: list[Path] = []
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.name.startswith("."):
            continue
        if path.suffix.lower() not in allowed:
            continue
        out.append(path)
    return out


def convert(source_dir: Path, output_dir: Path, overwrite: bool, dry_run: bool) -> int:
    sources = collect_sources(source_dir)
    if not sources:
        print(f"No supported list files found in: {source_dir}")
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    written = 0

    for source in sources:
        include, exclude, name_from_source = parse_source(source)

        stem = source.stem
        list_id = slugify(stem)
        name = name_from_source or human_name(stem)

        payload = build_output_payload(name=name, include=include, exclude=exclude)
        out_path = output_dir / f"{list_id}.json"

        if out_path.exists() and not overwrite:
            print(f"SKIP {source} -> {out_path} (exists, use --overwrite)")
            continue

        if dry_run:
            print(
                f"DRY  {source} -> {out_path} "
                f"(include={len(include)} exclude={len(exclude)})"
            )
            written += 1
            continue

        out_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(
            f"OK   {source} -> {out_path} "
            f"(include={len(include)} exclude={len(exclude)})"
        )
        written += 1

    print(f"Done: {written} list(s) processed")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Convert external ImageBuilder package lists into "
            "openwrt_builder/data/lists JSON format."
        )
    )
    parser.add_argument(
        "--source-dir",
        required=True,
        type=Path,
        help="Directory with source list files (e.g. cloned repo/lists).",
    )
    parser.add_argument(
        "--output-dir",
        default=Path("openwrt_builder/data/lists"),
        type=Path,
        help="Destination directory for converted list JSON files.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing output JSON files.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only show what would be converted.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return convert(
        source_dir=args.source_dir.resolve(),
        output_dir=args.output_dir.resolve(),
        overwrite=args.overwrite,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
