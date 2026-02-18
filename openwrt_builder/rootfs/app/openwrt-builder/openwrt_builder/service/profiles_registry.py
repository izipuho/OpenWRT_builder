"""Registry helpers for profiles and lists."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any

from pydantic import ValidationError

from openwrt_builder.env import env_path
from openwrt_builder.service.models import ListModel, ProfileModel

_JSON_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


class BaseRegistry:
    """Shared JSON file registry for config-like objects."""

    def __init__(self, configs_path: Path) -> None:
        """Initialize a registry rooted at the provided configs path."""
        self._configs_path = configs_path
        self._config_type = f"{configs_path.name[:-1]}"

    def _validate_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Validate payload before persistence/readback."""
        return payload

    def _load_validated(self, path: Path) -> dict[str, Any]:
        """Load and validate JSON payload from disk."""
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return self._validate_payload(data)

    @staticmethod
    def _now_z() -> str:
        """Return current UTC timestamp in RFC3339-like format."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def _slug(value: str) -> str:
        """Convert a string to a URL-friendly slug."""
        value = value.strip().lower()
        value = re.sub(r"[^a-z0-9]+", "-", value)
        value = re.sub(r"-{2,}", "-", value).strip("-")
        return value

    @staticmethod
    def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
        """Write JSON to a file atomically."""
        tmp_dir = Path("/tmp")

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=tmp_dir,
            delete=False,
        ) as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
            tmp_name = f.name

        shutil.move(tmp_name, path)

    def list(self) -> list[dict[str, Any]]:
        """Return a sorted list of all config records."""
        configs: list[dict[str, Any]] = []
        if self._configs_path.exists():
            for path in self._configs_path.glob("*.json"):
                try:
                    data = self._load_validated(path)

                    configs.append(
                        {
                            f"{self._config_type}_id": path.stem,
                            **data,
                        }
                    )
                except (OSError, json.JSONDecodeError):
                    continue
        configs.sort(key=lambda x: x["updated_at"])
        return configs

    def get(self, config_id: str) -> dict[str, Any]:
        """Return a single config by ID or raise FileNotFoundError."""
        path = self._configs_path / f"{config_id}.json"
        if not path.exists():
            raise FileNotFoundError(config_id)

        return {f"{self._config_type}_id": config_id, **self._load_validated(path)}

    def create(self, full_config: dict[str, Any], config_id: str = None, force: bool = False) -> dict[str, Any]:
        """Create or update a config record and return it."""
        full_config = self._validate_payload(full_config)
        name = full_config["name"]
        schema_version = full_config["schema_version"]

        if not isinstance(name, str) or not name.strip():
            raise ValueError("name")
        if not isinstance(schema_version, int):
            raise ValueError("schema_version")
        if not isinstance(full_config[self._config_type], dict):
            raise ValueError(self._config_type)

        config_id = config_id or full_config.get(f"{self._config_type}_id", self._slug(name))
        if not isinstance(config_id, str) or not _JSON_ID_RE.match(config_id):
            raise ValueError(f"{self._config_type}_id")

        path = self._configs_path / f"{config_id}.json"
        if path.exists() and not force:
            raise FileExistsError(config_id)

        out = {
            "updated_at": self._now_z(),
            **full_config,
        }

        self._atomic_write_json(path, out)

        return {f"{self._config_type}_id": config_id, **out}

    def delete(self, config_id: str) -> bool:
        """Delete a config by ID and return deletion status."""
        path = self._configs_path / f"{config_id}.json"
        if not path.exists():
            raise FileNotFoundError(config_id)
        path.unlink()
        return {f"{self._config_type}_id": config_id, "deleted": True}


class ProfilesRegistry(BaseRegistry):
    """Registry wrapper for profile configurations."""

    def __init__(self, configs_path: Path | None = None) -> None:
        """Initialize a profile registry rooted at the provided configs path."""
        if configs_path is None:
            configs_path = env_path("OPENWRT_BUILDER_PROFILES_DIR")
        super().__init__(configs_path)

    def _validate_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Validate profile payload shape."""
        try:
            return ProfileModel.model_validate(payload).model_dump()
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc


class ListsRegistry(BaseRegistry):
    """Registry wrapper for list configurations."""

    def __init__(self, configs_path: Path | None = None) -> None:
        """Initialize a list registry rooted at the provided configs path."""
        if configs_path is None:
            configs_path = env_path("OPENWRT_BUILDER_LISTS_DIR")
        super().__init__(configs_path)

    def _validate_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Validate list payload shape."""
        try:
            return ListModel.model_validate(payload).model_dump()
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc
