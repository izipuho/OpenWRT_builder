"""Executor that runs OpenWrt ImageBuilder commands."""
from __future__ import annotations

import json
import os
import platform
import re
import signal
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable


_SAFE_VALUE_RE = re.compile(r"^[A-Za-z0-9_.@:+\-/]+$")
_SAFE_PART_RE = re.compile(r"^[A-Za-z0-9_.+-]+$")
_SAFE_PKG_RE = re.compile(r"^[A-Za-z0-9_.+-]+$")
_IMAGE_SUFFIX = {
    "sysupgrade": "squashfs-sysupgrade.bin",
    "factory": "squashfs-factory.bin",
}
_LOG_CHUNK_MAX = 8192


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
    def _safe_image_kind(kind: str) -> str:
        value = str(kind or "").strip()
        if value not in _IMAGE_SUFFIX:
            raise ValueError("invalid_output_images")
        return value

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
    def _normalize_file_not_found(exc: FileNotFoundError) -> RuntimeError:
        raw = str(exc or "").strip()
        if raw.startswith("selected_file_not_found:"):
            return RuntimeError(raw)
        if raw.startswith("profile_not_found:") or raw.startswith("list_not_found:"):
            return RuntimeError(raw)
        missing = Path(raw).name if raw else ""
        if not missing:
            missing = "unknown"
        return RuntimeError(f"file_not_found:{missing}")

    def _resolve_output_images(self, options: dict[str, Any]) -> list[str]:
        raw = options.get("output_images")
        if raw is None:
            return ["sysupgrade"]
        if not isinstance(raw, list):
            raise ValueError("invalid_output_images")
        if not raw:
            raise ValueError("invalid_output_images")
        values = [self._safe_image_kind(str(item)) for item in raw]
        values = self._uniq(values)
        if not values:
            raise ValueError("invalid_output_images")
        return values

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

    @staticmethod
    def _summarize_make_failure(stderr_tail: str, stdout_tail: str, returncode: int) -> str:
        combined = f"{stderr_tail}\n{stdout_tail}"
        if re.search(r"No space left on device", combined, flags=re.IGNORECASE):
            return "no_space_left"

        too_big = re.search(r"is too big:\s*(\d+)\s*>\s*(\d+)", combined)
        if too_big:
            built_size, max_size = too_big.groups()
            return f"image_too_big:built={built_size}:max={max_size}"

        if (
            re.search(r"curl:\s*\(\d+\)", combined)
            or "The requested URL returned error" in combined
            or "Failed to connect to" in combined
            or "Could not resolve host" in combined
        ):
            return "imagebuilder_download_failed"

        if (
            re.search(r"Unknown package", combined, flags=re.IGNORECASE)
            or re.search(r"conflicts with", combined, flags=re.IGNORECASE)
            or re.search(r"check_data_file_clashes", combined, flags=re.IGNORECASE)
            or re.search(r"Collected errors", combined, flags=re.IGNORECASE)
        ):
            return "package_conflict_or_not_found"

        message = (stderr_tail or stdout_tail or f"make_failed:{returncode}").strip()
        if not message:
            return f"make_failed:{returncode}"
        return message

    @staticmethod
    def _read_new_chunk(path: Path, offset: int, *, max_bytes: int = _LOG_CHUNK_MAX) -> tuple[str, int]:
        if not path.exists():
            return "", offset
        try:
            size = path.stat().st_size
        except OSError:
            return "", offset
        safe_offset = max(0, min(offset, size))
        try:
            with path.open("rb") as f:
                f.seek(safe_offset)
                raw = f.read(max_bytes)
                new_offset = f.tell()
        except OSError:
            return "", offset
        if not raw:
            return "", new_offset
        return raw.decode("utf-8", errors="replace"), new_offset

    @staticmethod
    def _emit_update(
        on_update: Callable[[dict[str, Any]], None] | None,
        *,
        progress: int,
        phase: str,
        message: str | None = None,
        stdout_path: Path | None = None,
        stderr_path: Path | None = None,
        stdout_chunk: str | None = None,
        stderr_chunk: str | None = None,
        phase_event: bool = False,
    ) -> None:
        if on_update is None:
            return
        payload: dict[str, Any] = {
            "progress": max(0, min(100, int(progress))),
            "phase": phase,
            "message": message,
        }
        if stdout_path is not None:
            payload["stdout_path"] = str(stdout_path)
        if stderr_path is not None:
            payload["stderr_path"] = str(stderr_path)
        if stdout_chunk:
            payload["stdout_chunk"] = stdout_chunk
        if stderr_chunk:
            payload["stderr_chunk"] = stderr_chunk
        if phase_event:
            payload["phase_event"] = {
                "phase": phase,
                "progress": max(0, min(100, int(progress))),
                "message": message,
            }
        on_update(payload)

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
    def _assert_supported_host_arch() -> None:
        """OpenWrt ImageBuilder artifacts we use are Linux-x86_64 only."""
        machine = platform.machine().strip().lower()
        if machine not in {"x86_64", "amd64"}:
            raise RuntimeError(f"unsupported_host_arch:{machine}:requires_x86_64")

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

    def _resolve_profile(self, profile_id: str) -> tuple[list[str], list[str], list[str]]:
        try:
            profile_payload = self._json_load(self._profiles_dir / f"{profile_id}.json")
        except FileNotFoundError as exc:
            raise RuntimeError(f"profile_not_found:{profile_id}") from exc
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
            try:
                list_payload = self._json_load(self._lists_dir / f"{list_id}.json")
            except FileNotFoundError as exc:
                raise RuntimeError(f"list_not_found:{list_id}") from exc
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

        return self._uniq(include), self._uniq(exclude), self._uniq(selected_files)

    @staticmethod
    def _write_build_config(
        cfg_dir: Path,
        *,
        version: str,
        target: str,
        subtarget: str,
        platform: str,
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
                    f"PLATFORM = {platform}",
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
                raise FileNotFoundError(f"selected_file_not_found:{rel}")
            dst_path = dst / rel
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, dst_path)

    def __call__(
        self,
        build: dict,
        *,
        on_update: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict:
        build_id = str(build["build_id"])
        request = dict(build.get("request") or {})
        options = dict(request.get("options") or {})

        self._emit_update(on_update, progress=6, phase="validating", message="validating", phase_event=True)
        self._assert_supported_host_arch()

        version = self._safe_part("version", str(request.get("version") or ""))
        platform = self._safe_part("platform", str(request.get("platform") or ""))
        target = self._safe_part("target", str(request.get("target") or ""))
        subtarget = self._safe_part("subtarget", str(request.get("subtarget") or ""))
        profile_id = self._safe_part("profile_id", str(request.get("profile_id") or ""))
        self._emit_update(
            on_update,
            progress=12,
            phase="resolving_profile",
            message=f"resolving_profile:{profile_id}",
            phase_event=True,
        )
        include_pkgs, exclude_pkgs, selected_files = self._resolve_profile(profile_id)
        output_images = self._resolve_output_images(options)
        jobs = str(max(1, (os.cpu_count() or 1)))
        debug = bool(options.get("debug"))
        if not (self._wrapper_dir / "Makefile").exists():
            raise RuntimeError("wrapper_makefile_missing")

        build_root = self._builds_dir / build_id
        logs_dir = build_root / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        out_dir = build_root / "wrapper-config"
        self._emit_update(on_update, progress=16, phase="preparing", message="writing_config", phase_event=True)
        self._write_build_config(
            out_dir,
            version=version,
            platform=platform,
            target=target,
            subtarget=subtarget,
            include_pkgs=include_pkgs,
            exclude_pkgs=exclude_pkgs,
        )
        self._sync_files(self._files_dir, out_dir / "files", selected_files)
        self._emit_update(
            on_update,
            progress=20,
            phase="preparing",
            message=f"files_selected:{len(selected_files)}",
            phase_event=False,
        )

        cache_override = self._cache_dir / "imagebuilder" / version
        builddir_hint = out_dir / ".imgbuilder_builddir"
        cmd = [
            "make",
            f"-j{jobs}",
            f"C={out_dir}",
            f"CACHE={cache_override}",
            f"BUILDDIR_HINT_FILE={builddir_hint}",
            f"IMAGES={' '.join(output_images)}",
            "image",
        ]
        if debug:
            cmd.append("V=s")

        stdout_log = logs_dir / "stdout.log"
        stderr_log = logs_dir / "stderr.log"
        proc: subprocess.Popen[str] | None = None
        env = os.environ.copy()
        env["TMPDIR"] = "/tmp"
        env["TMP"] = "/tmp"
        env["TEMP"] = "/tmp"
        self._emit_update(
            on_update,
            progress=24,
            phase="building",
            message="launching_make",
            stdout_path=stdout_log,
            stderr_path=stderr_log,
            phase_event=True,
        )
        try:
            with stdout_log.open("w", encoding="utf-8") as out_f, stderr_log.open("w", encoding="utf-8") as err_f:
                proc = subprocess.Popen(
                    cmd,
                    cwd=self._wrapper_dir,
                    text=True,
                    env=env,
                    stdout=out_f,
                    stderr=err_f,
                    preexec_fn=os.setsid,
                )
                stdout_pos = 0
                stderr_pos = 0
                progress = 24
                last_progress_at = time.monotonic()
                while proc.poll() is None:
                    if self._is_cancel_requested(build_id):
                        raise BuildCanceled("canceled")
                    stdout_chunk, stdout_pos = self._read_new_chunk(stdout_log, stdout_pos)
                    stderr_chunk, stderr_pos = self._read_new_chunk(stderr_log, stderr_pos)
                    now = time.monotonic()
                    progress_changed = False
                    if now - last_progress_at >= 2.0 and progress < 92:
                        progress += 1
                        last_progress_at = now
                        progress_changed = True
                    if stdout_chunk or stderr_chunk or progress_changed:
                        self._emit_update(
                            on_update,
                            progress=progress,
                            phase="building",
                            message="building",
                            stdout_path=stdout_log,
                            stderr_path=stderr_log,
                            stdout_chunk=stdout_chunk,
                            stderr_chunk=stderr_chunk,
                            phase_event=False,
                        )
                    time.sleep(0.2)
                stdout_chunk, stdout_pos = self._read_new_chunk(stdout_log, stdout_pos)
                stderr_chunk, stderr_pos = self._read_new_chunk(stderr_log, stderr_pos)
                if stdout_chunk or stderr_chunk:
                    self._emit_update(
                        on_update,
                        progress=93,
                        phase="building",
                        message="build_output_finalized",
                        stdout_path=stdout_log,
                        stderr_path=stderr_log,
                        stdout_chunk=stdout_chunk,
                        stderr_chunk=stderr_chunk,
                        phase_event=False,
                    )

            if proc.returncode != 0:
                stderr_tail = self._tail_file(stderr_log)
                stdout_tail = self._tail_file(stdout_log)
                message = self._summarize_make_failure(stderr_tail, stdout_tail, proc.returncode)
                self._emit_update(
                    on_update,
                    progress=94,
                    phase="failed",
                    message=message,
                    stdout_path=stdout_log,
                    stderr_path=stderr_log,
                    phase_event=True,
                )
                raise RuntimeError(message.strip())

            artifacts: list[dict[str, Any]] = []
            self._emit_update(on_update, progress=95, phase="collecting_artifacts", message="collecting_artifacts", phase_event=True)
            for image_kind in output_images:
                image_name = f"openwrt-{version}-{target}-{subtarget}-{platform}-" f"{_IMAGE_SUFFIX[image_kind]}"
                artifact_src = out_dir / image_name
                if not artifact_src.is_file():
                    raise RuntimeError(f"requested_image_not_built:{image_kind}")
                artifact_dst = build_root / image_name
                artifact_dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(artifact_src, artifact_dst)
                artifacts.append(
                    {
                        "id": image_kind,
                        "name": image_name,
                        "path": str(artifact_dst),
                        "size": artifact_dst.stat().st_size,
                        "type": "firmware",
                        "role": "primary" if image_kind == "sysupgrade" else "optional",
                    }
                )
                if len(output_images) > 0:
                    collected = len(artifacts)
                    step_progress = 95 + int((collected / len(output_images)) * 4)
                else:
                    step_progress = 98
                self._emit_update(
                    on_update,
                    progress=min(99, step_progress),
                    phase="collecting_artifacts",
                    message=f"artifact_ready:{image_kind}",
                    phase_event=False,
                )
            if artifacts and artifacts[0]["role"] != "primary":
                artifacts[0]["role"] = "primary"
            self._emit_update(on_update, progress=99, phase="finalizing", message="finalizing", phase_event=True)
            return {"artifacts": artifacts}
        except FileNotFoundError as exc:
            raise self._normalize_file_not_found(exc) from exc
        except OSError as exc:
            detail = str(exc.strerror or "").strip() or exc.__class__.__name__
            raise RuntimeError(f"io_error:{detail}") from exc
        finally:
            if proc is not None and proc.poll() is None:
                self._terminate_process(proc)
            self._cleanup_temp_builddir_from_hint(builddir_hint)
            self._cleanup_workspace(out_dir)
