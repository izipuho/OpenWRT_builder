from __future__ import annotations

from pydantic import BaseModel
import os


class Settings(BaseModel):
    data_dir: str = os.getenv("DATA_DIR", "/data")
    profiles_dir: str = os.getenv("PROFILES_DIR", "/data/profiles")
    jobs_dir: str = os.getenv("JOBS_DIR", "/data/jobs")
    artifacts_dir: str = os.getenv("ARTIFACTS_DIR", "/data/artifacts")
    cache_dir: str = os.getenv("CACHE_DIR", "/cache")
    max_concurrent_jobs: int = int(os.getenv("MAX_CONCURRENT_JOBS", "1"))


settings = Settings()