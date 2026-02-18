"""Service layer for builds backed by :class:`BuildsRegistry`."""
from __future__ import annotations

from openwrt_builder.service.builds_registry import BuildsRegistry


class BuildsService:
    """Thin wrapper around :class:`BuildsRegistry` operations."""

    def __init__(self, registry: BuildsRegistry) -> None:
        """Construct service with the builds registry."""
        self._registry = registry

    def list_builds(self) -> list[dict]:
        """Return all known builds sorted by registry rules."""
        return self._registry.list_builds()

    def get_build(self, build_id: str) -> dict:
        """Fetch a single build by identifier."""
        return self._registry.get_build(build_id)

    def create_build(self, request: dict) -> tuple[dict, bool]:
        """Create build using registry-defined queue semantics."""
        return self._registry.create_build(request)

    def cancel_build(self, build_id: str) -> bool:
        """Request build cancellation using registry-defined semantics."""
        return self._registry.cancel_build(build_id)

    def get_build_download(self, build_id: str) -> str:
        """Return absolute artifact path for a completed build."""
        return self._registry.get_build_download(build_id)
