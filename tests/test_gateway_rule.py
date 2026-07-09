from __future__ import annotations

import json

import httpx
import pytest
import respx

from pexip_mcp.client import PexipError
from pexip_mcp.tools import gateway_rule

from .conftest import BASE_URL, fk


@respx.mock
async def test_list_gateway_rules_orders_by_priority(ctx):
    route = respx.get(f"{BASE_URL}/gateway_routing_rule/").mock(
        return_value=httpx.Response(
            200, json={"meta": {"total_count": 0, "limit": 20, "offset": 0}, "objects": []}
        )
    )

    await gateway_rule.list_gateway_rules(ctx, enabled_only=True, name_contains="teams")

    params = route.calls.last.request.url.params
    assert params["order_by"] == "priority"
    assert params["enable"] == "True"
    assert params["name__icontains"] == "teams"


@respx.mock
async def test_get_gateway_rule_by_id(ctx):
    respx.get(f"{BASE_URL}/gateway_routing_rule/3/").mock(
        return_value=httpx.Response(200, json={"id": 3, "name": "TeamsOut"})
    )

    result = await gateway_rule.get_gateway_rule(ctx, 3)

    assert result["name"] == "TeamsOut"


@respx.mock
async def test_create_gateway_rule_resolves_outgoing_location_name_to_uri(ctx):
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
    post = respx.post(f"{BASE_URL}/gateway_routing_rule/").mock(
        return_value=httpx.Response(201, headers={"Location": fk("gateway_routing_rule", 9)})
    )
    respx.get(f"{BASE_URL}/gateway_routing_rule/9/").mock(
        return_value=httpx.Response(200, json={"id": 9})
    )

    await gateway_rule.create_gateway_rule(
        ctx,
        name="TeamsOut",
        priority=100,
        match_string=r"^teams.*",
        outgoing_location="London",
        outgoing_protocol="teams",
    )

    payload = json.loads(post.calls.last.request.read())
    assert payload["outgoing_location"] == fk("system_location", 4)
    assert payload["match_string"] == r"^teams.*"
    assert payload["enable"] is True


@respx.mock
async def test_create_gateway_rule_no_outgoing_location_omitted(ctx):
    post = respx.post(f"{BASE_URL}/gateway_routing_rule/").mock(
        return_value=httpx.Response(201, headers={"Location": fk("gateway_routing_rule", 1)})
    )
    respx.get(f"{BASE_URL}/gateway_routing_rule/1/").mock(
        return_value=httpx.Response(200, json={"id": 1})
    )

    await gateway_rule.create_gateway_rule(
        ctx, name="r", priority=10, match_string=".*", enable=False
    )

    payload = json.loads(post.calls.last.request.read())
    assert "outgoing_location" not in payload
    assert payload["enable"] is False


@respx.mock
async def test_update_gateway_rule_no_fields_raises_400(ctx):
    with pytest.raises(PexipError) as exc:
        await gateway_rule.update_gateway_rule(ctx, 3)

    assert exc.value.status_code == 400


@respx.mock
async def test_update_gateway_rule_priority_only(ctx):
    patch = respx.patch(f"{BASE_URL}/gateway_routing_rule/3/").mock(
        return_value=httpx.Response(202)
    )
    respx.get(f"{BASE_URL}/gateway_routing_rule/3/").mock(
        return_value=httpx.Response(200, json={"id": 3, "priority": 5})
    )

    await gateway_rule.update_gateway_rule(ctx, 3, priority=5)

    assert json.loads(patch.calls.last.request.read()) == {"priority": 5}


@respx.mock
async def test_delete_gateway_rule(ctx):
    route = respx.delete(f"{BASE_URL}/gateway_routing_rule/3/").mock(
        return_value=httpx.Response(204)
    )

    result = await gateway_rule.delete_gateway_rule(ctx, 3)

    assert route.called
    assert result == {"deleted": True, "id": 3}
