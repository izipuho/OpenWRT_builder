"""Profiles and lists API endpoints (v1)."""
from fastapi import APIRouter, Request

from openwrt_builder.api.errors import http_400, http_404, http_409

router = APIRouter(prefix="/api/v1", tags=["profiles", "lists"])


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
