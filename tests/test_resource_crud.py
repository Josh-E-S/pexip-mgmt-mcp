from __future__ import annotations

import json

import httpx
import pytest
import respx

from pexip_mcp.client import PexipError
from pexip_mcp.tools import resource_crud

from .conftest import BASE_URL


def _list_url(resource: str) -> str:
    return f"{BASE_URL}/{resource}/"


def _detail_url(resource: str, obj_id: int) -> str:
    return f"{BASE_URL}/{resource}/{obj_id}/"


def _fk_uri(resource: str, obj_id: int) -> str:
    return f"/api/admin/configuration/v1/{resource}/{obj_id}/"


EMPTY_LIST = {"meta": {"total_count": 0, "limit": 20, "offset": 0}, "objects": []}


# ── list_resources ──────────────────────────────────────────────────────────


@respx.mock
async def test_list_resources_basic(ctx):
    route = respx.get(_list_url("sip_proxy")).mock(
        return_value=httpx.Response(200, json=EMPTY_LIST)
    )

    result = await resource_crud.list_resources(ctx, resource="sip_proxy")

    assert route.called
    assert result["objects"] == []


@respx.mock
async def test_list_resources_with_name_contains(ctx):
    route = respx.get(_list_url("role")).mock(
        return_value=httpx.Response(200, json=EMPTY_LIST)
    )

    await resource_crud.list_resources(ctx, resource="role", name_contains="admin")

    assert route.calls.last.request.url.params["name__icontains"] == "admin"


@respx.mock
async def test_list_resources_with_filters(ctx):
    route = respx.get(_list_url("dns_server")).mock(
        return_value=httpx.Response(200, json=EMPTY_LIST)
    )

    await resource_crud.list_resources(
        ctx, resource="dns_server", filters={"custom_field": "value"}
    )

    assert route.calls.last.request.url.params["custom_field"] == "value"


async def test_list_resources_unknown_resource_raises(ctx):
    with pytest.raises(PexipError) as exc:
        await resource_crud.list_resources(ctx, resource="nonexistent_thing")

    assert exc.value.status_code == 400
    assert "nonexistent_thing" in str(exc.value.body)


# ── get_resource ────────────────────────────────────────────────────────────


@respx.mock
async def test_get_resource_by_int_id(ctx):
    get = respx.get(_detail_url("sip_proxy", 5)).mock(
        return_value=httpx.Response(200, json={"id": 5, "name": "proxy-1"})
    )

    result = await resource_crud.get_resource(ctx, resource="sip_proxy", id=5)

    assert get.called
    assert result["name"] == "proxy-1"


@respx.mock
async def test_get_resource_by_name_resolves(ctx):
    respx.get(_list_url("turn_server")).mock(
        return_value=httpx.Response(
            200,
            json={
                "meta": {"total_count": 1, "limit": 2, "offset": 0},
                "objects": [
                    {"id": 3, "name": "eu-turn", "resource_uri": _fk_uri("turn_server", 3)}
                ],
            },
        )
    )
    respx.get(_detail_url("turn_server", 3)).mock(
        return_value=httpx.Response(200, json={"id": 3, "name": "eu-turn"})
    )

    result = await resource_crud.get_resource(ctx, resource="turn_server", id="eu-turn")

    assert result["name"] == "eu-turn"


# ── create_resource ─────────────────────────────────────────────────────────


@respx.mock
async def test_create_resource(ctx):
    post = respx.post(_list_url("dns_server")).mock(
        return_value=httpx.Response(201, headers={"Location": _fk_uri("dns_server", 10)})
    )
    respx.get(_detail_url("dns_server", 10)).mock(
        return_value=httpx.Response(200, json={"id": 10, "name": "ns1"})
    )

    result = await resource_crud.create_resource(
        ctx, resource="dns_server", settings={"name": "ns1", "address": "8.8.8.8"}
    )

    payload = json.loads(post.calls.last.request.read())
    assert payload == {"name": "ns1", "address": "8.8.8.8"}
    assert result["id"] == 10


async def test_create_resource_empty_settings_raises(ctx):
    with pytest.raises(PexipError) as exc:
        await resource_crud.create_resource(ctx, resource="smtp_server", settings={})

    assert exc.value.status_code == 400


# ── update_resource ─────────────────────────────────────────────────────────


@respx.mock
async def test_update_resource_by_id(ctx):
    patch = respx.patch(_detail_url("smtp_server", 7)).mock(
        return_value=httpx.Response(202)
    )
    respx.get(_detail_url("smtp_server", 7)).mock(
        return_value=httpx.Response(200, json={"id": 7, "name": "mail", "port": 587})
    )

    result = await resource_crud.update_resource(
        ctx, resource="smtp_server", id=7, settings={"port": 587}
    )

    payload = json.loads(patch.calls.last.request.read())
    assert payload == {"port": 587}
    assert result["port"] == 587


async def test_update_resource_empty_settings_raises(ctx):
    with pytest.raises(PexipError) as exc:
        await resource_crud.update_resource(
            ctx, resource="smtp_server", id=1, settings={}
        )

    assert exc.value.status_code == 400


# ── delete_resource ─────────────────────────────────────────────────────────


@respx.mock
async def test_delete_resource_by_id(ctx):
    route = respx.delete(_detail_url("ntp_server", 2)).mock(
        return_value=httpx.Response(204)
    )

    result = await resource_crud.delete_resource(ctx, resource="ntp_server", id=2)

    assert route.called
    assert result == {"deleted": True, "resource": "ntp_server", "id": 2}


@respx.mock
async def test_delete_resource_by_name(ctx):
    respx.get(_list_url("stun_server")).mock(
        return_value=httpx.Response(
            200,
            json={
                "meta": {"total_count": 1, "limit": 2, "offset": 0},
                "objects": [
                    {"id": 4, "name": "stun-eu", "resource_uri": _fk_uri("stun_server", 4)}
                ],
            },
        )
    )
    respx.delete(_detail_url("stun_server", 4)).mock(
        return_value=httpx.Response(204)
    )

    result = await resource_crud.delete_resource(ctx, resource="stun_server", id="stun-eu")

    assert result["id"] == 4


# ── registry coverage ──────────────────────────────────────────────────────


def test_registry_has_all_expected_resources():
    expected_prefixes = [
        "sip_proxy", "turn_server", "role", "dns_server",
        "policy_profile", "mjx_integration", "webapp_branding",
    ]
    for r in expected_prefixes:
        assert r in resource_crud.RESOURCE_REGISTRY, f"Missing registry entry: {r}"


# ── docstring inventory stays in sync with the registry ─────────────────────


def test_list_resources_docstring_names_every_registry_resource():
    """The list_resources docstring is the LLM's only way to discover which
    resources the generic CRUD tools cover — every registry key must be in it."""
    doc = resource_crud.list_resources.__doc__ or ""
    missing = [name for name in resource_crud.RESOURCE_REGISTRY if name not in doc]
    assert not missing, f"list_resources docstring is missing: {missing}"
