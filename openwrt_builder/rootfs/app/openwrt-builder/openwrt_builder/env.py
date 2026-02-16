"""Environment variable helpers."""
from __future__ import annotations

import os
from pathlib import Path


def env_path(name: str) -> Path:
    """Return required path from environment variable."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"missing_env:{name}")
    return Path(value)
