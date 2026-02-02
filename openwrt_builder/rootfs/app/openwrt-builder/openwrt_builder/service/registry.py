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
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
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


class Registry:
    def __init__(self) -> None:
        self._profiles_dir = Path(os.environ["OPENWRT_BUILDER_PROFILES_DIR"])
        self._lists_dir = Path(os.environ["OPENWRT_BUILDER_LISTS_DIR"])
    
    def debug(self):
        return Path("/").iterdir()

    def list_profiles(self) -> list[dict]:
        profiles: list[dict] = _list_configs(self._profiles_dir)
        #profiles.sort(key=lambda x: x.get("updated_at", reversed=True)) 
        return profiles
    
    def create_profile(self, profile: dict) -> dict:
        name = profile.get("name")
        schema_version = profile.get("schema_version")
        profile = profile.get("profile")

        if not isinstance(name, str) or not name.strip():
            raise ValueError("name")
        if not isinstance(schema_version, int):
            raise ValueError("schema_version")
        if not isinstance(profile, dict):
            raise ValueError("profile")

        profile_id = profile.get("profile_id")
        if profile_id is None:
            profile_id = _slug(name)
        if not isinstance(profile_id, str) or not _JSON_ID_RE.match(profile_id):
            raise ValueError("profile_id")

        path = self._profiles_dir / f"{profile_id}.json"
        if path.exists():
            raise FileExistsError(profile_id)

        out = {
            "name": name,
            "schema_version": schema_version,
            "updated_at": _now_z(),
            "profile": profile,
        }
        _atomic_write_json(path, out)

        # API-ответ включает id, хотя в файле id не храним
        return {"profile_id": profile_id, **out}

    def list_lists(self) -> list[dict]:
        lists: list[dict] = _list_configs(self._lists_dir)
        return lists

    def create_list(self, list_data: dict) -> dict:
        name = list_data.get("name")
        schema_version = list_data.get("schema_version")
        list_data = list_data.get("list")

        if not isinstance(name, str) or not name.strip():
            raise ValueError("name")
        if not isinstance(schema_version, int):
            raise ValueError("schema_version")
        if not isinstance(list_data, dict):
            raise ValueError("list")

        list_id = list_data.get("list_id")
        if profile_id is None:
            profile_id = _slug(name)
        if not isinstance(profile_id, str) or not _JSON_ID_RE.match(profile_id):
            raise ValueError("profile_id")

        path = self._profiles_dir / f"{profile_id}.json"
        if path.exists():
            raise FileExistsError(profile_id)

        out = {
            "name": name,
            "schema_version": schema_version,
            "updated_at": _now_z(),
            "profile": profile,
        }
        _atomic_write_json(path, out)

        # API-ответ включает id, хотя в файле id не храним
        return {"profile_id": profile_id, **out}
