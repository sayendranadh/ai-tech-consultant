"""Hand-written Task 1 KB client: timeout + bounded retries.

No live calls in tests. Live calls occur only when constructed with a real base_url
and bearer token and used against a running Task 1 service.
"""
from __future__ import annotations

import logging
import time

import httpx
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)


class KBQueryResponse(BaseModel):
    status: str
    answer: str = ""
    sources: list[dict] = Field(default_factory=list)
    escalation_required: bool = False


class KBUnavailableError(RuntimeError):
    pass


class HTTPKBClient:
    def __init__(self, base_url: str, bearer_token: str, timeout_ms: int = 30000, max_retries: int = 2) -> None:
        self._base = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {bearer_token}"}
        self._timeout = timeout_ms / 1000.0
        self._max_retries = max_retries

    def query(self, question: str) -> dict:
        last: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                with httpx.Client(timeout=self._timeout) as c:
                    resp = c.post(f"{self._base}/query", headers=self._headers, json={"question": question})
                if resp.status_code == 200:
                    return KBQueryResponse.model_validate(resp.json()).model_dump()
                if resp.status_code in (429, 500, 502, 503, 504):
                    last = KBUnavailableError(f"kb status {resp.status_code}")
                    time.sleep(0.3 * (2 ** attempt))
                    continue
                last = KBUnavailableError(f"kb rejected query: {resp.text[:200]}")
                break
            except Exception as exc:  # noqa: BLE001
                last = KBUnavailableError(str(exc))
                time.sleep(0.3 * (2 ** attempt))
        raise last or KBUnavailableError("kb unavailable")
