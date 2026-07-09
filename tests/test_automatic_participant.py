from __future__ import annotations

import json

import httpx
import respx

from pexip_mcp.tools import automatic_participant

from .conftest import BASE_URL, fk, vmr_uri


@respx.mock
async def test_list_automatic_participants_scoped_to_vmr(ctx):
    respx.get(f"{BASE_URL}/conference/").mock(
        return_value=httpx.Response(
            200,
            json={
                "meta": {"total_count": 1, "limit": 2, "offset": 0},
                "objects": [{"id": 7, "name": "AllHands", "resource_uri": vmr_uri(7)}],
            },
        )
    )
    list_route = respx.get(f"{BASE_URL}/automatic_participant/").mock(
        return_value=httpx.Response(
            200, json={"meta": {"total_count": 0, "limit": 20, "offset": 0}, "objects": []}
        )
    )

    await automatic_participant.list_automatic_participants(ctx, vmr="AllHands")

    assert list_route.calls.last.request.url.params["conference"] == vmr_uri(7)


@respx.mock
async def test_add_automatic_participant_resolves_location_and_vmr(ctx):
    respx.get(f"{BASE_URL}/conference/").mock(
        return_value=httpx.Response(
            200,
            json={
                "meta": {"total_count": 1, "limit": 2, "offset": 0},
                "objects": [{"id": 7, "name": "AllHands", "resource_uri": vmr_uri(7)}],
            },
        )
    )
    respx.get(f"{BASE_URL}/system_location/").mock(
        return_value=httpx.Response(
            200,
            json={
                "meta": {"total_count": 1, "limit": 2, "offset": 0},
                "objects": [
                    {"id": 4, "name": "London", "resource_uri": fk("system_location", 4)}
                ],
            },
        )
    )
    post = respx.post(f"{BASE_URL}/automatic_participant/").mock(
        return_value=httpx.Response(201, headers={"Location": fk("automatic_participant", 33)})
    )
    respx.get(f"{BASE_URL}/automatic_participant/33/").mock(
        return_value=httpx.Response(200, json={"id": 33})
    )

    await automatic_participant.add_automatic_participant(
        ctx,
        vmr="AllHands",
        alias="rec@recorder.example.com",
        protocol="sip",
        system_location="London",
        streaming=True,
    )

    payload = json.loads(post.calls.last.request.read())
    assert payload["alias"] == "rec@recorder.example.com"
    assert payload["conference"] == vmr_uri(7)
    assert payload["system_location"] == fk("system_location", 4)
    assert payload["protocol"] == "sip"
    assert payload["streaming"] is True


@respx.mock
async def test_delete_automatic_participant(ctx):
    route = respx.delete(f"{BASE_URL}/automatic_participant/33/").mock(
        return_value=httpx.Response(204)
    )

    result = await automatic_participant.delete_automatic_participant(ctx, 33)

    assert route.called
    assert result == {"deleted": True, "id": 33}
