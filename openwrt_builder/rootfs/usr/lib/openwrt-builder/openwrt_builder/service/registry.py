from __future__ import annotations
import json
from pathlib import Path
import os



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
