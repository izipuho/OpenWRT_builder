"""Pydantic DTOs used by files API endpoints."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from openwrt_builder.service.models import validate_file_id, validate_rel_path


class FileOut(BaseModel):
    """Single uploaded file row returned by API."""

    id: str
    source_path: str
    target_path: str
    size: int = Field(ge=0)
    updated_at: datetime

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        return validate_file_id(value)

    @field_validator("source_path", "target_path")
    @classmethod
    def _validate_paths(cls, value: str) -> str:
        return validate_rel_path(value)


class FileMetaUpdateIn(BaseModel):
    """Payload for metadata updates."""

    target_path: str

    @field_validator("target_path")
    @classmethod
    def _validate_target_path(cls, value: str) -> str:
        return validate_rel_path(value)


class FileDeleteOut(BaseModel):
    """Deletion result payload."""

    source_path: str
    deleted: bool
    remaining: int = Field(ge=0)
