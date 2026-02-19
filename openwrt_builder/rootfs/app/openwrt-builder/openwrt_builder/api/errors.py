"""Shared HTTP error helpers and exception handlers for API routes."""
from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

_LOG = logging.getLogger(__name__)

def error_detail(code: str, reason: str) -> dict[str, str]:
    """Build a v1 error payload body."""
    return {"code": code, "reason": reason}


def http_400(exc: Exception) -> HTTPException:
    """Return v1 400 invalid_request with reason."""
    return HTTPException(status_code=400, detail=error_detail("invalid_request", str(exc)))


def http_404(reason: str) -> HTTPException:
    """Return v1 404 not_found with reason."""
    return HTTPException(status_code=404, detail=error_detail("not_found", reason))


def http_409(reason: str = "conflict") -> HTTPException:
    """Return v1 409 conflict with reason."""
    return HTTPException(status_code=409, detail=error_detail("conflict", reason))


def http_500(exc: Exception, reason: str | None = None) -> HTTPException:
    """Return v1 500 internal_error with reason."""
    return HTTPException(status_code=500, detail=error_detail("internal_error", reason or str(exc)))


def http_502(exc: Exception) -> HTTPException:
    """Return v1 502 upstream_error with reason."""
    return HTTPException(status_code=502, detail=error_detail("upstream_error", str(exc)))


def register_exception_handlers(app: FastAPI) -> None:
    """Register process-wide FastAPI exception handlers."""

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(_: Request, exc: Exception):
        _LOG.exception("Unhandled API exception")
        return JSONResponse(status_code=500, content=error_detail("internal_error", str(exc)))
