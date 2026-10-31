"""pexip_list_status / pexip_get_status over the status registry."""

from __future__ import annotations

import httpx
import pytest
import respx

from pexip_mcp.client import PexipError
from pexip_mcp.tools import status_generic
from pexip_mcp.tools._catalog import STATUS_REGISTRY

from .conftest import PEXIP_HOST

STATUS = f"https://{PEXIP_HOST}/api/admin/status/v1"


def _page(objects, **meta):
    return httpx.Response(
        200,
        json={
            "objects": objects,
            "meta": {"total_count": len(objects), "limit": 20, "offset": 0, **meta},
        },
    )


async def test_unknown_resource_is_a_helpful_400(ctx):
    with pytest.raises(PexipError) as exc:
        await status_generic.list_status(ctx, resource="nope")
    assert exc.value.status_code == 400 and exc.value.upstream is False
    assert "teamsnode" in str(exc.value)


async def test_subpath_resources_are_not_listable(ctx):
    with pytest.raises(PexipError):
        await status_generic.list_status(ctx, resource="worker_vm/{id}/statistics")


@respx.mock
async def test_list_passes_name_and_validated_filters(ctx):
    route = respx.get(f"{STATUS}/mjx_endpoint/").mock(
        return_value=_page([{"id": "e1", "name": "Boardroom", "status": "ok", "blob": "x"}])
    )
    out = await status_generic.list_status(
        ctx, resource="mjx_endpoint", name_contains="board", filters={"status": "ok"}
    )
    url = str(route.calls.last.request.url)
    assert "name__icontains=board" in url and "status=ok" in url and "limit=20" in url
    assert out["meta"]["response_format"] == "detailed"  # no concise set for mjx_endpoint
    assert out["objects"][0]["name"] == "Boardroom"


@respx.mock
async def test_list_concise_for_resources_with_a_field_set(ctx):
    respx.get(f"{STATUS}/system_location/").mock(
        return_value=_page([{"id": 1, "name": "London", "media_load": 3, "internal_blob": "z"}])
    )
    out = await status_generic.list_status(ctx, resource="system_location")
    assert out["meta"]["response_format"] == "concise"
    assert "internal_blob" not in out["objects"][0] and out["objects"][0]["name"] == "London"


async def test_list_rejects_unsafe_filter_keys(ctx):
    with pytest.raises(PexipError) as exc:
        await status_generic.list_status(ctx, resource="teamsnode", filters={"format": "xml"})
    assert exc.value.status_code == 400


@respx.mock
async def test_fetch_all_walks_pages(ctx):
    respx.get(f"{STATUS}/cloud_node/", params={"limit": "1000", "offset": "0"}).mock(
        return_value=httpx.Response(
            200,
            json={
                "objects": [{"id": "a"}],
                "meta": {"total_count": 2, "limit": 1000, "offset": 0, "next": "/x?offset=1000"},
            },
        )
    )
    respx.get(f"{STATUS}/cloud_node/", params={"limit": "1000", "offset": "1000"}).mock(
        return_value=httpx.Response(
            200,
            json={
                "objects": [{"id": "b"}],
                "meta": {"total_count": 2, "limit": 1000, "offset": 1000, "next": None},
            },
        )
    )
    out = await status_generic.list_status(ctx, resource="cloud_node", fetch_all=True)
    assert [o["id"] for o in out["objects"]] == ["a", "b"]
    assert out["meta"]["truncated"] is False


@respx.mock
async def test_get_by_id_and_subpath(ctx):
    respx.get(f"{STATUS}/teamsnode/tc-01/").mock(
        return_value=httpx.Response(200, json={"id": "tc-01", "ok": True})
    )
    assert (await status_generic.get_status(ctx, resource="teamsnode", id="tc-01"))["ok"] is True

    route = respx.get(f"{STATUS}/worker_vm/3/statistics/").mock(return_value=_page([{"cpu": 12}]))
    out = await status_generic.get_status(ctx, resource="worker_vm/{id}/statistics", id=3)
    assert route.called and out["objects"][0]["cpu"] == 12


def test_every_registry_entry_has_a_label_and_valid_dedicated_tools():
    from pexip_mcp.mcp_app import mcp

    import pexip_mcp.server  # noqa: F401

    names = {t.name for t in mcp._tool_manager.list_tools()}
    for spec in STATUS_REGISTRY.values():
        assert spec.label
        for t in (spec.dedicated_list_tool, spec.dedicated_get_tool):
            assert t is None or f"pexip_{t}" in names, t
