"""Files API endpoints (v1)."""
from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from openwrt_builder.env import env_path

router = APIRouter(prefix="/api/v1", tags=["files"])
FILES_DIR = env_path("OPENWRT_BUILDER_FILES_DIR").resolve()


def http_400(e: Exception) -> HTTPException:
    """Return v1 400 invalid_request with reason."""
    return HTTPException(status_code=400, detail={"code": "invalid_request", "reason": str(e)})


def http_404(reason: str) -> HTTPException:
    """Return v1 404 not_found with reason."""
    return HTTPException(status_code=404, detail={"code": "not_found", "reason": reason})


def _safe_rel(path: str) -> Path:
    raw = str(path or "").strip().replace("\\", "/")
    if not raw:
        raise ValueError("empty_path")
    rel = Path(raw)
    if rel.is_absolute() or any(part in {"", ".", ".."} for part in rel.parts):
        raise ValueError("invalid_path")
    return rel


def _resolve_under_root(path: str) -> tuple[Path, Path]:
    rel = _safe_rel(path)
    abs_path = (FILES_DIR / rel).resolve()
    if FILES_DIR != abs_path and FILES_DIR not in abs_path.parents:
        raise ValueError("invalid_path")
    return rel, abs_path


def _ts(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat().replace("+00:00", "Z")


@router.get("/files")
def list_files(req: Request):
    """Return all uploaded files under OPENWRT_BUILDER_FILES_DIR."""
    _ = req
    FILES_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for p in FILES_DIR.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(FILES_DIR).as_posix()
        rows.append(
            {
                "path": rel,
                "size": p.stat().st_size,
                "updated_at": _ts(p),
            }
        )
    rows.sort(key=lambda x: x["updated_at"], reverse=True)
    return rows


@router.post("/file", status_code=201)
def upload_file(req: Request, file: UploadFile = File(...)):
    """Upload one file into OPENWRT_BUILDER_FILES_DIR."""
    _ = req
    try:
        rel, abs_path = _resolve_under_root(file.filename or "")
    except ValueError as e:
        raise http_400(e)

    FILES_DIR.mkdir(parents=True, exist_ok=True)
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    with abs_path.open("wb") as fp:
        shutil.copyfileobj(file.file, fp)

    return {
        "path": rel.as_posix(),
        "size": abs_path.stat().st_size,
        "updated_at": _ts(abs_path),
    }


@router.delete("/file/{file_path:path}")
def delete_file(req: Request, file_path: str):
    """Delete one uploaded file by relative path."""
    _ = req
    try:
        rel, abs_path = _resolve_under_root(file_path)
    except ValueError as e:
        raise http_400(e)

    if not abs_path.exists() or not abs_path.is_file():
        raise http_404("file_not_found")

    abs_path.unlink()
    return {"path": rel.as_posix(), "deleted": True}
