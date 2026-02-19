"""Build runner (worker loop).

Responsibilities:
- Ensure single-runner execution via file lock.
- Re-queue "running" builds on startup (crash/restart recovery).
- Pull build_ids from BuildQueue (FIFO).
- Transition build state: queued -> running -> done/failed/canceled.
- Persist progress/message/result updates via atomic JSON writes.

This module MUST NOT implement HTTP concerns.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import fcntl
from pydantic import ValidationError

from openwrt_builder.service.build_queue import BuildQueue
from openwrt_builder.service.models import BuildModel, BuildResultModel
from openwrt_builder.service.profiles_registry import BaseRegistry
from openwrt_builder.runner.imagebuilder_executor import BuildCanceled


@dataclass(frozen=True)
class RunnerConfig:
    """Runtime config for the build runner."""

    builds_dir: Path
    runtime_dir: Path
    poll_interval_sec: float = 1.0


class RunnerLock:
    """Single-runner lock (fcntl)."""

    def __init__(self, lock_path: Path) -> None:
        """Initialize lock manager for the given lock file path."""
        self._lock_path = lock_path
        self._fp = None

    def __enter__(self) -> "RunnerLock":
        """Acquire exclusive non-blocking file lock and write current PID."""
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        fp = self._lock_path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            fp.close()
            raise RuntimeError("runner_already_running")
        fp.seek(0)
        fp.truncate()
        fp.write(f"{os.getpid()}\n")
        fp.flush()
        self._fp = fp
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        """Release lock file descriptor if it was acquired."""
        if self._fp is not None:
            try:
                fcntl.flock(self._fp.fileno(), fcntl.LOCK_UN)
            finally:
                self._fp.close()
                self._fp = None


class BuildRunner:
    """Build runner loop."""

    def __init__(
        self,
        cfg: RunnerConfig,
        queue: BuildQueue,
        executor: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> None:
        """
        Args:
            cfg: RunnerConfig.
            queue: Persistent build queue.
            executor: Callable that performs the build.
                Input: build dict
                Output: dict with {"artifacts": [...]} on success.
        """
        self._cfg = cfg
        self._queue = queue
        self._executor = executor

    def _build_path(self, build_id: str) -> Path:
        """Return JSON metadata path for a build identifier."""
        return self._cfg.builds_dir / f"{build_id}.json"

    @staticmethod
    def _validate_build(payload: dict[str, Any]) -> dict[str, Any]:
        """Validate and normalize build payload."""
        return BuildModel.model_validate(payload).model_dump()

    def _read_build(self, build_id: str) -> dict[str, Any]:
        """Read and deserialize build metadata for a build identifier."""
        path = self._build_path(build_id)
        if not path.exists():
            raise FileNotFoundError(build_id)
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        return self._validate_build(payload)

    def _write_build(self, build_id: str, payload: dict[str, Any]) -> None:
        """Persist build metadata atomically."""
        BaseRegistry._atomic_write_json(self._build_path(build_id), self._validate_build(payload))

    def _set_state(
        self,
        build: dict[str, Any],
        *,
        state: str | None = None,
        progress: int | None = None,
        message: str | None = None,
        result: dict[str, Any] | None = None,
        runner_pid: int | None | object = None,
    ) -> dict[str, Any]:
        """Apply partial build state changes and refresh update timestamp."""
        if state is not None:
            build["state"] = state
        if progress is not None:
            build["progress"] = int(progress)
        build["updated_at"] = BaseRegistry._now_z()
        build["message"] = message
        if result is not None:
            build["result"] = BuildResultModel.model_validate(result).model_dump()
        if runner_pid is not None:
            build["runner_pid"] = runner_pid
        return build

    def requeue_running_on_startup(self) -> int:
        """Move all builds in state 'running' back to 'queued'."""
        n = 0
        self._cfg.builds_dir.mkdir(parents=True, exist_ok=True)
        for path in self._cfg.builds_dir.glob("*.json"):
            try:
                with path.open("r", encoding="utf-8") as f:
                    b = self._validate_build(json.load(f))
                if b.get("state") != "running":
                    continue
                b["state"] = "queued"
                b["progress"] = 0
                b["message"] = "runner_restart_requeued"
                b["runner_pid"] = None
                b["updated_at"] = BaseRegistry._now_z()
                BaseRegistry._atomic_write_json(path, b)
                n += 1
            except (OSError, json.JSONDecodeError, ValidationError):
                continue
        return n

    def run_forever(self) -> None:
        """Main runner loop."""
        lock_path = self._cfg.runtime_dir / "runner.lock"
        with RunnerLock(lock_path):
            self.requeue_running_on_startup()

            while True:
                build_id = self._queue.dequeue()
                if not build_id:
                    time.sleep(self._cfg.poll_interval_sec)
                    continue

                try:
                    build = self._read_build(build_id)
                except (FileNotFoundError, json.JSONDecodeError, ValidationError):
                    continue

                state = build.get("state")
                if state in {"done", "failed", "canceled"}:
                    continue
                if state != "queued":
                    continue

                # cancel before starting
                if build.get("cancel_requested") is True:
                    build = self._set_state(build, state="canceled", message="canceled", runner_pid=None)
                    self._write_build(build_id, build)
                    continue

                # start
                build = self._set_state(
                    build,
                    state="running",
                    progress=1,
                    message="starting",
                    runner_pid=os.getpid(),
                )
                self._write_build(build_id, build)

                try:
                    build = self._set_state(build, progress=10, message="executing")
                    self._write_build(build_id, build)

                    # cancel right before executor
                    if build.get("cancel_requested") is True:
                        build = self._set_state(build, state="canceled", message="canceled", runner_pid=None)
                        self._write_build(build_id, build)
                        continue

                    result = self._executor(build)

                    # cancel may have been requested during execution
                    try:
                        build = self._read_build(build_id)
                    except (FileNotFoundError, json.JSONDecodeError, ValidationError):
                        continue
                    if build.get("cancel_requested") is True:
                        build = self._set_state(build, state="canceled", message="canceled", runner_pid=None)
                        self._write_build(build_id, build)
                        continue

                    build = self._set_state(build, state="done", progress=100, message=None, result=result, runner_pid=None)
                    self._write_build(build_id, build)
                except BuildCanceled:
                    try:
                        build = self._read_build(build_id)
                    except (FileNotFoundError, json.JSONDecodeError, ValidationError):
                        continue
                    build = self._set_state(build, state="canceled", message="canceled", runner_pid=None)
                    self._write_build(build_id, build)
                except Exception as e:
                    try:
                        build = self._read_build(build_id)
                    except (FileNotFoundError, json.JSONDecodeError, ValidationError):
                        continue
                    build = self._set_state(build, state="failed", message=str(e), runner_pid=None)
                    self._write_build(build_id, build)
