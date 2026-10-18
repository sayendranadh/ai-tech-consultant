"""Consistent error payload envelope: {"error": {"code", "message", "details"}}.

Two handlers:
- HTTPException → envelope with code=int(status), message=str(detail), details=None.
- RequestValidationError → envelope with code=422, message="validation error",
  details=[{"loc": [...], "type": ..., "msg": ...}, ...].
"""
from __future__ import annotations

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.status_code, "message": str(exc.detail), "details": None}},
        headers=getattr(exc, "headers", None),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # FastAPI 0.115 stores errors in exc.errors(); 'ctx' may contain non-serializable values, strip it.
    details = []
    for err in exc.errors():
        details.append({
            "loc": list(err.get("loc", [])),
            "type": err.get("type"),
            "msg": err.get("msg"),
        })
    return JSONResponse(
        status_code=422,
        content={"error": {"code": 422, "message": "validation error", "details": details}},
    )
