"""
Builds API (v1).

This module defines the HTTP contract for "build" objects:
- POST /api/v1/build
- GET  /api/v1/builds
- GET  /api/v1/build/{id}
- POST /api/v1/build/{id}/cancel
- GET  /api/v1/build/{id}/download

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

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field


router = APIRouter(prefix="/api/v1", tags=["builds"])

BuildState = Literal["queued", "running", "done", "failed", "canceled"]


# =========================
# DTOs (request/response)
# =========================

class BuildOptions(BaseModel):
    """
    Optional build flags.

    force_rebuild:
        If true, registry must ignore cache and create a new build.

    debug:
        If true, the flag is forwarded to runner for verbose behavior/logging.
    """
    force_rebuild: bool = False
    debug: bool = False


class BuildRequest(BaseModel):
    """
    Build request payload (the 'request' object).

    Only presence and types are validated here (per contract).
    """
    profile_id: str
    target: str
    version: str
    options: BuildOptions = Field(default_factory=BuildOptions)


class BuildCreateIn(BaseModel):
    """
    POST /api/v1/build request body.
    """
    request: BuildRequest


class BuildSummaryOut(BaseModel):
    """
    Build summary representation.
    Used in GET /api/v1/builds.
    """
    build_id: str
    state: BuildState
    created_at: datetime
    updated_at: datetime
    progress: int = Field(ge=0, le=100)
    message: str|None = None


class BuildResultOut(BaseModel):
    """
    Build result payload.

    path:
        Filesystem path to the produced artifact.
    """
    path: str


class BuildOut(BuildSummaryOut):
    """
    Full build representation.
    Used in GET /api/v1/build/{id} and POST /api/v1/build.
    """
    request: BuildRequest
    result: BuildResultOut|None = None


class CancelOut(BaseModel):
    """
    Cancel endpoint response.
    """
    cancel_requested: bool


# =========================
# Error helpers (contract)
# =========================

def http_400(e: Exception) -> HTTPException:
    """Return v1 400 invalid_request with reason."""
    return HTTPException(status_code=400, detail={"code": "invalid_request", "reason": str(e)})


def http_404(reason: str) -> HTTPException:
    """Return v1 404 not_found with reason."""
    return HTTPException(status_code=404, detail={"code": "not_found", "reason": reason})


def http_409(reason: str) -> HTTPException:
    """Return v1 409 conflict with reason."""
    return HTTPException(status_code=409, detail={"code": "conflict", "reason": reason})


# =========================
# Registry interface (expected)
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
#   get_build_download(build_id: str) -> str
#       Returns filesystem path for artifact download.
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
    except ValueError as e:
        raise http_400(e)
    except FileNotFoundError:
        # Optional mapping if registry checks profile existence early
        raise http_404("profile_not_found")
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "internal_error", "reason": str(e)})

    model = BuildOut.model_validate(build_dict)
    return JSONResponse(
        status_code=201 if created else 200,
        content=model.model_dump(mode="json"),
    )


@router.get("/builds", response_model=list[BuildSummaryOut])
def get_builds(req: Request):
    """
    List builds (summary only).
    """
    reg = req.app.state.builds_registry

    try:
        items = reg.list_builds()
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "internal_error", "reason": str(e)})

    return [BuildSummaryOut.model_validate(x) for x in items]


@router.get("/build/{build_id}", response_model=BuildOut)
def get_build(req: Request, build_id: str):
    """
    Get a single build (full representation).
    """
    reg = req.app.state.builds_registry

    try:
        b = reg.get_build(build_id)
    except ValueError as e:
        raise http_400(e)
    except FileNotFoundError:
        raise http_404("build_not_found")
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "internal_error", "reason": str(e)})

    return BuildOut.model_validate(b)


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
    except ValueError as e:
        raise http_400(e)
    except FileNotFoundError:
        raise http_404("build_not_found")
    except PermissionError:
        raise http_409("already_finished")
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "internal_error", "reason": str(e)})

    if not ok:
        raise http_409("already_finished")

    return CancelOut(cancel_requested=True)


@router.get("/build/{build_id}/download")
def download_build(req: Request, build_id: str):
    """
    Download build artifact.

    Contract:
    - 200: returns a file response (binary)
    - 404: build/artifact not found
    - 409: build not ready (not done)
    """
    reg = req.app.state.builds_registry

    try:
        path = reg.get_build_download(build_id)
    except ValueError as e:
        raise http_400(e)
    except FileNotFoundError:
        raise http_404("artifact_not_found")
    except PermissionError:
        raise http_409("not_ready")
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "internal_error", "reason": str(e)})

    return FileResponse(
        path=path,
        media_type="application/octet-stream",
        filename=f"{build_id}.tar.gz",
    )
