from __future__ import annotations
import json
from pathlib import Path
import os
from datetime import datetime, timezone
import re
import tempfile
import shutil

_JSON_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")

def _now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _slug(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s

def _atomic_write_json(path: Path, data: dict) -> None:
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

def _list_configs(conifgs_path: Path) -> list[dict]:
    configs: list[dict] = []
    if conifgs_path.exists():
        for path in conifgs_path.glob("*.json"):
            try:
                with path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                
                configs.append(
                    {
                        f"{conifgs_path.name[:-1]}_id": path.stem,
                        **data
                    }
                )
            except (OSError, json.JSONDecodeError):
                continue
    configs.sort(key=lambda x: x["updated_at"])
    return configs

def _get_config(config_path: Path, config_id: str) -> dict:
    config_type = f"{config_path.name[:-1]}"
    path = config_path / f"{config_id}.json"
    if not path.exists():
        raise FileNotFoundError(config_id)

    with path.open("r", encoding="utf-8") as f:
        return {f"{config_type}_id": config_id, **json.load(f)}

def _create_config(config_path: Path, full_config: dict, config_id: str = None, force: bool = False) -> dict:
    name = full_config["name"]
    schema_version = full_config["schema_version"]
    config_type = f"{config_path.name[:-1]}"

    if not isinstance(name, str) or not name.strip():
        raise ValueError("name")
    if not isinstance(schema_version, int):
        raise ValueError("schema_version")
    if not isinstance(full_config[config_type], dict):
        raise ValueError(config_type)

    config_id = config_id or full_config.get(f"{config_type}_id", _slug(name))
    if not isinstance(config_id, str) or not _JSON_ID_RE.match(config_id):
        raise ValueError(f"{config_type}_id")
    
    path = config_path / f"{config_id}.json"
    if path.exists() and not force:
        raise FileExistsError(config_id)
    
    out = {
        "updated_at": _now_z(),
        **full_config
    }

    _atomic_write_json(path, out)

    return {f"{config_type}_id": config_id, **out}

def _delete_config(config_path: Path, config_id: str) -> bool:
    config_type = f"{config_path.name[:-1]}"
    path = config_path / f"{config_id}.json"
    if not path.exists():
        raise FileNotFoundError(config_id)
    path.unlink()
    return {f"{config_type}_id": config_id, "deleted": True}

class Registry:
    def __init__(self) -> None:
        self._profiles_dir = Path(os.environ["OPENWRT_BUILDER_PROFILES_DIR"])
        self._lists_dir = Path(os.environ["OPENWRT_BUILDER_LISTS_DIR"])
    
    def list_profiles(self) -> list[dict]:
        return _list_configs(self._profiles_dir)
    
    def get_profile(self, profile_id: str) -> dict:
        return _get_config(self._profiles_dir, profile_id)
    
    def create_profile(self, profile: dict, profile_id: str = None, force: bool = False) -> dict:
        return _create_config(self._profiles_dir, profile, profile_id, force)
    
    def delete_profile(self, profile_id: str):
        return _delete_config(self._profiles_dir, profile_id)

    def list_lists(self) -> list[dict]:
        return _list_configs(self._lists_dir)
    
    def get_list(self, list_id: str) -> dict:
        return _get_config(self._lists_dir, list_id)

    def create_list(self, list_data: dict, list_id: str = None, force: bool = False) -> dict:
        return _create_config(self._lists_dir, list_data, list_id, force)

    def delete_list(self, list_id: str):
        return _delete_config(self._lists_dir, list_id)

