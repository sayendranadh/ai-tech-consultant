"""Request-ID middleware. Adds X-Request-ID to responses; logs each request with it."""
from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

log = logging.getLogger("kb.access")


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        rid = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = rid
        start = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            log.error(json.dumps({
                "event": "request_error",
                "request_id": rid,
                "method": request.method,
                "path": request.url.path,
                "elapsed_ms": elapsed_ms,
                "ts": datetime.now(timezone.utc).isoformat(),
            }))
            raise
        elapsed_ms = int((time.monotonic() - start) * 1000)
        response.headers["x-request-id"] = rid
        log.info(json.dumps({
            "event": "request",
            "request_id": rid,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "elapsed_ms": elapsed_ms,
            "ts": datetime.now(timezone.utc).isoformat(),
        }))
        return response
