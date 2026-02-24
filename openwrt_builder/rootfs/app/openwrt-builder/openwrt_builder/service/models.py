"""Typed service-layer payload models."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

BuildState = Literal["queued", "running", "done", "failed", "canceled"]
ImageKind = Literal["sysupgrade", "factory"]
ArtifactType = Literal["firmware", "metadata"]
ArtifactRole = Literal["primary", "optional", "checksum", "manifest"]


def validate_rel_path(value: str) -> str:
    """Validate and normalize a relative filesystem path."""
    raw = str(value or "").strip().replace("\\", "/")
    if not raw:
        raise ValueError("invalid_path")
    parts = raw.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("invalid_path")
    return "/".join(parts)


def validate_rel_dir(value: str) -> str:
    """Validate and normalize a relative directory path.

    ``.`` is allowed and means "root directory".
    """
    raw = str(value or "").strip().replace("\\", "/")
    if not raw:
        raise ValueError("invalid_path")
    if raw == ".":
        return "."
    parts = raw.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("invalid_path")
    return "/".join(parts)


def validate_output_images(values: list[ImageKind]) -> list[ImageKind]:
    """Validate `output_images` option shape."""
    if not values:
        raise ValueError("invalid_output_images")
    if len(set(values)) != len(values):
        raise ValueError("invalid_output_images")
    return values


class StrictModel(BaseModel):
    """Base model with strict field checks."""

    model_config = ConfigDict(extra="forbid")


class BuildOptionsModel(StrictModel):
    """Normalized build options payload."""

    force_rebuild: bool = False
    debug: bool = False
    output_images: list[ImageKind] = Field(default_factory=lambda: ["sysupgrade"])

    @field_validator("output_images")
    @classmethod
    def _validate_output_images(cls, values: list[ImageKind]) -> list[ImageKind]:
        return validate_output_images(values)


class BuildRequestModel(StrictModel):
    """Build request payload persisted in build metadata."""

    profile_id: str
    platform: str
    target: str
    subtarget: str
    version: str
    options: BuildOptionsModel = Field(default_factory=BuildOptionsModel)


class BuildArtifactModel(StrictModel):
    """Single artifact produced by a build."""

    id: str
    name: str
    path: str
    size: int = Field(ge=0)
    type: ArtifactType
    role: ArtifactRole


class BuildResultModel(StrictModel):
    """Build execution result metadata."""

    artifacts: list[BuildArtifactModel] = Field(min_length=1)


class BuildPhaseEventModel(StrictModel):
    """Single phase/progress event emitted by the runner/executor."""

    at: str
    phase: str
    progress: int = Field(ge=0, le=100)
    message: str | None = None


class BuildLogsModel(StrictModel):
    """Persisted log references and tails for a build."""

    stdout_path: str | None = None
    stderr_path: str | None = None
    stdout_tail: str = ""
    stderr_tail: str = ""
    updated_at: str | None = None


class BuildModel(StrictModel):
    """Build payload persisted to builds registry."""

    build_id: str
    state: BuildState
    created_at: str
    updated_at: str
    progress: int
    message: str | None = None
    phase: str | None = None
    phase_events: list[BuildPhaseEventModel] = Field(default_factory=list)
    logs: BuildLogsModel | None = None
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

    profile_id: str | None = None
    profile: dict[str, Any]


class ListModel(BaseConfigModel):
    """List record payload."""

    list_id: str | None = None
    list: dict[str, Any]


class FileDescriptorModel(StrictModel):
    """Persisted file descriptor."""

    source_path: str
    target_path: str

    @field_validator("source_path")
    @classmethod
    def _validate_source_path(cls, value: str) -> str:
        return validate_rel_path(value)

    @field_validator("target_path")
    @classmethod
    def _validate_target_dir(cls, value: str) -> str:
        return validate_rel_dir(value)


class FileDescriptorsIndexModel(StrictModel):
    """Descriptor index persisted in ``.descriptors.json``."""

    schema_version: int = 1
    files: list[FileDescriptorModel] = Field(default_factory=list)


class FileRowModel(StrictModel):
    """Expanded file row returned by files API/listing."""

    source_path: str
    target_path: str
    size: int = Field(ge=0)
    updated_at: str

    @field_validator("source_path")
    @classmethod
    def _validate_source_path(cls, value: str) -> str:
        return validate_rel_path(value)

    @field_validator("target_path")
    @classmethod
    def _validate_target_dir(cls, value: str) -> str:
        return validate_rel_dir(value)
