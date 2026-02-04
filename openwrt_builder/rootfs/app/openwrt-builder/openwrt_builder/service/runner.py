"""Minimal build runner loop."""
from __future__ import annotations

import os
import random
import signal
import time
from pathlib import Path
from subprocess import Popen

from openwrt_builder.service.build_queue import BuildQueue
from openwrt_builder.service.builds_registry import BuildsRegistry
from openwrt_builder.service.profiles_registry import BaseRegistry
from openwrt_builder.service.runner_lock import RunnerLock


class Executor:
    """Stub executor for running a build."""

    def run(self, build: dict) -> tuple[Popen, dict]:
        process = Popen(
            ["/bin/sleep", "1"],
            preexec_fn=os.setsid,
        )
        result = {"path": f"/tmp/{build['build_id']}.tar.gz"}
        return process, result


class Runner:
    """Single-worker runner consuming the persistent queue."""

    def __init__(
        self,
        registry: BuildsRegistry,
        runtime_dir: Path,
        executor: Executor | None = None,
    ) -> None:
        self._registry = registry
        self._queue = BuildQueue(runtime_dir / "queue.json")
        self._lock = RunnerLock(runtime_dir)
        self._executor = executor or Executor()

    def recover_running_builds(self) -> None:
        for build in self._registry.list_builds():
            if build.get("state") != "running":
                continue
            build_id = build["build_id"]
            self._registry.update_build(
                build_id,
                {
                    "state": "queued",
                    "progress": 0,
                    "message": "runner_restart_requeued",
                    "runner_pid": None,
                    "updated_at": BaseRegistry._now_z(),
                },
            )
            self._queue.enqueue(build_id)

    def _cancel_build(self, build_id: str, process: Popen | None) -> None:
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                process = None
        if process is not None:
            deadline = time.time() + 5
            while time.time() < deadline and process.poll() is None:
                time.sleep(0.1)
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        self._registry.update_build(
            build_id,
            {
                "state": "canceled",
                "progress": 0,
                "message": "canceled",
                "runner_pid": None,
                "updated_at": BaseRegistry._now_z(),
            },
        )

    def run_forever(self) -> None:
        if not self._lock.acquire():
            return
        try:
            self.recover_running_builds()
            while True:
                build_id = self._queue.dequeue()
                if not build_id:
                    time.sleep(random.uniform(0.5, 2.0))
                    continue
                build = self._registry.get_build(build_id)
                if build["state"] in {"done", "failed", "canceled"}:
                    continue
                if build["state"] != "queued":
                    continue
                if build.get("cancel_requested"):
                    self._registry.update_build(
                        build_id,
                        {
                            "state": "canceled",
                            "progress": 0,
                            "message": "canceled",
                            "runner_pid": None,
                            "updated_at": BaseRegistry._now_z(),
                        },
                    )
                    continue
                self._registry.update_build(
                    build_id,
                    {
                        "state": "running",
                        "progress": 1,
                        "message": "starting",
                        "runner_pid": None,
                        "updated_at": BaseRegistry._now_z(),
                    },
                )
                process = None
                try:
                    process, result = self._executor.run(build)
                    self._registry.update_build(
                        build_id,
                        {
                            "runner_pid": process.pid,
                            "updated_at": BaseRegistry._now_z(),
                        },
                    )
                    while process.poll() is None:
                        current = self._registry.get_build(build_id)
                        if current.get("cancel_requested"):
                            self._cancel_build(build_id, process)
                            process = None
                            break
                        time.sleep(0.2)
                    if process is None:
                        continue
                    if process.returncode == 0:
                        self._registry.update_build(
                            build_id,
                            {
                                "state": "done",
                                "progress": 100,
                                "message": None,
                                "result": result,
                                "runner_pid": None,
                                "updated_at": BaseRegistry._now_z(),
                            },
                        )
                    else:
                        self._registry.update_build(
                            build_id,
                            {
                                "state": "failed",
                                "progress": 0,
                                "message": f"exit_code:{process.returncode}",
                                "runner_pid": None,
                                "updated_at": BaseRegistry._now_z(),
                            },
                        )
                except Exception as exc:
                    self._registry.update_build(
                        build_id,
                        {
                            "state": "failed",
                            "progress": 0,
                            "message": str(exc),
                            "runner_pid": None,
                            "updated_at": BaseRegistry._now_z(),
                        },
                    )
        finally:
            self._lock.release()
