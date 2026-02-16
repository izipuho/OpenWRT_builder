"""Runner entrypoint: python -m openwrt_builder.runner.main"""
from __future__ import annotations

import os
from pathlib import Path

from openwrt_builder.runner.runner import BuildRunner, RunnerConfig
from openwrt_builder.runner.stub_executor import StubExecutor
from openwrt_builder.service.build_queue import BuildQueue


def _env_path(name: str) -> Path:
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(f"missing_env:{name}")
    return Path(v)


def main() -> None:
    builds_dir = _env_path("OPENWRT_BUILDER_BUILDS_DIR")
    runtime_dir = _env_path("OPENWRT_BUILDER_RUNTIME_DIR")

    queue = BuildQueue(runtime_dir / "queue.json")
    executor = StubExecutor(builds_dir)

    runner = BuildRunner(
        cfg=RunnerConfig(builds_dir=builds_dir, runtime_dir=runtime_dir),
        queue=queue,
        executor=executor,
    )
    runner.run_forever()


if __name__ == "__main__":
    main()
