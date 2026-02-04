"""Registry helpers for builds."""
from __future__ import annotations

import json
from pathlib import Path

from openwrt_builder.service.profiles_registry import BaseRegistry, ProfilesRegistry


class BuildsRegistry:
    """File-backed registry for build objects."""

    def __init__(self, builds_path: Path, profiles: ProfilesRegistry) -> None:
        self._builds_path = builds_path
        self._builds_path.mkdir(parents=True, exist_ok=True)
        self._profiles = profiles

    def _build_path(self, build_id: str) -> Path:
        return self._builds_path / f"{build_id}.json"

    def _read_build(self, build_id: str) -> dict:
        path = self._build_path(build_id)
        if not path.exists():
            raise FileNotFoundError(build_id)
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _write_build(self, build_id: str, payload: dict) -> None:
        BaseRegistry._atomic_write_json(self._build_path(build_id), payload)

    @staticmethod
    def _normalize_request(request: dict) -> dict:
        normalized = json.loads(json.dumps(request))
        options = normalized.get("options") or {}
        options["force_rebuild"] = False
        normalized["options"] = options
        return normalized

    def list_builds(self) -> list[dict]:
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
        return self._read_build(build_id)

    def create_build(self, request: dict) -> tuple[dict, bool]:
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
        }
        self._write_build(build_id, build)
        return build, True

    def cancel_build(self, build_id: str) -> bool:
        build = self._read_build(build_id)
        if build["state"] in {"done", "failed", "canceled"}:
            return False
        build["state"] = "canceled"
        build["updated_at"] = BaseRegistry._now_z()
        build["message"] = "canceled"
        self._write_build(build_id, build)
        return True

    def get_build_download(self, build_id: str) -> str:
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
