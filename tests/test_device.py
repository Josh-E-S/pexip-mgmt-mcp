from __future__ import annotations

import json

import httpx
import pytest
import respx

from pexip_mcp.client import PexipError
from pexip_mcp.tools import device

from .conftest import BASE_URL, STATUS_URL, fk


@respx.mock
async def test_list_devices_builds_filters(ctx):
    route = respx.get(f"{BASE_URL}/device/").mock(
        return_value=httpx.Response(
            200, json={"meta": {"total_count": 0, "limit": 20, "offset": 0}, "objects": []}
        )
    )

    await device.list_devices(ctx, alias_contains="room", owner_email="a@x.com", tag="lab")

    params = route.calls.last.request.url.params
    assert params["alias__icontains"] == "room"
    assert params["primary_owner_email_address"] == "a@x.com"
    assert params["tag"] == "lab"


@respx.mock
async def test_get_device_by_alias_resolves_then_fetches(ctx):
    respx.get(f"{BASE_URL}/device/").mock(
        return_value=httpx.Response(
            200,
            json={
                "meta": {"total_count": 1, "limit": 2, "offset": 0},
                "objects": [{"id": 9, "alias": "room1@x.com", "resource_uri": fk("device", 9)}],
            },
        )
    )
    respx.get(f"{BASE_URL}/device/9/").mock(return_value=httpx.Response(200, json={"id": 9}))

    result = await device.get_device(ctx, "room1@x.com")

    assert result["id"] == 9


@respx.mock
async def test_create_device_omits_unset_fields(ctx):
    post = respx.post(f"{BASE_URL}/device/").mock(
        return_value=httpx.Response(201, headers={"Location": fk("device", 3)})
    )
    respx.get(f"{BASE_URL}/device/3/").mock(return_value=httpx.Response(200, json={"id": 3}))

    await device.create_device(ctx, alias="room1@x.com", enable_sip=True)

    payload = json.loads(post.calls.last.request.read())
    assert payload == {"alias": "room1@x.com", "enable_sip": True}


@respx.mock
async def test_update_device_no_fields_raises_400(ctx):
    with pytest.raises(PexipError) as exc:
        await device.update_device(ctx, 5)

    assert exc.value.status_code == 400


@respx.mock
async def test_update_device_patches(ctx):
    patch = respx.patch(f"{BASE_URL}/device/5/").mock(return_value=httpx.Response(202))
    respx.get(f"{BASE_URL}/device/5/").mock(
        return_value=httpx.Response(200, json={"id": 5, "description": "Lab room"})
    )

    await device.update_device(ctx, 5, description="Lab room")

    assert json.loads(patch.calls.last.request.read()) == {"description": "Lab room"}


@respx.mock
async def test_delete_device_by_id(ctx):
    route = respx.delete(f"{BASE_URL}/device/5/").mock(return_value=httpx.Response(204))

    result = await device.delete_device(ctx, 5)

    assert route.called
    assert result == {"deleted": True, "id": 5}


@respx.mock
async def test_list_registrations_hits_status_api(ctx):
    route = respx.get(f"{STATUS_URL}/registration/").mock(
        return_value=httpx.Response(
            200, json={"meta": {"total_count": 0, "limit": 20, "offset": 0}, "objects": []}
        )
    )

    await device.list_registrations(ctx, protocol="sip")

    assert route.called
    assert route.calls.last.request.url.params["protocol"] == "sip"
