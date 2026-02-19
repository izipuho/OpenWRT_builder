"""Executor that runs OpenWrt ImageBuilder commands."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path


_SAFE_VALUE_RE = re.compile(r"^[A-Za-z0-9_.@:+\-/]+$")
_SAFE_PART_RE = re.compile(r"^[A-Za-z0-9_.+-]+$")


class ImageBuilderExecutor:
    """Thin wrapper over external imagebuilder Makefile-based frontend."""

    def __init__(self, builds_dir: Path, files_dir: Path, cache_dir: Path, wrapper_dir: Path) -> None:
        self._builds_dir = builds_dir
        self._files_dir = files_dir
        self._cache_dir = cache_dir
        self._wrapper_dir = wrapper_dir
        self._builds_dir.mkdir(parents=True, exist_ok=True)
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _safe_make_arg(name: str, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"invalid_{name}")
        value = value.strip()
        if not _SAFE_VALUE_RE.match(value):
            raise ValueError(f"invalid_{name}")
        return value

    @staticmethod
    def _pick_artifact(output_dir: Path) -> Path:
        preferred = [".bin", ".img.gz", ".tar.gz", ".itb", ".trx"]
        files = sorted(p for p in output_dir.rglob("*") if p.is_file())
        if not files:
            raise RuntimeError("artifact_not_found")
        for suffix in preferred:
            for file in files:
                if file.name.endswith(suffix):
                    return file
        return files[0]

    @staticmethod
    def _safe_part(name: str, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"invalid_{name}")
        value = value.strip()
        if not _SAFE_PART_RE.match(value):
            raise ValueError(f"invalid_{name}")
        return value

    @classmethod
    def _parse_target(cls, target_raw: str) -> tuple[str, str]:
        parts = [p for p in str(target_raw).strip().split("/") if p]
        if len(parts) != 2:
            raise ValueError("invalid_target_format_expected_target_subtarget")
        return cls._safe_part("target", parts[0]), cls._safe_part("subtarget", parts[1])

    @staticmethod
    def _write_build_config(
        cfg_dir: Path,
        *,
        version: str,
        target: str,
        subtarget: str,
        platform: str,
    ) -> Path:
        cfg_dir.mkdir(parents=True, exist_ok=True)
        cfg_path = cfg_dir / "config.mk"
        cfg_path.write_text(
            "\n".join(
                [
                    f"RELEASE = {version}",
                    f"TARGET = {target}",
                    f"SUBTARGET = {subtarget}",
                    f"PLATFORM = {platform}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return cfg_path

    @staticmethod
    def _sync_files(src: Path, dst: Path) -> None:
        if dst.exists():
            shutil.rmtree(dst)
        if src.exists() and any(src.rglob("*")):
            shutil.copytree(src, dst)

    def __call__(self, build: dict) -> dict:
        build_id = str(build["build_id"])
        request = dict(build.get("request") or {})
        options = dict(request.get("options") or {})

        version = self._safe_part("version", str(request.get("version") or ""))
        target, subtarget = self._parse_target(str(request.get("target") or ""))
        # NOTE: until API gets a dedicated device profile field.
        profile = self._safe_make_arg("profile", str(request.get("profile_id") or ""))
        jobs = str(max(1, (os.cpu_count() or 1)))
        debug = bool(options.get("debug"))
        if not (self._wrapper_dir / "Makefile").exists():
            raise RuntimeError("wrapper_makefile_missing")

        build_root = self._builds_dir / build_id
        out_dir = build_root / "wrapper-config"
        self._write_build_config(
            out_dir,
            version=version,
            target=target,
            subtarget=subtarget,
            platform=profile,
        )
        self._sync_files(self._files_dir, out_dir / "files")

        cache_override = self._cache_dir / "imagebuilder" / version
        cmd = [
            "make",
            f"-j{jobs}",
            f"C={out_dir}",
            f"CACHE={cache_override}",
            "image",
        ]
        if debug:
            cmd.append("V=s")

        proc = subprocess.run(
            cmd,
            cwd=self._wrapper_dir,
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            stderr_tail = (proc.stderr or "")[-3000:]
            stdout_tail = (proc.stdout or "")[-3000:]
            message = stderr_tail or stdout_tail or f"make_failed:{proc.returncode}"
            raise RuntimeError(message.strip())

        artifact_src = self._pick_artifact(out_dir)
        artifact_dst = build_root / f"{build_id}{artifact_src.suffix}"
        shutil.copy2(artifact_src, artifact_dst)
        if artifact_src.exists():
            artifact_src.unlink()
        return {"path": str(artifact_dst)}
