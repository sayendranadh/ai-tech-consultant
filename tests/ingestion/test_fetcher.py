import httpx
import pytest

from task1_knowledge_brain.ingestion.config import IngestionConfig
from task1_knowledge_brain.ingestion.fetcher import (
    PermanentFetchError,
    PoliteFetcher,
    TransientFetchError,
    robots_allows,
)


@pytest.mark.asyncio
async def test_retry_transient_then_success():
    call_count = {"n": 0}

    async def handler(request):
        call_count["n"] += 1
        if call_count["n"] < 3:
            return httpx.Response(503, content=b"busy")
        return httpx.Response(200, content=b"ok")

    cfg = IngestionConfig(KB_MAX_RETRIES=3, KB_BACKOFF_BASE_SECONDS=0.001, KB_BACKOFF_MAX_SECONDS=0.01)
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, headers={"User-Agent": "t"}) as client:
        fetcher = PoliteFetcher(cfg, client=client)
        res = await fetcher.fetch("https://support.brilliantdirectories.com/x")
        assert res.content == b"ok"
        assert call_count["n"] == 3


@pytest.mark.asyncio
async def test_retry_exhausted_transient():
    async def handler(request):
        return httpx.Response(503, content=b"busy")

    cfg = IngestionConfig(KB_MAX_RETRIES=2, KB_BACKOFF_BASE_SECONDS=0.001, KB_BACKOFF_MAX_SECONDS=0.01)
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, headers={"User-Agent": "t"}) as client:
        fetcher = PoliteFetcher(cfg, client=client)
        with pytest.raises(TransientFetchError):
            await fetcher.fetch("https://support.brilliantdirectories.com/x")


@pytest.mark.asyncio
async def test_permanent_404_not_retried():
    call_count = {"n": 0}

    async def handler(request):
        call_count["n"] += 1
        return httpx.Response(404)

    cfg = IngestionConfig(KB_MAX_RETRIES=5, KB_BACKOFF_BASE_SECONDS=0.001, KB_BACKOFF_MAX_SECONDS=0.01)
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, headers={"User-Agent": "t"}) as client:
        fetcher = PoliteFetcher(cfg, client=client)
        with pytest.raises(PermanentFetchError):
            await fetcher.fetch("https://support.brilliantdirectories.com/x")
        assert call_count["n"] == 1


def test_robots_absent_allows_all():
    assert robots_allows(None, "/anything")


def test_robots_disallow():
    txt = "User-agent: *\nDisallow: /private\n"
    assert not robots_allows(txt, "/private/page")
    assert robots_allows(txt, "/public/page")
