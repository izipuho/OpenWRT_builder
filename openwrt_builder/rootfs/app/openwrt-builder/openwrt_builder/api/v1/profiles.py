"""Profiles and lists API endpoints (v1)."""
from fastapi import APIRouter, Request

from openwrt_builder.api.errors import http_400, http_404, http_409
from openwrt_builder.env import env_path
from openwrt_builder.service.lists_importer import (
    build_output_payload,
    collect_sources,
    human_name,
    parse_source,
    slugify,
    unique_id,
)

router = APIRouter(prefix="/api/v1", tags=["profiles", "lists"])
LISTS_DIR = env_path("OPENWRT_BUILDER_LISTS_DIR").resolve()


@router.get("/health")
def health():
    """Return a basic health check response."""
    return {"status": "ok"}

# =========================
# Manage Profiles
# =========================

@router.get("/profiles")
def get_profiles(req: Request):
    """Return all available profiles (summary only)."""
    return req.app.state.profiles_registry.list_summary()

@router.get("/profile/{profile_id}", status_code=200)
def get_profile(req: Request, profile_id: str):
    """Return a single profile by ID."""
    reg = req.app.state.profiles_registry
    try:
        return reg.get(profile_id)
    except FileNotFoundError:
        raise http_404("profile_not_found")

@router.post("/profile", status_code=201)
def post_profile(req: Request, body: dict):
    """Create a new profile."""
    reg = req.app.state.profiles_registry
    try:
        return reg.create(body)
    except ValueError as e:
        raise http_400(e)
    except FileExistsError:
        raise http_409()

@router.put("/profile/{profile_id}", status_code=200)
def put_profile(req: Request, profile_id: str, body: dict):
    """Create or replace a profile by ID."""
    reg = req.app.state.profiles_registry
    try:
        return reg.create(body, profile_id, True)
    except ValueError as e:
        raise http_400(e)
    except FileNotFoundError:
        raise http_404("profile_not_found")

@router.delete("/profile/{profile_id}", status_code=200)
def delete_profile(req: Request, profile_id: str):
    """Delete a profile by ID."""
    reg = req.app.state.profiles_registry
    try:
        return reg.delete(profile_id)
    except FileNotFoundError:
        raise http_404("profile_not_found")

# =========================
# Manage lists
# =========================

@router.get("/lists")
def get_lists(req: Request):
    """Return all available lists (summary only)."""
    return req.app.state.lists_registry.list_summary()

@router.get("/list/{list_id}", status_code=200)
def get_list(req: Request, list_id: str):
    """Return a single list by ID."""
    reg = req.app.state.lists_registry
    try:
        return reg.get(list_id)
    except FileNotFoundError:
        raise http_404("list_not_found")

@router.post("/list", status_code=201)
def post_list(req: Request, body: dict):
    """Create a new list."""
    reg = req.app.state.lists_registry
    try:
        return reg.create(body)
    except ValueError as e:
        raise http_400(e)
    except FileExistsError:
        raise http_409()

@router.put("/list/{list_id}", status_code=200)
def put_list(req: Request, list_id: str, body: dict):
    """Create or replace a list by ID."""
    reg = req.app.state.lists_registry
    try:
        return reg.create(body, list_id, True)
    except ValueError as e:
        raise http_400(e)
    except FileNotFoundError:
        raise http_404("list_not_found")

@router.delete("/list/{list_id}", status_code=200)
def delete_list(req: Request, list_id: str):
    """Delete a list by ID."""
    reg = req.app.state.lists_registry
    try:
        return reg.delete(list_id)
    except FileNotFoundError:
        raise http_404("list_not_found")


@router.post("/lists/import", status_code=200)
def import_lists(req: Request):
    """Import list files from OPENWRT_BUILDER_LISTS_DIR/lists."""
    reg = req.app.state.lists_registry
    abs_source = (LISTS_DIR / "raw").resolve()
    if not abs_source.exists() or not abs_source.is_dir():
        raise http_404("source_dir_not_found")
    if LISTS_DIR != abs_source and LISTS_DIR not in abs_source.parents:
        raise http_400(ValueError("invalid_path"))

    sources = collect_sources(abs_source)
    used_ids: set[str] = set()
    created = 0
    skipped = 0
    errors = 0

    for source in sources:
        rel_stem = source.relative_to(abs_source).with_suffix("").as_posix()
        list_id = unique_id(slugify(rel_stem), used_ids)
        exists = False

        try:
            include, exclude, name_from_source = parse_source(source)
            name = name_from_source or human_name(source.stem)
            payload = build_output_payload(name=name, include=include, exclude=exclude)
            try:
                reg.get(list_id)
                exists = True
            except FileNotFoundError:
                exists = False

            if exists:
                skipped += 1
                continue
            reg.create(payload, list_id, False)
            created += 1
        except Exception as exc:
            if isinstance(exc, FileExistsError):
                skipped += 1
                continue
            errors += 1
            continue

    return {
        "source_subdir": "lists",
        "found": len(sources),
        "created": created,
        "skipped": skipped,
        "errors": errors,
    }

# =========================
# Misc
# =========================

@router.post("/debug", status_code=201)
def debug(req: Request, body: dict) -> list:
    """Run simple debug commands and return results."""
    res: list = []
    if body["command"] == "ls":
        from pathlib import Path
        for path in Path(body["path"]).iterdir():
            res.append(path)
    return res
