"""Registry helpers for builds."""
from __future__ import annotations

import json
from pathlib import Path

from openwrt_builder.service.build_queue import BuildQueue
from openwrt_builder.service.profiles_registry import BaseRegistry, ProfilesRegistry


class BuildsRegistry:
    """File-backed registry for build objects.

    This registry stores build metadata as JSON files on disk and provides
    convenience helpers for lifecycle operations (create, list, cancel, and
    download lookups). It relies on :class:`ProfilesRegistry` to validate
    profile identifiers before creating builds.
    """

    def __init__(self, builds_path: Path, profiles: ProfilesRegistry, queue: BuildQueue) -> None:
        """Initialize the registry and ensure the build directory exists.

        Args:
            builds_path: Filesystem directory where build JSON files live.
            profiles: Registry used to validate profile identifiers.
        """
        self._builds_path = builds_path
        self._builds_path.mkdir(parents=True, exist_ok=True)
        self._profiles = profiles
        self._queue = queue

    def _build_path(self, build_id: str) -> Path:
        """Return the path for a build JSON file by ID."""
        return self._builds_path / f"{build_id}.json"

    def _read_build(self, build_id: str) -> dict:
        """Load a build JSON payload from disk.

        Args:
            build_id: Identifier for the build.

        Returns:
            The parsed JSON payload for the build.

        Raises:
            FileNotFoundError: If the build file does not exist.
            json.JSONDecodeError: If the build file is invalid JSON.
        """
        path = self._build_path(build_id)
        if not path.exists():
            raise FileNotFoundError(build_id)
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _write_build(self, build_id: str, payload: dict) -> None:
        """Persist a build JSON payload to disk atomically."""
        BaseRegistry._atomic_write_json(self._build_path(build_id), payload)

    def update_build(self, build_id: str, updates: dict) -> dict:
        """Update a build payload with the provided fields."""
        build = self._read_build(build_id)
        build.update(updates)
        if "updated_at" not in updates:
            build["updated_at"] = BaseRegistry._now_z()
        self._write_build(build_id, build)
        return build

    @staticmethod
    def _normalize_request(request: dict) -> dict:
        """Normalize a build request for equality comparisons.

        This performs a JSON round-trip to deep-copy the request, then ensures
        ``options.force_rebuild`` is set to ``False`` so that equality checks
        ignore explicit rebuild flags.
        """
        normalized = json.loads(json.dumps(request))
        options = normalized.get("options") or {}
        options["force_rebuild"] = False
        normalized["options"] = options
        return normalized

    def list_builds(self) -> list[dict]:
        """Return all build payloads sorted by ``updated_at``.

        Returns:
            A list of build payloads sorted by updated timestamp.
        """
        builds: list[dict] = []
        if self._builds_path.exists():
            for path in self._builds_path.glob("*.json"):
                try:
                    with path.open("r", encoding="utf-8") as f:
                        data = json.load(f)
                    builds.append(data)
                except (OSError, json.JSONDecodeError):
                    continue
        builds.sort(key=lambda x: x["updated_at"])
        return builds

    def get_build(self, build_id: str) -> dict:
        """Fetch a build payload by identifier."""
        return self._read_build(build_id)

    def create_build(self, request: dict) -> tuple[dict, bool]:
        """Create a new build or reuse an existing completed one.

        Args:
            request: Build request payload containing a ``profile_id`` key and
                optional ``options`` dict.

        Returns:
            Tuple of (build payload, created_flag) where ``created_flag`` is
            ``True`` when a new build was created and ``False`` when a matching
            completed build was reused.

        Raises:
            ValueError: If ``profile_id`` is missing or invalid.
            FileNotFoundError: If the profile does not exist.
        """
        profile_id = request.get("profile_id")
        if not isinstance(profile_id, str):
            raise ValueError("profile_id")
        self._profiles.get(profile_id)

        normalized = self._normalize_request(request)
        force_rebuild = bool(request.get("options", {}).get("force_rebuild"))

        if not force_rebuild:
            for existing in self.list_builds():
                if self._normalize_request(existing.get("request", {})) == normalized:
                    if existing.get("state") == "done":
                        return existing, False

        build_id = BaseRegistry._slug(f"{request.get('profile_id','build')}-{BaseRegistry._now_z()}")
        created_at = BaseRegistry._now_z()
        build = {
            "build_id": build_id,
            "state": "queued",
            "created_at": created_at,
            "updated_at": created_at,
            "progress": 0,
            "message": None,
            "request": request,
            "result": None,
            "cancel_requested": False,
            "runner_pid": None,
        }
        self._write_build(build_id, build)
        if self._queue is not None:
            self._queue.enqueue(build_id)
        return build, True

    def cancel_build(self, build_id: str) -> bool:
        """Cancel a build unless it is already terminal.

        Args:
            build_id: Identifier for the build.

        Returns:
            ``True`` if the build was canceled, ``False`` if it was already in a
            terminal state.
        """
        build = self._read_build(build_id)
        if build["state"] in {"done", "failed", "canceled"}:
            return False
        if build["state"] == "queued":
            build["state"] = "canceled"
            build["updated_at"] = BaseRegistry._now_z()
            build["message"] = "canceled"
            self._write_build(build_id, build)
            if self._queue is not None:
                self._queue.remove(build_id)
            return True
        if build["state"] == "running":
            build["cancel_requested"] = True
            build["updated_at"] = BaseRegistry._now_z()
            build["message"] = "cancel_requested"
            self._write_build(build_id, build)
            return True
        return False

    def get_build_download(self, build_id: str) -> str:
        """Return the filesystem path to a completed build artifact.

        Args:
            build_id: Identifier for the build.

        Returns:
            Path to the build artifact on disk.

        Raises:
            PermissionError: If the build is not in the ``done`` state.
            FileNotFoundError: If the build or artifact path is missing.
        """
        build = self._read_build(build_id)
        if build.get("state") != "done":
            raise PermissionError(build_id)
        result = build.get("result") or {}
        path = result.get("path")
        if not path:
            raise FileNotFoundError(build_id)
        if not Path(path).exists():
            raise FileNotFoundError(build_id)
        return path
