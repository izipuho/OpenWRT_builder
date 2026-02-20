"""Pydantic DTOs used by builds API endpoints."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from openwrt_builder.service.models import (
    ArtifactRole,
    ArtifactType,
    BuildState,
    ImageKind,
    validate_output_images,
)


class BuildOptions(BaseModel):
    """Optional build flags."""

    force_rebuild: bool = False
    debug: bool = False
    output_images: list[ImageKind] = Field(default_factory=lambda: ["sysupgrade"])

    @field_validator("output_images")
    @classmethod
    def _validate_output_images(cls, values: list[ImageKind]) -> list[ImageKind]:
        return validate_output_images(values)


class BuildRequest(BaseModel):
    """Build request payload (the 'request' object)."""

    profile_id: str
    platform: str
    target: str
    subtarget: str
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
    phase: str | None = None
    cancel_requested: bool = False
    runner_pid: int | None = None


class BuildArtifactOut(BaseModel):
    """Single build artifact."""

    id: str
    name: str
    path: str
    size: int = Field(ge=0)
    type: ArtifactType
    role: ArtifactRole


class BuildResultOut(BaseModel):
    """Build result payload."""

    artifacts: list[BuildArtifactOut] = Field(min_length=1)


class BuildPhaseEventOut(BaseModel):
    """Single timestamped phase/progress point."""

    at: datetime
    phase: str
    progress: int = Field(ge=0, le=100)
    message: str | None = None


class BuildLogsOut(BaseModel):
    """Log pointers and persisted tails."""

    stdout_path: str | None = None
    stderr_path: str | None = None
    stdout_tail: str = ""
    stderr_tail: str = ""
    updated_at: datetime | None = None


class BuildOut(BuildSummaryOut):
    """Full build representation used in single-build endpoints."""

    request: BuildRequest
    result: BuildResultOut | None = None
    phase_events: list[BuildPhaseEventOut] = Field(default_factory=list)
    logs: BuildLogsOut | None = None


class BuildLogsResponseOut(BaseModel):
    """Tail content of persisted build logs."""

    build_id: str
    state: BuildState
    phase: str | None = None
    updated_at: datetime
    stdout_path: str | None = None
    stderr_path: str | None = None
    stdout: str = ""
    stderr: str = ""
    stdout_truncated: bool = False
    stderr_truncated: bool = False


class CancelOut(BaseModel):
    """Cancel endpoint response."""

    cancel_requested: bool
