from __future__ import annotations

import json

import httpx
import respx

from pexip_mcp.tools import alias

from .conftest import BASE_URL, vmr_uri


@respx.mock
async def test_list_aliases_filters_by_vmr_uri(ctx):
    respx.get(f"{BASE_URL}/conference/").mock(
        return_value=httpx.Response(
            200,
            json={
                "meta": {"total_count": 1, "limit": 2, "offset": 0},
                "objects": [{"id": 7, "name": "Standup", "resource_uri": vmr_uri(7)}],
            },
        )
    )
    list_route = respx.get(f"{BASE_URL}/conference_alias/").mock(
        return_value=httpx.Response(
            200, json={"meta": {"total_count": 0, "limit": 20, "offset": 0}, "objects": []}
        )
    )

    await alias.list_aliases(ctx, vmr="Standup")

    assert list_route.calls.last.request.url.params["conference"] == vmr_uri(7)


@respx.mock
async def test_add_vmr_alias_sends_conference_fk_uri(ctx):
    post = respx.post(f"{BASE_URL}/conference_alias/").mock(
        return_value=httpx.Response(
            201, headers={"Location": "/api/admin/configuration/v1/conference_alias/55/"}
        )
    )
    respx.get(f"{BASE_URL}/conference_alias/55/").mock(
        return_value=httpx.Response(200, json={"id": 55, "alias": "meet.alice"})
    )

    await alias.add_vmr_alias(ctx, vmr=7, alias="meet.alice")

    payload = json.loads(post.calls.last.request.read())
    assert payload == {"alias": "meet.alice", "conference": vmr_uri(7)}


@respx.mock
async def test_delete_alias(ctx):
    route = respx.delete(f"{BASE_URL}/conference_alias/55/").mock(
        return_value=httpx.Response(204)
    )

    result = await alias.delete_alias(ctx, 55)

    assert route.called
    assert result == {"deleted": True, "id": 55}
