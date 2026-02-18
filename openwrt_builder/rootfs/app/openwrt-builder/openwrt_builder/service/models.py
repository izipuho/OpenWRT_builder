"""Typed service-layer payload models."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

BuildState = Literal["queued", "running", "done", "failed", "canceled"]


class StrictModel(BaseModel):
    """Base model with strict field checks."""

    model_config = ConfigDict(extra="forbid")


class BuildOptionsModel(StrictModel):
    """Normalized build options payload."""

    force_rebuild: bool = False
    debug: bool = False


class BuildRequestModel(StrictModel):
    """Build request payload persisted in build metadata."""

    profile_id: str
    target: str
    version: str
    options: BuildOptionsModel = Field(default_factory=BuildOptionsModel)


class BuildResultModel(StrictModel):
    """Build execution result metadata."""

    path: str


class BuildModel(StrictModel):
    """Build payload persisted to builds registry."""

    build_id: str
    state: BuildState
    created_at: str
    updated_at: str
    progress: int
    message: str | None = None
    request: BuildRequestModel
    result: BuildResultModel | None = None
    cancel_requested: bool = False
    runner_pid: int | None = None


class BaseConfigModel(StrictModel):
    """Base shape for profile/list records."""

    name: str
    schema_version: int
    updated_at: str | None = None


class ProfileModel(BaseConfigModel):
    """Profile record payload."""

    profile: dict[str, Any]


class ListModel(BaseConfigModel):
    """List record payload."""

    list: dict[str, Any]
