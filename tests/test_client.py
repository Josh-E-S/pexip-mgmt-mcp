"""Tests for the raw HTTP transport layer (`pexip_mcp.client`).

Two groups here:

  - `TestExtractIdFromUri` exercises the pure URI-parsing helper. No network.
  - The async `test_*` functions verify the PexipClient's HTTP behavior using
    the `client` fixture from conftest.py. They wrap themselves with
    `@respx.mock` so every request gets a canned response and no real network
    call happens (see conftest.py docstring for the respx pattern).

If you're new to respx: `respx.get(url).mock(return_value=httpx.Response(...))`
registers a fake response for a URL; `route.called`, `route.call_count`, and
`route.calls.last.request` let the test assert what the client sent.
"""
from __future__ import annotations

import httpx
import pytest
import respx

from pexip_mcp.client import PexipError, extract_id_from_uri

from .conftest import BASE_URL


class TestExtractIdFromUri:
    def test_with_trailing_slash(self):
        assert extract_id_from_uri("/api/admin/configuration/v1/conference/42/") == 42

    def test_without_trailing_slash(self):
        assert extract_id_from_uri("/api/admin/configuration/v1/conference/42") == 42

    def test_full_url(self):
        assert (
            extract_id_from_uri("https://m.example.com/api/admin/configuration/v1/conference/7/")
            == 7
        )


@respx.mock
async def test_list_passes_query_params(client):
    route = respx.get(f"{BASE_URL}/conference/").mock(
        return_value=httpx.Response(
            200,
            json={
                "meta": {"total_count": 0, "limit": 20, "offset": 0},
                "objects": [],
            },
        )
    )
    await client.list("conference", service_type="conference", limit=20, name="foo")

    assert route.called
    request = route.calls.last.request
    assert request.url.params["service_type"] == "conference"
    assert request.url.params["name"] == "foo"
    assert request.url.params["limit"] == "20"


@respx.mock
async def test_list_returns_parsed_body(client):
    payload = {
        "meta": {"total_count": 1, "limit": 20, "offset": 0},
        "objects": [{"id": 1, "name": "Standup"}],
    }
    respx.get(f"{BASE_URL}/conference/").mock(return_value=httpx.Response(200, json=payload))

    result = await client.list("conference")

    assert result == payload


@respx.mock
async def test_get_single(client):
    respx.get(f"{BASE_URL}/conference/5/").mock(
        return_value=httpx.Response(200, json={"id": 5, "name": "Boardroom"})
    )

    result = await client.get("conference", 5)

    assert result["name"] == "Boardroom"


@respx.mock
async def test_create_returns_location(client):
    new_uri = "/api/admin/configuration/v1/conference/99/"
    respx.post(f"{BASE_URL}/conference/").mock(
        return_value=httpx.Response(201, headers={"Location": new_uri})
    )

    location = await client.create("conference", {"name": "New", "service_type": "conference"})

    assert location == new_uri


@respx.mock
async def test_update_sends_patch(client):
    route = respx.patch(f"{BASE_URL}/conference/5/").mock(return_value=httpx.Response(202))

    await client.update("conference", 5, {"description": "updated"})

    assert route.called
    assert route.calls.last.request.method == "PATCH"


@respx.mock
async def test_delete(client):
    route = respx.delete(f"{BASE_URL}/conference/5/").mock(return_value=httpx.Response(204))

    await client.delete("conference", 5)

    assert route.called


@respx.mock
async def test_error_with_json_body(client):
    respx.get(f"{BASE_URL}/conference/1/").mock(
        return_value=httpx.Response(400, json={"name": ["This field is required."]})
    )

    with pytest.raises(PexipError) as exc:
        await client.get("conference", 1)

    assert exc.value.status_code == 400
    assert exc.value.body == {"name": ["This field is required."]}


@respx.mock
async def test_error_with_text_body(client):
    respx.get(f"{BASE_URL}/conference/1/").mock(
        return_value=httpx.Response(500, text="Internal Server Error")
    )

    with pytest.raises(PexipError) as exc:
        await client.get("conference", 1)

    assert exc.value.status_code == 500
    assert exc.value.body == "Internal Server Error"


@respx.mock
async def test_unauthorized(client):
    respx.get(f"{BASE_URL}/conference/").mock(return_value=httpx.Response(401))

    with pytest.raises(PexipError) as exc:
        await client.list("conference")

    assert exc.value.status_code == 401
