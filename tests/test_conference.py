from __future__ import annotations

import json

import httpx
import pytest
import respx

from pexip_mcp.client import PexipError
from pexip_mcp.tools import conference

from .conftest import BASE_URL, vmr_uri


@respx.mock
async def test_list_vmrs_filters_to_service_type_conference(ctx):
    route = respx.get(f"{BASE_URL}/conference/").mock(
        return_value=httpx.Response(
            200, json={"meta": {"total_count": 0, "limit": 20, "offset": 0}, "objects": []}
        )
    )

    await conference.list_vmrs(ctx)

    params = route.calls.last.request.url.params
    assert params["service_type"] == "conference"


@respx.mock
async def test_list_vmrs_uses_icontains_for_name_contains(ctx):
    route = respx.get(f"{BASE_URL}/conference/").mock(
        return_value=httpx.Response(
            200, json={"meta": {"total_count": 0, "limit": 20, "offset": 0}, "objects": []}
        )
    )

    await conference.list_vmrs(ctx, name_contains="stand")

    assert route.calls.last.request.url.params["name__icontains"] == "stand"


@respx.mock
async def test_get_vmr_by_int_id_skips_lookup(ctx):
    get = respx.get(f"{BASE_URL}/conference/42/").mock(
        return_value=httpx.Response(200, json={"id": 42, "name": "Boardroom"})
    )

    result = await conference.get_vmr(ctx, 42)

    assert get.called
    assert result["name"] == "Boardroom"


@respx.mock
async def test_get_vmr_redacts_pins(ctx):
    respx.get(f"{BASE_URL}/conference/42/").mock(
        return_value=httpx.Response(
            200,
            json={"id": 42, "name": "Boardroom", "pin": "1234", "guest_pin": "5678"},
        )
    )

    result = await conference.get_vmr(ctx, 42)

    # Read paths mask PINs so they never reach the model context / provider logs.
    assert result["pin"] == "***REDACTED***"
    assert result["guest_pin"] == "***REDACTED***"
    assert result["name"] == "Boardroom"


@respx.mock
async def test_get_vmr_by_name_resolves_then_fetches(ctx):
    list_route = respx.get(f"{BASE_URL}/conference/").mock(
        return_value=httpx.Response(
            200,
            json={
                "meta": {"total_count": 1, "limit": 2, "offset": 0},
                "objects": [{"id": 7, "name": "Standup", "resource_uri": vmr_uri(7)}],
            },
        )
    )
    get_route = respx.get(f"{BASE_URL}/conference/7/").mock(
        return_value=httpx.Response(200, json={"id": 7, "name": "Standup"})
    )

    result = await conference.get_vmr(ctx, "Standup")

    assert list_route.called
    assert get_route.called
    assert result["name"] == "Standup"


@respx.mock
async def test_get_vmr_name_not_found_raises_404(ctx):
    respx.get(f"{BASE_URL}/conference/").mock(
        return_value=httpx.Response(
            200, json={"meta": {"total_count": 0, "limit": 2, "offset": 0}, "objects": []}
        )
    )

    with pytest.raises(PexipError) as exc:
        await conference.get_vmr(ctx, "ghost")

    assert exc.value.status_code == 404


@respx.mock
async def test_get_vmr_name_ambiguous_raises_409(ctx):
    respx.get(f"{BASE_URL}/conference/").mock(
        return_value=httpx.Response(
            200,
            json={
                "meta": {"total_count": 2, "limit": 2, "offset": 0},
                "objects": [
                    {"id": 1, "name": "Dup", "resource_uri": vmr_uri(1)},
                    {"id": 2, "name": "Dup", "resource_uri": vmr_uri(2)},
                ],
            },
        )
    )

    with pytest.raises(PexipError) as exc:
        await conference.get_vmr(ctx, "Dup")

    assert exc.value.status_code == 409


@respx.mock
async def test_create_vmr_minimal(ctx):
    post = respx.post(f"{BASE_URL}/conference/").mock(
        return_value=httpx.Response(201, headers={"Location": vmr_uri(99)})
    )
    respx.get(f"{BASE_URL}/conference/99/").mock(
        return_value=httpx.Response(
            200, json={"id": 99, "name": "New VMR", "service_type": "conference"}
        )
    )

    await conference.create_vmr(ctx, name="New VMR", allow_no_pin=True)

    payload = json.loads(post.calls.last.request.read())
    assert payload == {"name": "New VMR", "service_type": "conference"}


@respx.mock
async def test_create_vmr_returns_pin_unredacted(ctx):
    # Writes return PINs raw so the caller can confirm the value it just set
    # (contrast get_vmr, which redacts on read).
    respx.post(f"{BASE_URL}/conference/").mock(
        return_value=httpx.Response(201, headers={"Location": vmr_uri(99)})
    )
    respx.get(f"{BASE_URL}/conference/99/").mock(
        return_value=httpx.Response(200, json={"id": 99, "name": "Room", "pin": "1234"})
    )

    result = await conference.create_vmr(ctx, name="Room", pin="1234")

    assert result["pin"] == "1234"


@respx.mock
async def test_create_vmr_aliases_are_wrapped_as_objects(ctx):
    post = respx.post(f"{BASE_URL}/conference/").mock(
        return_value=httpx.Response(201, headers={"Location": vmr_uri(99)})
    )
    respx.get(f"{BASE_URL}/conference/99/").mock(
        return_value=httpx.Response(200, json={"id": 99})
    )

    await conference.create_vmr(
        ctx, name="VMR", aliases=["meet.alice", "1234"], pin="1111", allow_guests=True
    )

    payload = json.loads(post.calls.last.request.read())
    assert payload["aliases"] == [{"alias": "meet.alice"}, {"alias": "1234"}]
    assert payload["pin"] == "1111"
    assert payload["allow_guests"] is True


@respx.mock
async def test_create_vmr_omits_unset_optional_fields(ctx):
    post = respx.post(f"{BASE_URL}/conference/").mock(
        return_value=httpx.Response(201, headers={"Location": vmr_uri(1)})
    )
    respx.get(f"{BASE_URL}/conference/1/").mock(return_value=httpx.Response(200, json={"id": 1}))

    await conference.create_vmr(ctx, name="VMR", allow_no_pin=True)

    payload = json.loads(post.calls.last.request.read())
    assert "pin" not in payload
    assert "tag" not in payload
    assert "aliases" not in payload


@respx.mock
async def test_update_vmr_no_fields_raises_400(ctx):
    with pytest.raises(PexipError) as exc:
        await conference.update_vmr(ctx, 5)

    assert exc.value.status_code == 400


@respx.mock
async def test_update_vmr_patches_then_returns(ctx):
    patch = respx.patch(f"{BASE_URL}/conference/5/").mock(return_value=httpx.Response(202))
    respx.get(f"{BASE_URL}/conference/5/").mock(
        return_value=httpx.Response(200, json={"id": 5, "description": "x"})
    )

    await conference.update_vmr(ctx, 5, description="x")

    payload = json.loads(patch.calls.last.request.read())
    assert payload == {"description": "x"}


@respx.mock
async def test_delete_vmr_by_id(ctx):
    route = respx.delete(f"{BASE_URL}/conference/5/").mock(return_value=httpx.Response(204))

    result = await conference.delete_vmr(ctx, 5)

    assert route.called
    assert result == {"deleted": True, "id": 5}
