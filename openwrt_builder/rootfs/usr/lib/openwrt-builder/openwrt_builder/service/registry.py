from __future__ import annotations
import json
from pathlib import Path
import os
from datetime import datetime, timezone
import re
import tempfile


def _now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slug(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s


def _atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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

class Registry:
    def __init__(self) -> None:
        self._profiles_dir = Path(os.environ["PROFILES_DIR"])
        self._lists_dir = Path(os.environ["LISTS_DIR"])
    
    def debug(self):
        return Path("/").iterdir()

    def list_profiles(self) -> list[dict]:
        profiles: list[dict] = []
        if self._profiles_dir.exists():
            for path in self._profiles_dir.glob("*.json"):
                try:
                    with path.open("r", encoding="utf-8") as f:
                        data = json.load(f)
                    
                    profiles.append(
                        {
                            "profile_id": path.stem,
                            "name": data.get("name", path.stem),
                            "schema_version": data.get("schema_version", 1),
                            "updated_at": data.get("updated_at"),
                        }
                    )
                except (OSError, json.JSONDecodeError):
                    continue
        #profiles.sort(key=lambda x: x.get("updated_at", reversed=True)) 
        return profiles
    
    def create_profile(self, doc: dict) -> dict:
        name = doc.get("name")
        schema_version = doc.get("schema_version")
        profile = doc.get("profile")

        if not isinstance(name, str) or not name.strip():
            raise ValueError("name")
        if not isinstance(schema_version, int):
            raise ValueError("schema_version")
        if not isinstance(profile, dict):
            raise ValueError("profile")

        profile_id = doc.get("profile_id")
        if profile_id is None:
            profile_id = _slug(name)
            if not profile_id:
                raise ValueError("profile_id")
        if not isinstance(profile_id, str) or not _PROFILE_ID_RE.match(profile_id):
            raise ValueError("profile_id")

        path = PROFILES_DIR / f"{profile_id}.json"
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
        lists: list[dict] = []
        if self._lists_dir.exists():
            for path in self._lists_dir.glob("*.json"):
                try:
                    with path.open("r", encoding="utf-8") as f:
                        data = json.load(f)
                    
                    lists.append(
                        {
                            "list_id": path.stem,
                            "name": data.get("name", path.stem),
                            "schema_version": data.get("schema_version", 1),
                            "updated_at": data.get("updated_at"),
                            "profile": data.get("profile", {})
                        }
                    )
                except (OSError, json.JSONDecodeError):
                    continue
                return lists
