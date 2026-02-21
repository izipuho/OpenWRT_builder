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
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import ValidationError

from openwrt_builder.api.errors import http_404, http_502
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
    BuildLogsResponseOut,
    BuildOut,
    BuildSummaryOut,
    CancelOut,
)


router = APIRouter(prefix="/api/v1", tags=["builds"])
SYSUPGRADE_OVERVIEW_URL = "https://sysupgrade.openwrt.org/json/v1/overview.json"
_SYSUPGRADE_OVERVIEW_TTL_SECONDS = 300.0
_sysupgrade_overview_cache: dict[str, Any] | list[Any] | None = None
_sysupgrade_overview_cached_at_monotonic = 0.0


def _fetch_sysupgrade_overview() -> dict[str, Any] | list[Any]:
    """Load sysupgrade overview payload with a small in-process cache."""
    global _sysupgrade_overview_cache, _sysupgrade_overview_cached_at_monotonic

    now = time.monotonic()
    has_fresh_cache = (
        _sysupgrade_overview_cache is not None
        and (now - _sysupgrade_overview_cached_at_monotonic) < _SYSUPGRADE_OVERVIEW_TTL_SECONDS
    )
    if has_fresh_cache:
        return _sysupgrade_overview_cache

    try:
        req = UrlRequest(
            SYSUPGRADE_OVERVIEW_URL,
            headers={
                "Accept": "application/json",
                "User-Agent": "openwrt-builder/1.0",
            },
        )
        with urlopen(req, timeout=8) as res:
            payload = json.loads(res.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
        # Prefer stale data over hard failure when upstream is temporarily unavailable.
        if _sysupgrade_overview_cache is not None:
            return _sysupgrade_overview_cache
        raise http_502(e)

    if not isinstance(payload, (dict, list)):
        raise http_502(ValueError("sysupgrade overview returned unexpected payload type"))

    _sysupgrade_overview_cache = payload
    _sysupgrade_overview_cached_at_monotonic = now
    return payload


def _extract_versions_from_overview(payload: dict[str, Any] | list[Any]) -> list[str]:
    """Extract latest version list from overview payload."""
    versions: list[str] = []

    if isinstance(payload, dict):
        raw_latest = payload.get("latest")
        if isinstance(raw_latest, list):
            for item in raw_latest:
                if isinstance(item, str) and item.strip():
                    versions.append(item.strip())

        if not versions:
            # Backward compatibility with legacy payload layouts.
            direct_versions = payload.get("versions")
            if isinstance(direct_versions, list):
                for item in direct_versions:
                    if isinstance(item, str):
                        v = item.strip()
                        if v:
                            versions.append(v)
                    elif isinstance(item, dict):
                        raw_version = item.get("version")
                        if isinstance(raw_version, str) and raw_version.strip():
                            versions.append(raw_version.strip())
            elif isinstance(direct_versions, dict):
                for raw_version in direct_versions.keys():
                    if isinstance(raw_version, str) and raw_version.strip():
                        versions.append(raw_version.strip())

    deduped: list[str] = []
    seen: set[str] = set()
    for v in versions:
        if v in seen:
            continue
        seen.add(v)
        deduped.append(v)
    return deduped


def _platform_from_profile_node(node: Any) -> str | None:
    if isinstance(node, str):
        value = node.strip()
        return value or None
    if not isinstance(node, dict):
        return None
    for key in ("id", "name", "profile", "platform", "device"):
        raw = node.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return None


def _normalize_target_subtarget(target_raw: str, subtarget_raw: str | None = None) -> tuple[str, str | None]:
    target = str(target_raw or "").strip()
    subtarget = str(subtarget_raw or "").strip() or None
    if target and "/" in target and subtarget is None:
        parts = target.split("/", 1)
        target = parts[0].strip()
        subtarget = parts[1].strip() or None
    return target, subtarget


def _add_tree_leaf(
    tree: dict[str, dict[str, dict[str, set[str]]]],
    version: str,
    target: str,
    subtarget: str,
    platform: str | None = None,
) -> None:
    versions = tree.setdefault(version, {})
    targets = versions.setdefault(target, {})
    profiles = targets.setdefault(subtarget, set())
    if platform:
        profiles.add(platform)


def _parse_profiles_node(raw_profiles: Any) -> list[str]:
    if not isinstance(raw_profiles, list):
        return []
    out: list[str] = []
    for item in raw_profiles:
        platform = _platform_from_profile_node(item)
        if platform:
            out.append(platform)
    return out


def _parse_subtargets_node(
    tree: dict[str, dict[str, dict[str, set[str]]]],
    version: str,
    target: str,
    raw_subtargets: Any,
) -> None:
    if isinstance(raw_subtargets, dict):
        for key, value in raw_subtargets.items():
            subtarget = str(key or "").strip()
            if not subtarget:
                continue
            if isinstance(value, dict):
                platforms = _parse_profiles_node(value.get("profiles"))
            elif isinstance(value, str):
                platform = value.strip()
                platforms = [platform] if platform else []
            else:
                platforms = _parse_profiles_node(value)
            _add_tree_leaf(tree, version, target, subtarget)
            for platform in platforms:
                _add_tree_leaf(tree, version, target, subtarget, platform)
        return

    if not isinstance(raw_subtargets, list):
        return

    for item in raw_subtargets:
        if isinstance(item, str):
            subtarget = item.strip()
            if subtarget:
                _add_tree_leaf(tree, version, target, subtarget)
            continue
        if not isinstance(item, dict):
            continue
        subtarget = str(item.get("subtarget") or item.get("name") or "").strip()
        if not subtarget:
            continue
        _add_tree_leaf(tree, version, target, subtarget)
        for platform in _parse_profiles_node(item.get("profiles")):
            _add_tree_leaf(tree, version, target, subtarget, platform)


def _parse_targets_node(
    tree: dict[str, dict[str, dict[str, set[str]]]],
    version: str,
    raw_targets: Any,
) -> None:
    if isinstance(raw_targets, dict):
        for key, value in raw_targets.items():
            target, subtarget_from_key = _normalize_target_subtarget(str(key or ""))
            if not target:
                continue
            if isinstance(value, dict):
                raw_subtargets = value.get("subtargets")
                if raw_subtargets is not None:
                    _parse_subtargets_node(tree, version, target, raw_subtargets)
                    continue
                platforms = _parse_profiles_node(value.get("profiles"))
            elif isinstance(value, str):
                platform = value.strip()
                platforms = [platform] if platform else []
            else:
                platforms = _parse_profiles_node(value)

            effective_subtarget = subtarget_from_key or "generic"
            _add_tree_leaf(tree, version, target, effective_subtarget)
            for platform in platforms:
                _add_tree_leaf(tree, version, target, effective_subtarget, platform)
        return

    if not isinstance(raw_targets, list):
        return

    for item in raw_targets:
        if isinstance(item, str):
            target, subtarget = _normalize_target_subtarget(item)
            if target and subtarget:
                _add_tree_leaf(tree, version, target, subtarget)
            continue
        if not isinstance(item, dict):
            continue

        target, subtarget = _normalize_target_subtarget(
            str(item.get("target") or item.get("name") or ""),
            str(item.get("subtarget") or ""),
        )
        if not target:
            continue

        raw_subtargets = item.get("subtargets")
        if raw_subtargets is not None:
            _parse_subtargets_node(tree, version, target, raw_subtargets)
            continue

        effective_subtarget = subtarget or "generic"
        _add_tree_leaf(tree, version, target, effective_subtarget)
        for platform in _parse_profiles_node(item.get("profiles")):
            _add_tree_leaf(tree, version, target, effective_subtarget, platform)


def _targets_for_latest_version(payload: dict[str, Any] | list[Any], version: str) -> Any | None:
    """Resolve raw targets for a version from latest-only branch data."""
    if not isinstance(payload, dict):
        return None

    latest_versions = set(_extract_versions_from_overview(payload))
    if version not in latest_versions:
        return None

    # Current ASU layout: find branch that contains the selected latest version.
    for _, branch_node in payload.items():
        if not isinstance(branch_node, dict):
            continue
        branch_versions = branch_node.get("versions")
        if not isinstance(branch_versions, list):
            continue
        has_version = any(isinstance(v, str) and v.strip() == version for v in branch_versions)
        if not has_version:
            continue
        return branch_node.get("targets")

    # Backward compatibility: direct version-keyed object.
    version_node = payload.get(version)
    if isinstance(version_node, dict):
        return version_node.get("targets")

    return None


def _tree_for_version_targets(version: str, raw_targets: Any) -> dict[str, dict[str, set[str]]]:
    tree: dict[str, dict[str, dict[str, set[str]]]] = {}
    _parse_targets_node(tree, version, raw_targets)
    return tree.get(version, {})


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
    """Return build versions derived from sysupgrade overview payload."""
    overview = _fetch_sysupgrade_overview()
    latest = _extract_versions_from_overview(overview)
    if not latest:
        raise http_502(ValueError("sysupgrade overview does not contain versions"))
    return {"latest": latest}


@router.get("/build-targets")
def get_build_targets(version: str):
    """Return available targets for a version."""
    overview = _fetch_sysupgrade_overview()
    raw_targets = _targets_for_latest_version(overview, version)
    if raw_targets is None:
        raise http_404("version_not_found")
    targets_tree = _tree_for_version_targets(version, raw_targets)
    return {"version": version, "targets": sorted(targets_tree.keys())}


@router.get("/build-subtargets")
def get_build_subtargets(version: str, target: str):
    """Return available subtargets for a version/target."""
    overview = _fetch_sysupgrade_overview()
    raw_targets = _targets_for_latest_version(overview, version)
    if raw_targets is None:
        raise http_404("version_not_found")
    version_targets = _tree_for_version_targets(version, raw_targets)
    target_subtargets = version_targets.get(target)
    if target_subtargets is None:
        raise http_404("target_not_found")
    return {
        "version": version,
        "target": target,
        "subtargets": sorted(target_subtargets.keys()),
    }


@router.get("/build-platforms")
def get_build_platforms(version: str, target: str, subtarget: str):
    """Return available platform/profile names for version/target/subtarget."""
    overview = _fetch_sysupgrade_overview()
    raw_targets = _targets_for_latest_version(overview, version)
    if raw_targets is None:
        raise http_404("version_not_found")
    version_targets = _tree_for_version_targets(version, raw_targets)
    target_subtargets = version_targets.get(target)
    if target_subtargets is None:
        raise http_404("target_not_found")
    platforms = target_subtargets.get(subtarget)
    if platforms is None:
        raise http_404("subtarget_not_found")
    return {
        "version": version,
        "target": target,
        "subtarget": subtarget,
        "platforms": sorted(platforms),
    }


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


@router.get("/build/{build_id}/logs", response_model=BuildLogsResponseOut)
def get_build_logs(req: Request, build_id: str, limit: int = 20000):
    """Get persisted log tails for a build."""
    reg = req.app.state.builds_registry

    try:
        payload = reg.get_build_logs(build_id, limit=limit)
    except (ValueError, FileNotFoundError) as e:
        raise map_get_build_error(e)

    try:
        return BuildLogsResponseOut.model_validate(payload)
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
