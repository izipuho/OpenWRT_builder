from __future__ import annotations
import json
from pathlib import Path
import os
from datetime import datetime, timezone
import re
import tempfile

_JSON_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")

def _now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slug(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s


def _atomic_write_json(path: Path, data: dict) -> None:
    print(f"AtWrite data: {path}")
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    print(f"AtWrite TMP: {fd, tmp}")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass

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
    return configs

def _create_config(config_path: Path, full_config: dict) -> dict:
    print(f"Incoming data:\n{full_config}")
    name = full_config["name"]
    schema_version = full_config["schema_version"]
    config_type = f"{config_path.name[:-1]}"
    config = full_config[config_type]

    if not isinstance(name, str) or not name.strip():
        raise ValueError("name")
    if not isinstance(schema_version, int):
        raise ValueError("schema_version")
    if not isinstance(config, dict):
        raise ValueError(config_type)

    config_id = config.get(f"{config_type}_id", _slug(name))
    if not isinstance(config_id, str) or not _JSON_ID_RE.match(config_id):
        raise ValueError(f"{config_type}_id")
    
    path = config_path / f"{config_id}.json"
    if path.exists():
        raise FileExistsError(config_id)
    
    out = {
        "updated_at": _now_z(),
        **full_config
    }

    _atomic_write_json(path, out)

    return {f"{config_type}_id": config_id, **out}

class Registry:
    def __init__(self) -> None:
        self._profiles_dir = Path(os.environ["OPENWRT_BUILDER_PROFILES_DIR"])
        self._lists_dir = Path(os.environ["OPENWRT_BUILDER_LISTS_DIR"])
    
    def list_profiles(self) -> list[dict]:
        profiles: list[dict] = _list_configs(self._profiles_dir)
        #profiles.sort(key=lambda x: x.get("updated_at", reversed=True)) 
        return profiles
    
    def create_profile(self, profile: dict) -> dict:
        data: dict = _create_config(self._profiles_dir, profile)
        return data

    def list_lists(self) -> list[dict]:
        lists: list[dict] = _list_configs(self._lists_dir)
        return lists

    def create_list(self, list_data: dict) -> dict:
        data: dict = _create_config(self._lists_dir, list_data)
        return data
