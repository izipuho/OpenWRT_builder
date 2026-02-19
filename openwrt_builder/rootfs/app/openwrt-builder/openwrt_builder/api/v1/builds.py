"""
Builds API (v1).

This module defines the HTTP contract for "build" objects:
- POST /api/v1/build
- GET  /api/v1/builds
- GET  /api/v1/build/{id}
- POST /api/v1/build/{id}/cancel
- DELETE /api/v1/build/{id}
- GET  /api/v1/build/{id}/artifacts
- GET  /api/v1/build/{id}/download/{artifact_id}

HTTP layer responsibilities:
- Parse and validate request payloads (structure + types)
- Delegate actions to app.state.builds_registry (source of truth)
- Convert registry results to response DTOs

This module MUST NOT:
- Run the build process
- Manage queues in memory
- Implement business logic beyond HTTP contract mapping
"""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import ValidationError

from openwrt_builder.api.errors import http_502
from openwrt_builder.api.builds_errors import (
    invalid_build_payload_error,
    map_cancel_build_error,
    map_create_build_error,
    map_delete_build_error,
    map_download_build_error,
    map_get_build_error,
)
from openwrt_builder.api.builds_schemas import (
    BuildArtifactOut,
    BuildCreateIn,
    BuildOut,
    BuildSummaryOut,
    CancelOut,
)


router = APIRouter(prefix="/api/v1", tags=["builds"])
SYSUPGRADE_LATEST_URL = "https://sysupgrade.openwrt.org/api/v1/latest"


# =========================
# Registry interface
# =========================
#
# This module expects req.app.state.builds_registry to provide:
#
#   create_build(request: dict) -> tuple[dict, bool]
#       Returns (build_dict, created) where created:
#         - True  => new build created, HTTP 201
#         - False => cache hit, HTTP 200
#
#   list_builds() -> list[dict]
#       Returns list of build summaries.
#
#   get_build(build_id: str) -> dict
#       Returns full build dict.
#       Raises FileNotFoundError if not found.
#
#   cancel_build(build_id: str) -> bool
#       Returns True if cancel request accepted.
#       Returns False (or raises) if already final.
#       Raises FileNotFoundError if not found.
#
#   delete_build(build_id: str) -> bool
#       Deletes build metadata and artifacts.
#       Raises FileNotFoundError if build not found.
#       Raises PermissionError if build is running.
#
#   list_build_artifacts(build_id: str) -> list[dict]
#       Returns produced artifact metadata.
#
#   get_build_download(build_id: str, artifact_id: str) -> str
#       Returns filesystem path for a specific artifact download.
#       Raises FileNotFoundError if artifact/build not found.
#       Raises PermissionError if build is not ready (not done).
#


# =========================
# Endpoints
# =========================

@router.post("/build")
def post_build(req: Request, body: BuildCreateIn):
    """
    Create a build.

    Contract:
    - Validates request structure and types only.
    - Delegates caching/rebuild decision to registry.
    - Returns:
        * 201 + full build object if created
        * 200 + full build object if cache hit (force_rebuild != true)
    """
    reg = req.app.state.builds_registry

    try:
        build_dict, created = reg.create_build(body.request.model_dump())
    except (ValueError, FileNotFoundError) as e:
        raise map_create_build_error(e)

    try:
        model = BuildOut.model_validate(build_dict)
    except ValidationError as e:
        raise invalid_build_payload_error(e)

    return JSONResponse(
        status_code=201 if created else 200,
        content=model.model_dump(mode="json"),
    )


@router.get("/builds", response_model=list[BuildSummaryOut])
def get_builds(req: Request):
    """List builds (summary only)."""
    reg = req.app.state.builds_registry

    items = reg.list_builds()

    summaries: list[BuildSummaryOut] = []
    for item in items:
        try:
            summaries.append(BuildSummaryOut.model_validate(item))
        except ValidationError:
            continue
    return summaries


@router.get("/build-versions")
def get_build_versions():
    """Return sysupgrade latest payload as-is."""
    try:
        req = UrlRequest(
            SYSUPGRADE_LATEST_URL,
            headers={
                "Accept": "application/json",
                "User-Agent": "openwrt-builder/1.0",
            },
        )
        with urlopen(req, timeout=8) as res:
            payload = json.loads(res.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
        raise http_502(e)

    return payload


@router.get("/build/{build_id}", response_model=BuildOut)
def get_build(req: Request, build_id: str):
    """Get a single build (full representation)."""
    reg = req.app.state.builds_registry

    try:
        b = reg.get_build(build_id)
    except (ValueError, FileNotFoundError) as e:
        raise map_get_build_error(e)

    try:
        return BuildOut.model_validate(b)
    except ValidationError as e:
        raise invalid_build_payload_error(e)


@router.post("/build/{build_id}/cancel", response_model=CancelOut)
def cancel_build(req: Request, build_id: str):
    """
    Request cancellation of a build.

    Contract:
    - 200 {cancel_requested:true} if accepted
    - 404 not_found if build does not exist
    - 409 conflict if build already in a final state (done/canceled)
    """
    reg = req.app.state.builds_registry

    try:
        ok = reg.cancel_build(build_id)
    except (ValueError, FileNotFoundError, PermissionError) as e:
        raise map_cancel_build_error(e)

    if not ok:
        raise map_cancel_build_error(PermissionError("already_finished"))

    return CancelOut(cancel_requested=True)


@router.delete("/build/{build_id}")
def delete_build(req: Request, build_id: str):
    """Delete a build and its artifacts."""
    reg = req.app.state.builds_registry

    try:
        reg.delete_build(build_id)
    except (ValueError, FileNotFoundError, PermissionError) as e:
        raise map_delete_build_error(e)

    return {"deleted": True}


@router.get("/build/{build_id}/artifacts", response_model=list[BuildArtifactOut])
def get_build_artifacts(req: Request, build_id: str):
    """List artifacts of a completed build."""
    reg = req.app.state.builds_registry

    try:
        items = reg.list_build_artifacts(build_id)
    except (ValueError, FileNotFoundError, PermissionError) as e:
        raise map_download_build_error(e)

    out: list[BuildArtifactOut] = []
    for item in items:
        try:
            out.append(BuildArtifactOut.model_validate(item))
        except ValidationError:
            continue
    return out


@router.get("/build/{build_id}/download/{artifact_id}")
def download_build(req: Request, build_id: str, artifact_id: str):
    """
    Download build artifact.

    Contract:
    - 200: returns a file response (binary)
    - 404: build/artifact not found
    - 409: build not ready (not done)
    """
    reg = req.app.state.builds_registry

    try:
        path = reg.get_build_download(build_id, artifact_id)
    except (ValueError, FileNotFoundError, PermissionError) as e:
        raise map_download_build_error(e)

    filename = path.rsplit("/", 1)[-1] or artifact_id
    return FileResponse(
        path=path,
        media_type="application/octet-stream",
        filename=filename,
    )
