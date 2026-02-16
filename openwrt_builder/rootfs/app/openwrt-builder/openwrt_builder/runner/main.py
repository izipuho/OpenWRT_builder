"""Runner entrypoint: python -m openwrt_builder.runner.main"""
from __future__ import annotations

from openwrt_builder.runner.runner import BuildRunner, RunnerConfig
from openwrt_builder.runner.stub_executor import StubExecutor
from openwrt_builder.env import env_path
from openwrt_builder.service.build_queue import BuildQueue


def main() -> None:
    builds_dir = env_path("OPENWRT_BUILDER_BUILDS_DIR")
    runtime_dir = env_path("OPENWRT_BUILDER_RUNTIME_DIR")

    queue = BuildQueue(builds_dir / "queue.json")
    executor = StubExecutor(builds_dir)

    runner = BuildRunner(
        cfg=RunnerConfig(builds_dir=builds_dir, runtime_dir=runtime_dir),
        queue=queue,
        executor=executor,
    )
    runner.run_forever()


if __name__ == "__main__":
    main()
