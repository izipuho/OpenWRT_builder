"""Service layer for builds (registry + queue orchestration)."""
from __future__ import annotations

from openwrt_builder.service.build_queue import BuildQueue
from openwrt_builder.service.builds_registry import BuildsRegistry


class BuildsService:
    """Orchestrates build lifecycle between API and runner."""

    def __init__(self, registry: BuildsRegistry, queue: BuildQueue) -> None:
        self._registry = registry
        self._queue = queue

    def list_builds(self) -> list[dict]:
        return self._registry.list_builds()

    def get_build(self, build_id: str) -> dict:
        return self._registry.get_build(build_id)

    def create_build(self, request: dict) -> tuple[dict, bool]:
        build, created = self._registry.create_build(request)
        if created:
            self._queue.enqueue(build["build_id"])
        return build, created

    def cancel_build(self, build_id: str) -> bool:
        ok = self._registry.cancel_build(build_id)
        if ok:
            self._queue.remove(build_id)
        return ok

    def get_build_download(self, build_id: str) -> str:
        return self._registry.get_build_download(build_id)
