"""Executor that runs OpenWrt ImageBuilder commands."""
from __future__ import annotations

import json
import os
import re
import signal
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any


_SAFE_VALUE_RE = re.compile(r"^[A-Za-z0-9_.@:+\-/]+$")
_SAFE_PART_RE = re.compile(r"^[A-Za-z0-9_.+-]+$")
_SAFE_PKG_RE = re.compile(r"^[A-Za-z0-9_.+-]+$")


class BuildCanceled(RuntimeError):
    """Build execution canceled by user request."""


class ImageBuilderExecutor:
    """Thin wrapper over external imagebuilder Makefile-based frontend."""

    def __init__(
        self,
        builds_dir: Path,
        files_dir: Path,
        cache_dir: Path,
        wrapper_dir: Path,
        profiles_dir: Path,
        lists_dir: Path,
    ) -> None:
        self._builds_dir = builds_dir
        self._files_dir = files_dir
        self._cache_dir = cache_dir
        self._wrapper_dir = wrapper_dir
        self._profiles_dir = profiles_dir
        self._lists_dir = lists_dir
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

    @staticmethod
    def _safe_pkg(name: str) -> str:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("invalid_package_name")
        name = name.strip()
        if not _SAFE_PKG_RE.match(name):
            raise ValueError("invalid_package_name")
        return name

    @staticmethod
    def _uniq(values: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            out.append(value)
        return out

    @staticmethod
    def _safe_file_rel(path_raw: str) -> str:
        value = str(path_raw or "").strip().replace("\\", "/")
        if not value:
            raise ValueError("invalid_profile_file_path")
        parts = value.split("/")
        if any(part in {"", ".", ".."} for part in parts):
            raise ValueError("invalid_profile_file_path")
        return "/".join(parts)

    @staticmethod
    def _json_load(path: Path) -> dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(path)
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("invalid_json_payload")
        return data

    @staticmethod
    def _tail_file(path: Path, limit: int = 3000) -> str:
        if not path.exists():
            return ""
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        return text[-limit:]

    def _is_cancel_requested(self, build_id: str) -> bool:
        build_path = self._builds_dir / f"{build_id}.json"
        if not build_path.exists():
            return False
        try:
            with build_path.open("r", encoding="utf-8") as f:
                payload = json.load(f)
        except (OSError, json.JSONDecodeError):
            return False
        if not isinstance(payload, dict):
            return False
        return bool(payload.get("cancel_requested"))

    @staticmethod
    def _terminate_process(proc: subprocess.Popen[str], timeout_sec: float = 5.0) -> None:
        if proc.poll() is not None:
            return
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        except OSError:
            try:
                proc.terminate()
            except OSError:
                return
        end_time = time.monotonic() + timeout_sec
        while proc.poll() is None and time.monotonic() < end_time:
            time.sleep(0.1)
        if proc.poll() is not None:
            return
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            try:
                proc.kill()
            except OSError:
                return

    @staticmethod
    def _cleanup_workspace(path: Path) -> None:
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)

    @staticmethod
    def _cleanup_temp_builddir_from_hint(hint_path: Path) -> None:
        try:
            raw = hint_path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            return
        if not raw:
            return
        path = Path(raw)
        # Safety guard: cleanup only expected ImageBuilder temp dirs.
        if not path.name.startswith("imgbldr-"):
            return
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)

    def _resolve_profile(self, profile_id: str) -> tuple[str, list[str], list[str], list[str]]:
        profile_payload = self._json_load(self._profiles_dir / f"{profile_id}.json")
        profile = profile_payload.get("profile")
        if not isinstance(profile, dict):
            raise ValueError("invalid_profile_payload")

        raw_lists = profile.get("lists") or []
        if not isinstance(raw_lists, list):
            raise ValueError("invalid_profile_lists")
        list_ids = [self._safe_part("list_id", str(item)) for item in raw_lists]

        include: list[str] = []
        exclude: list[str] = []
        for list_id in list_ids:
            list_payload = self._json_load(self._lists_dir / f"{list_id}.json")
            list_data = list_payload.get("list")
            if not isinstance(list_data, dict):
                raise ValueError("invalid_list_payload")
            list_include = list_data.get("include") or []
            list_exclude = list_data.get("exclude") or []
            if not isinstance(list_include, list) or not isinstance(list_exclude, list):
                raise ValueError("invalid_list_include_exclude")
            include.extend(self._safe_pkg(str(pkg)) for pkg in list_include)
            exclude.extend(self._safe_pkg(str(pkg)) for pkg in list_exclude)

        extra_include = profile.get("extra_include") or []
        extra_exclude = profile.get("extra_exclude") or []
        if not isinstance(extra_include, list) or not isinstance(extra_exclude, list):
            raise ValueError("invalid_profile_extra_include_exclude")
        include.extend(self._safe_pkg(str(pkg)) for pkg in extra_include)
        exclude.extend(self._safe_pkg(str(pkg)) for pkg in extra_exclude)

        raw_files = profile.get("files") or []
        if not isinstance(raw_files, list):
            raise ValueError("invalid_profile_files")
        selected_files = [self._safe_file_rel(str(path)) for path in raw_files]

        # API has no dedicated field yet; allow explicit key in profile payload.
        requested = profile.get("device_profile") or profile.get("platform")
        device_profile = self._safe_make_arg("profile", str(requested or profile_id))
        return device_profile, self._uniq(include), self._uniq(exclude), self._uniq(selected_files)

    @staticmethod
    def _write_build_config(
        cfg_dir: Path,
        *,
        version: str,
        target: str,
        subtarget: str,
        profile: str,
        include_pkgs: list[str],
        exclude_pkgs: list[str],
    ) -> Path:
        cfg_dir.mkdir(parents=True, exist_ok=True)
        cfg_path = cfg_dir / "config.mk"
        include_value = " ".join(include_pkgs)
        exclude_value = " ".join(exclude_pkgs)
        cfg_path.write_text(
            "\n".join(
                [
                    f"RELEASE = {version}",
                    f"TARGET = {target}",
                    f"SUBTARGET = {subtarget}",
                    f"PROFILE = {profile}",
                    f"PACKAGES_INCLUDE = {include_value}",
                    f"PACKAGES_EXCLUDE = {exclude_value}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return cfg_path

    @staticmethod
    def _sync_files(src: Path, dst: Path, selected_files: list[str]) -> None:
        if dst.exists():
            shutil.rmtree(dst)
        if not selected_files:
            return
        for rel in selected_files:
            src_path = src / rel
            if not src_path.is_file():
                raise FileNotFoundError(f"profile_file_not_found:{rel}")
            dst_path = dst / rel
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, dst_path)

    def __call__(self, build: dict) -> dict:
        build_id = str(build["build_id"])
        request = dict(build.get("request") or {})
        options = dict(request.get("options") or {})

        version = self._safe_part("version", str(request.get("version") or ""))
        target = self._safe_part("target", str(request.get("target") or ""))
        subtarget = self._safe_part("subtarget", str(request.get("subtarget") or ""))
        profile_id = self._safe_part("profile_id", str(request.get("profile_id") or ""))
        profile, include_pkgs, exclude_pkgs, selected_files = self._resolve_profile(profile_id)
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
            profile=profile,
            include_pkgs=include_pkgs,
            exclude_pkgs=exclude_pkgs,
        )
        self._sync_files(self._files_dir, out_dir / "files", selected_files)

        cache_override = self._cache_dir / "imagebuilder" / version
        builddir_hint = out_dir / ".imgbuilder_builddir"
        cmd = [
            "make",
            f"-j{jobs}",
            f"C={out_dir}",
            f"CACHE={cache_override}",
            f"BUILDDIR_HINT_FILE={builddir_hint}",
            "image",
        ]
        if debug:
            cmd.append("V=s")

        stdout_log = out_dir / "stdout.log"
        stderr_log = out_dir / "stderr.log"
        proc: subprocess.Popen[str] | None = None
        try:
            with stdout_log.open("w", encoding="utf-8") as out_f, stderr_log.open("w", encoding="utf-8") as err_f:
                proc = subprocess.Popen(
                    cmd,
                    cwd=self._wrapper_dir,
                    text=True,
                    stdout=out_f,
                    stderr=err_f,
                    preexec_fn=os.setsid,
                )
                while proc.poll() is None:
                    if self._is_cancel_requested(build_id):
                        raise BuildCanceled("canceled")
                    time.sleep(0.2)

            if proc.returncode != 0:
                stderr_tail = self._tail_file(stderr_log)
                stdout_tail = self._tail_file(stdout_log)
                message = stderr_tail or stdout_tail or f"make_failed:{proc.returncode}"
                raise RuntimeError(message.strip())

            artifact_src = self._pick_artifact(out_dir)
            artifact_dst = build_root / f"{build_id}{artifact_src.suffix}"
            shutil.copy2(artifact_src, artifact_dst)
            if artifact_src.exists():
                artifact_src.unlink()
            return {"path": str(artifact_dst)}
        finally:
            if proc is not None and proc.poll() is None:
                self._terminate_process(proc)
            self._cleanup_temp_builddir_from_hint(builddir_hint)
            self._cleanup_workspace(out_dir)
