from __future__ import annotations

import json

import httpx
import pytest
import respx

from pexip_mcp.client import PexipError
from pexip_mcp.tools import end_user

from .conftest import BASE_URL, fk


@respx.mock
async def test_list_end_users_filter_constructs_icontains(ctx):
    route = respx.get(f"{BASE_URL}/end_user/").mock(
        return_value=httpx.Response(
            200, json={"meta": {"total_count": 0, "limit": 20, "offset": 0}, "objects": []}
        )
    )

    await end_user.list_end_users(ctx, email_contains="alice", name_contains="Alice")

    params = route.calls.last.request.url.params
    assert params["primary_email_address__icontains"] == "alice"
    assert params["display_name__icontains"] == "Alice"


@respx.mock
async def test_get_end_user_by_int_id(ctx):
    respx.get(f"{BASE_URL}/end_user/42/").mock(
        return_value=httpx.Response(200, json={"id": 42, "primary_email_address": "a@x.com"})
    )

    result = await end_user.get_end_user(ctx, 42)

    assert result["id"] == 42


@respx.mock
async def test_get_end_user_by_email_resolves_then_fetches(ctx):
    respx.get(f"{BASE_URL}/end_user/").mock(
        return_value=httpx.Response(
            200,
            json={
                "meta": {"total_count": 1, "limit": 2, "offset": 0},
                "objects": [
                    {
                        "id": 7,
                        "primary_email_address": "alice@example.com",
                        "resource_uri": fk("end_user", 7),
                    }
                ],
            },
        )
    )
    respx.get(f"{BASE_URL}/end_user/7/").mock(
        return_value=httpx.Response(200, json={"id": 7})
    )

    result = await end_user.get_end_user(ctx, "alice@example.com")

    assert result["id"] == 7


@respx.mock
async def test_get_end_user_email_not_found_raises_404(ctx):
    respx.get(f"{BASE_URL}/end_user/").mock(
        return_value=httpx.Response(
            200, json={"meta": {"total_count": 0, "limit": 2, "offset": 0}, "objects": []}
        )
    )

    with pytest.raises(PexipError) as exc:
        await end_user.get_end_user(ctx, "ghost@example.com")

    assert exc.value.status_code == 404


@respx.mock
async def test_create_end_user_omits_unset_fields(ctx):
    post = respx.post(f"{BASE_URL}/end_user/").mock(
        return_value=httpx.Response(201, headers={"Location": fk("end_user", 1)})
    )
    respx.get(f"{BASE_URL}/end_user/1/").mock(
        return_value=httpx.Response(200, json={"id": 1})
    )

    await end_user.create_end_user(ctx, primary_email_address="bob@example.com", first_name="Bob")

    payload = json.loads(post.calls.last.request.read())
    assert payload == {"primary_email_address": "bob@example.com", "first_name": "Bob"}


@respx.mock
async def test_update_end_user_no_fields_raises_400(ctx):
    with pytest.raises(PexipError) as exc:
        await end_user.update_end_user(ctx, 5)

    assert exc.value.status_code == 400


@respx.mock
async def test_update_end_user_patches(ctx):
    patch = respx.patch(f"{BASE_URL}/end_user/5/").mock(return_value=httpx.Response(202))
    respx.get(f"{BASE_URL}/end_user/5/").mock(
        return_value=httpx.Response(200, json={"id": 5, "department": "Eng"})
    )

    await end_user.update_end_user(ctx, 5, department="Eng")

    assert json.loads(patch.calls.last.request.read()) == {"department": "Eng"}


@respx.mock
async def test_delete_end_user_by_id(ctx):
    route = respx.delete(f"{BASE_URL}/end_user/5/").mock(return_value=httpx.Response(204))

    result = await end_user.delete_end_user(ctx, 5)

    assert route.called
    assert result == {"deleted": True, "id": 5}
