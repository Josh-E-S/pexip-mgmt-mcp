from __future__ import annotations

import httpx
import respx

from pexip_mcp.tools import infrastructure

from .conftest import BASE_URL, fk


@respx.mock
async def test_list_locations_with_name_contains(ctx):
    route = respx.get(f"{BASE_URL}/system_location/").mock(
        return_value=httpx.Response(
            200, json={"meta": {"total_count": 0, "limit": 20, "offset": 0}, "objects": []}
        )
    )

    await infrastructure.list_locations(ctx, name_contains="lon")

    assert route.calls.last.request.url.params["name__icontains"] == "lon"


@respx.mock
async def test_get_location_by_name(ctx):
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
    respx.get(f"{BASE_URL}/system_location/4/").mock(
        return_value=httpx.Response(200, json={"id": 4, "name": "London"})
    )

    result = await infrastructure.get_location(ctx, "London")

    assert result["name"] == "London"


@respx.mock
async def test_list_conferencing_nodes_filters_by_location_uri(ctx):
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
    list_route = respx.get(f"{BASE_URL}/worker_vm/").mock(
        return_value=httpx.Response(
            200, json={"meta": {"total_count": 0, "limit": 20, "offset": 0}, "objects": []}
        )
    )

    await infrastructure.list_conferencing_nodes(
        ctx, location="London", node_type="CONFERENCING"
    )

    params = list_route.calls.last.request.url.params
    assert params["system_location"] == fk("system_location", 4)
    assert params["node_type"] == "CONFERENCING"


@respx.mock
async def test_get_conferencing_node_by_id(ctx):
    respx.get(f"{BASE_URL}/worker_vm/12/").mock(
        return_value=httpx.Response(200, json={"id": 12, "name": "lon-conf-01"})
    )

    result = await infrastructure.get_conferencing_node(ctx, 12)

    assert result["name"] == "lon-conf-01"
