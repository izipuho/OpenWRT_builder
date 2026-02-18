"""Pydantic DTOs used by builds API endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

BuildState = Literal["queued", "running", "done", "failed", "canceled"]


class BuildOptions(BaseModel):
    """Optional build flags."""

    force_rebuild: bool = False
    debug: bool = False


class BuildRequest(BaseModel):
    """Build request payload (the 'request' object)."""

    profile_id: str
    target: str
    version: str
    options: BuildOptions = Field(default_factory=BuildOptions)


class BuildCreateIn(BaseModel):
    """POST /api/v1/build request body."""

    request: BuildRequest


class BuildSummaryOut(BaseModel):
    """Build summary representation used in GET /api/v1/builds."""

    build_id: str
    state: BuildState
    created_at: datetime
    updated_at: datetime
    progress: int = Field(ge=0, le=100)
    message: str | None = None
    cancel_requested: bool = False
    runner_pid: int | None = None


class BuildResultOut(BaseModel):
    """Build result payload."""

    path: str


class BuildOut(BuildSummaryOut):
    """Full build representation used in single-build endpoints."""

    request: BuildRequest
    result: BuildResultOut | None = None


class CancelOut(BaseModel):
    """Cancel endpoint response."""

    cancel_requested: bool
