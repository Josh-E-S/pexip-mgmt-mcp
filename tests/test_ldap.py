from __future__ import annotations

import json

import httpx
import pytest
import respx

from pexip_mcp.client import PexipError
from pexip_mcp.tools import ldap

from .conftest import BASE_URL, fk


@respx.mock
async def test_list_ldap_sources(ctx):
    route = respx.get(f"{BASE_URL}/ldap_sync_source/").mock(
        return_value=httpx.Response(
            200, json={"meta": {"total_count": 0, "limit": 20, "offset": 0,
                                "next": None, "previous": None},
                      "objects": []}
        )
    )

    await ldap.list_ldap_sources(ctx, name_contains="prod")

    assert route.calls.last.request.url.params["name__icontains"] == "prod"


@respx.mock
async def test_get_ldap_source_by_name(ctx):
    respx.get(f"{BASE_URL}/ldap_sync_source/").mock(
        return_value=httpx.Response(
            200,
            json={
                "meta": {"total_count": 1, "limit": 2, "offset": 0,
                         "next": None, "previous": None},
                "objects": [{"id": 5, "name": "corp-ad",
                             "resource_uri": fk("ldap_sync_source", 5)}],
            },
        )
    )
    respx.get(f"{BASE_URL}/ldap_sync_source/5/").mock(
        return_value=httpx.Response(200, json={"id": 5, "name": "corp-ad"})
    )

    result = await ldap.get_ldap_source(ctx, "corp-ad")

    assert result["id"] == 5


@respx.mock
async def test_create_ldap_source_required_fields(ctx):
    post = respx.post(f"{BASE_URL}/ldap_sync_source/").mock(
        return_value=httpx.Response(201, headers={"Location": fk("ldap_sync_source", 1)})
    )
    respx.get(f"{BASE_URL}/ldap_sync_source/1/").mock(
        return_value=httpx.Response(200, json={"id": 1})
    )

    await ldap.create_ldap_source(
        ctx,
        name="corp-ad",
        ldap_server="ldap.example.com",
        ldap_base_dn="DC=example,DC=com",
        bind_username="CN=svc,OU=Service,DC=example,DC=com",
        bind_password="secret",
    )

    payload = json.loads(post.calls.last.request.read())
    assert payload["name"] == "corp-ad"
    assert payload["ldap_server"] == "ldap.example.com"
    assert payload["ldap_base_dn"] == "DC=example,DC=com"
    assert payload["bind_password"] == "secret"


@respx.mock
async def test_update_ldap_source_no_fields_raises(ctx):
    with pytest.raises(PexipError) as exc:
        await ldap.update_ldap_source(ctx, 5)
    assert exc.value.status_code == 400


@respx.mock
async def test_delete_ldap_source(ctx):
    route = respx.delete(f"{BASE_URL}/ldap_sync_source/5/").mock(
        return_value=httpx.Response(204)
    )

    result = await ldap.delete_ldap_source(ctx, 5)

    assert route.called
    assert result == {"deleted": True, "id": 5}
