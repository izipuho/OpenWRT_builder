"""Files API endpoints (v1).

Thin HTTP layer over :class:`FilesRegistry`:
- validates/unwraps request payloads via FastAPI
- translates domain errors to HTTP 400/404
- returns registry payloads as JSON
"""
from __future__ import annotations

from fastapi import APIRouter, File, Form, Request, UploadFile

from openwrt_builder.api.errors import http_400, http_404
from openwrt_builder.api.files_schemas import FileDeleteOut, FileMetaUpdateIn, FileOut
from openwrt_builder.env import env_path
from openwrt_builder.service.files_registry import FilesRegistry

router = APIRouter(prefix="/api/v1", tags=["files"])
# Single process-local registry instance for file metadata operations.
FILES_REGISTRY = FilesRegistry(env_path("OPENWRT_BUILDER_FILES_DIR"))


@router.get("/files", response_model=list[FileOut])
def list_files(req: Request):
    """List uploaded files with ``id/source_path/target_path`` metadata."""
    _ = req
    return FILES_REGISTRY.list()


@router.post("/file", status_code=201, response_model=FileOut)
def upload_file(req: Request, file: UploadFile = File(...), target_path: str | None = Form(default=None)):
    """Upload one file and optionally set rootfs ``target_path``."""
    _ = req
    try:
        return FILES_REGISTRY.upload(file=file, target_path=target_path)
    except ValueError as exc:
        raise http_400(exc)


@router.put("/file-meta/{file_id}", status_code=200, response_model=FileOut)
def update_file_meta(req: Request, file_id: str, body: FileMetaUpdateIn):
    """Update descriptor metadata for a file by descriptor ID."""
    _ = req
    try:
        return FILES_REGISTRY.update_meta(file_id=file_id, target_path=body.target_path)
    except ValueError as exc:
        raise http_400(exc)
    except FileNotFoundError:
        raise http_404("file_not_found")


@router.delete("/file/{file_path:path}", response_model=FileDeleteOut)
def delete_file(req: Request, file_path: str):
    """Delete uploaded source file by its relative ``source_path``."""
    _ = req
    try:
        return FILES_REGISTRY.delete(file_path)
    except ValueError as exc:
        raise http_400(exc)
    except FileNotFoundError:
        raise http_404("file_not_found")
