from __future__ import annotations

import httpx
import pytest
import pytest_asyncio
import respx

from pexip_mcp.client import PexipClient, PexipError, _compute_retry_delay

from .conftest import BASE_URL, PEXIP_HOST


@pytest_asyncio.fixture
async def fast_client(monkeypatch):
    """A client whose asyncio.sleep is a no-op so retry tests run instantly."""

    async def _no_sleep(_):
        return None

    monkeypatch.setattr("pexip_mcp.client.asyncio.sleep", _no_sleep)
    c = PexipClient(host=PEXIP_HOST, username="admin", password="x", max_retries=3)
    try:
        yield c
    finally:
        await c.aclose()


def test_compute_retry_delay_uses_retry_after_seconds():
    response = httpx.Response(429, headers={"Retry-After": "7"})
    assert _compute_retry_delay(response, attempt=0) == 7.0


def test_compute_retry_delay_caps_retry_after_at_30():
    response = httpx.Response(429, headers={"Retry-After": "9999"})
    assert _compute_retry_delay(response, attempt=0) == 30.0


def test_compute_retry_delay_falls_back_to_exponential():
    response = httpx.Response(429)
    assert _compute_retry_delay(response, attempt=0) == 1.0
    assert _compute_retry_delay(response, attempt=2) == 4.0


def test_compute_retry_delay_invalid_header_falls_back():
    response = httpx.Response(429, headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"})
    # Unparseable as float, falls back to exponential at attempt=1 → 2.0
    assert _compute_retry_delay(response, attempt=1) == 2.0


@respx.mock
async def test_retry_429_then_succeeds(fast_client):
    route = respx.get(f"{BASE_URL}/conference/")
    route.side_effect = [
        httpx.Response(429, headers={"Retry-After": "0"}),
        httpx.Response(429, headers={"Retry-After": "0"}),
        httpx.Response(
            200,
            json={
                "meta": {"total_count": 0, "limit": 20, "offset": 0,
                         "next": None, "previous": None},
                "objects": [],
            },
        ),
    ]

    result = await fast_client.list("conference")

    assert route.call_count == 3
    assert result["objects"] == []


@respx.mock
async def test_retry_exhausted_raises_429(fast_client):
    route = respx.get(f"{BASE_URL}/conference/").mock(
        return_value=httpx.Response(429, json={"detail": "rate limited"})
    )

    with pytest.raises(PexipError) as exc:
        await fast_client.list("conference")

    assert exc.value.status_code == 429
    # max_retries=3 means 1 initial + 3 retries = 4 calls total
    assert route.call_count == 4


@respx.mock
async def test_no_retry_on_non_429(fast_client):
    route = respx.get(f"{BASE_URL}/conference/").mock(
        return_value=httpx.Response(401, json={"detail": "auth"})
    )

    with pytest.raises(PexipError) as exc:
        await fast_client.list("conference")

    assert exc.value.status_code == 401
    assert route.call_count == 1
