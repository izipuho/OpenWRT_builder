"""Registry classes for profiles, lists, and shared file-backed helpers."""
from __future__ import annotations
import json
from pathlib import Path
import os
from datetime import datetime, timezone
import re
import tempfile
import shutil

_JSON_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")

class BaseRegistry:
    """Shared JSON file registry for config-like objects."""
    def __init__(self, configs_path: Path) -> None:
        """Initialize a registry rooted at the provided configs path."""
        self._configs_path = configs_path
        self._config_type = f"{configs_path.name[:-1]}"

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
    def _atomic_write_json(path: Path, data: dict) -> None:
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

    def list_configs(self) -> list[dict]:
        """Return a sorted list of all config records."""
        configs: list[dict] = []
        if self._configs_path.exists():
            for path in self._configs_path.glob("*.json"):
                try:
                    with path.open("r", encoding="utf-8") as f:
                        data = json.load(f)

                    configs.append(
                        {
                            f"{self._config_type}_id": path.stem,
                            **data
                        }
                    )
                except (OSError, json.JSONDecodeError):
                    continue
        configs.sort(key=lambda x: x["updated_at"])
        return configs

    def get_config(self, config_id: str) -> dict:
        """Return a single config by ID or raise FileNotFoundError."""
        path = self._configs_path / f"{config_id}.json"
        if not path.exists():
            raise FileNotFoundError(config_id)

        with path.open("r", encoding="utf-8") as f:
            return {f"{self._config_type}_id": config_id, **json.load(f)}

    def create_config(self, full_config: dict, config_id: str = None, force: bool = False) -> dict:
        """Create or update a config record and return it."""
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
            **full_config
        }

        self._atomic_write_json(path, out)

        return {f"{self._config_type}_id": config_id, **out}

    def delete_config(self, config_id: str) -> bool:
        """Delete a config by ID and return deletion status."""
        path = self._configs_path / f"{config_id}.json"
        if not path.exists():
            raise FileNotFoundError(config_id)
        path.unlink()
        return {f"{self._config_type}_id": config_id, "deleted": True}


class Profiles(BaseRegistry):
    """Registry wrapper for profile configurations."""
    def list(self) -> list[dict]:
        """List all profiles."""
        return self.list_configs()

    def get(self, profile_id: str) -> dict:
        """Return a single profile by ID."""
        return self.get_config(profile_id)

    def create(self, profile: dict, profile_id: str = None, force: bool = False) -> dict:
        """Create or update a profile."""
        return self.create_config(profile, profile_id, force)

    def delete(self, profile_id: str) -> bool:
        """Delete a profile by ID."""
        return self.delete_config(profile_id)


class Lists(BaseRegistry):
    """Registry wrapper for list configurations."""
    def list(self) -> list[dict]:
        """List all lists."""
        return self.list_configs()

    def get(self, list_id: str) -> dict:
        """Return a single list by ID."""
        return self.get_config(list_id)

    def create(self, list_data: dict, list_id: str = None, force: bool = False) -> dict:
        """Create or update a list."""
        return self.create_config(list_data, list_id, force)

    def delete(self, list_id: str) -> bool:
        """Delete a list by ID."""
        return self.delete_config(list_id)
