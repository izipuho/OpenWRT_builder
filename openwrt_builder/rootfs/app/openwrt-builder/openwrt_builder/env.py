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


def env_str(name: str, default: str | None = None) -> str | None:
    """Return string environment variable, or default when unset/empty."""
    value = os.environ.get(name)
    if value is None:
        return default
    value = value.strip()
    return value if value else default
