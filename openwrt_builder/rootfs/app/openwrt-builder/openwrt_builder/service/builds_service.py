"""Service layer for builds (registry + queue orchestration)."""
from __future__ import annotations

from openwrt_builder.service.build_queue import BuildQueue
from openwrt_builder.service.builds_registry import BuildsRegistry


class BuildsService:
    """Orchestrates build lifecycle between API and runner."""

    def __init__(self, registry: BuildsRegistry, queue: BuildQueue) -> None:
        """Construct service with storage registry and execution queue."""
        self._registry = registry
        self._queue = queue

    def list_builds(self) -> list[dict]:
        """Return all known builds sorted by registry rules."""
        return self._registry.list_builds()

    def get_build(self, build_id: str) -> dict:
        """Fetch a single build by identifier."""
        return self._registry.get_build(build_id)

    def create_build(self, request: dict) -> tuple[dict, bool]:
        """Create build and enqueue it when newly created."""
        build, created = self._registry.create_build(request)
        if created:
            self._queue.enqueue(build["build_id"])
        return build, created

    def cancel_build(self, build_id: str) -> bool:
        """Request build cancellation and remove from queue when possible."""
        ok = self._registry.cancel_build(build_id)
        if ok:
            self._queue.remove(build_id)
        return ok

    def get_build_download(self, build_id: str) -> str:
        """Return absolute artifact path for a completed build."""
        return self._registry.get_build_download(build_id)
