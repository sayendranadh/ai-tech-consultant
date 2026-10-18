"""Polite async fetcher with bounded retries and exponential backoff."""
from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass

import httpx
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from .config import IngestionConfig

log = logging.getLogger(__name__)

TRANSIENT_STATUS = {429, 500, 502, 503, 504}
PERMANENT_STATUS = {400, 401, 403, 404, 410, 451}


class PermanentFetchError(RuntimeError):
    """Failures that should never be retried within a run."""


class TransientFetchError(RuntimeError):
    """Failures eligible for bounded retry."""


@dataclass(frozen=True)
class FetchResult:
    url: str
    status_code: int
    content: bytes
    last_modified_header: str | None


class PoliteFetcher:
    def __init__(self, cfg: IngestionConfig, client: httpx.AsyncClient | None = None) -> None:
        self._cfg = cfg
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=cfg.request_timeout_seconds,
            headers={"User-Agent": cfg.user_agent},
            follow_redirects=True,
        )
        self._sem = asyncio.Semaphore(cfg.concurrency)
        self._rate_lock = asyncio.Lock()
        self._last_request_at = 0.0
        self._min_interval = 1.0 / cfg.requests_per_second

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _rate_limit(self) -> None:
        async with self._rate_lock:
            loop = asyncio.get_running_loop()
            now = loop.time()
            wait = self._min_interval - (now - self._last_request_at)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request_at = loop.time()

    async def _one_attempt(self, url: str) -> FetchResult:
        await self._rate_limit()
        async with self._sem:
            resp = await self._client.get(url)
        if resp.status_code in TRANSIENT_STATUS:
            raise TransientFetchError(f"transient status {resp.status_code} for {url}")
        if resp.status_code in PERMANENT_STATUS:
            raise PermanentFetchError(f"permanent status {resp.status_code} for {url}")
        if resp.status_code >= 400:
            # Treat unknown 4xx/5xx conservatively: 4xx permanent, 5xx transient.
            if 400 <= resp.status_code < 500:
                raise PermanentFetchError(f"status {resp.status_code} for {url}")
            raise TransientFetchError(f"status {resp.status_code} for {url}")
        return FetchResult(url=url, status_code=resp.status_code, content=resp.content, last_modified_header=resp.headers.get("last-modified"))

    async def fetch(self, url: str) -> FetchResult:
        """Fetch with retry. Raises PermanentFetchError or TransientFetchError (after exhaustion)."""
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self._cfg.max_retries),
                wait=wait_exponential_jitter(
                    initial=self._cfg.backoff_base_seconds,
                    max=self._cfg.backoff_max_seconds,
                    jitter=random.uniform(0, 0.5),
                ),
                retry=retry_if_exception_type((TransientFetchError, httpx.TransportError, httpx.TimeoutException)),
                reraise=True,
            ):
                with attempt:
                    return await self._one_attempt(url)
        except PermanentFetchError:
            raise
        except RetryError as exc:
            raise TransientFetchError(f"retries exhausted for {url}") from exc
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            raise TransientFetchError(f"network failure for {url}: {exc}") from exc
        raise TransientFetchError(f"unreachable retry path for {url}")


async def fetch_robots(fetcher: PoliteFetcher, sitemap_url: str) -> str | None:
    """Best-effort robots.txt fetch. Returns None when unavailable."""
    from urllib.parse import urlparse
    p = urlparse(sitemap_url)
    robots_url = f"{p.scheme}://{p.netloc}/robots.txt"
    try:
        res = await fetcher.fetch(robots_url)
        return res.content.decode("utf-8", errors="replace")
    except (PermanentFetchError, TransientFetchError):
        return None


def robots_allows(robots_txt: str | None, path: str, user_agent: str = "*") -> bool:
    """Minimal robots.txt parser. Absent robots.txt → allow (standard convention)."""
    if robots_txt is None:
        return True
    current_agent: str | None = None
    allows: list[str] = []
    disallows: list[str] = []
    for raw in robots_txt.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if key == "user-agent":
            current_agent = value
        elif key in ("allow", "disallow") and current_agent in ("*", user_agent):
            (allows if key == "allow" else disallows).append(value)
    # Longest-match wins; allow beats disallow on equal length.
    def _match(prefix: str, p: str) -> bool:
        return p.startswith(prefix)
    best_len = -1
    allowed = True
    for d in disallows:
        if d == "":
            continue
        if _match(d, path) and len(d) >= best_len:
            best_len, allowed = len(d), False
    for a in allows:
        if _match(a, path) and len(a) >= best_len:
            best_len, allowed = len(a), True
    return allowed
