#!/usr/bin/env python3
"""Convert external ImageBuilder package lists into OpenWRT Builder list JSON files."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_APP_SRC = Path(__file__).resolve().parents[1] / "rootfs/app/openwrt-builder"
if str(_APP_SRC) not in sys.path:
    sys.path.insert(0, str(_APP_SRC))

from openwrt_builder.service.lists_importer import (
    build_output_payload,
    collect_sources,
    human_name,
    parse_source,
    slugify,
    unique_id,
)


def now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def convert(source_dir: Path, output_dir: Path, overwrite: bool, dry_run: bool) -> int:
    sources = collect_sources(source_dir)
    if not sources:
        print(f"No supported list files found in: {source_dir}")
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    processed = 0
    used_ids: set[str] = set()

    for source in sources:
        include, exclude, name_from_source = parse_source(source)
        rel_stem = source.relative_to(source_dir).with_suffix("").as_posix()
        list_id = unique_id(slugify(rel_stem), used_ids)
        name = name_from_source or human_name(source.stem)
        payload = build_output_payload(name=name, include=include, exclude=exclude)
        payload["updated_at"] = now_z()
        out_path = output_dir / f"{list_id}.json"

        if out_path.exists() and not overwrite:
            print(f"SKIP {source} -> {out_path} (exists, use --overwrite)")
            continue

        if dry_run:
            print(f"DRY  {source} -> {out_path} (include={len(include)} exclude={len(exclude)})")
            processed += 1
            continue

        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"OK   {source} -> {out_path} (include={len(include)} exclude={len(exclude)})")
        processed += 1

    print(f"Done: {processed} list(s) processed")
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
