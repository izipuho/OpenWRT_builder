"""Error mappers for builds API endpoints."""
from __future__ import annotations

from fastapi import HTTPException
from pydantic import ValidationError

from openwrt_builder.api.errors import http_400, http_404, http_409, http_500


def map_create_build_error(exc: Exception) -> HTTPException:
    """Map registry errors for build creation endpoint."""
    if isinstance(exc, ValueError):
        return http_400(exc)
    if isinstance(exc, FileNotFoundError):
        return http_404("profile_not_found")
    raise exc


def map_get_build_error(exc: Exception) -> HTTPException:
    """Map registry errors for single build fetch endpoint."""
    if isinstance(exc, ValueError):
        return http_400(exc)
    if isinstance(exc, FileNotFoundError):
        return http_404("build_not_found")
    raise exc


def map_cancel_build_error(exc: Exception) -> HTTPException:
    """Map registry errors for cancel endpoint."""
    if isinstance(exc, ValueError):
        return http_400(exc)
    if isinstance(exc, FileNotFoundError):
        return http_404("build_not_found")
    if isinstance(exc, PermissionError):
        return http_409("already_finished")
    raise exc


def map_delete_build_error(exc: Exception) -> HTTPException:
    """Map registry errors for delete endpoint."""
    if isinstance(exc, ValueError):
        return http_400(exc)
    if isinstance(exc, FileNotFoundError):
        return http_404("build_not_found")
    if isinstance(exc, PermissionError):
        return http_409("build_running")
    raise exc


def map_download_build_error(exc: Exception) -> HTTPException:
    """Map registry errors for download endpoint."""
    if isinstance(exc, ValueError):
        return http_400(exc)
    if isinstance(exc, FileNotFoundError):
        return http_404("artifact_not_found")
    if isinstance(exc, PermissionError):
        return http_409("not_ready")
    raise exc


def invalid_build_payload_error(exc: ValidationError) -> HTTPException:
    """Map schema validation failures for build payloads to 500."""
    return http_500(exc, reason=f"invalid_build_payload: {exc}")
