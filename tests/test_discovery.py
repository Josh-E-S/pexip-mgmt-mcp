"""pexip_describe_resources and the pexip:// MCP resources."""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import respx

from pexip_mcp.tools import discovery
from pexip_mcp.tools._catalog import HISTORY_REGISTRY, STATUS_REGISTRY
from pexip_mcp.tools.resource_crud import RESOURCE_REGISTRY

from .conftest import BASE_URL


def _ctx(client=None, toolsets=frozenset({"core", "rooms"})):
    return SimpleNamespace(
        request_context=SimpleNamespace(
            lifespan_context=SimpleNamespace(pexip=client, toolsets=toolsets)
        )
    )


def test_catalog_covers_every_registry_and_dedicated_resource():
    entries = discovery.catalog_entries()
    names = {(e["api"], e["resource"]) for e in entries}
    for r in RESOURCE_REGISTRY:
        assert ("configuration", r) in names
    for r in discovery.CONFIG_DEDICATED:
        assert ("configuration", r) in names
    for r in STATUS_REGISTRY:
        assert ("status", r) in names
    for r in HISTORY_REGISTRY:
        assert ("history", r) in names
    assert len(names) == len(entries)  # no duplicates


def test_dedicated_tools_are_published_names():
    vmr = next(
        e
        for e in discovery.catalog_entries()
        if e["resource"] == "conference" and e["api"] == "configuration"
    )
    assert vmr["tools"]["list"] == "pexip_list_vmrs"
    assert vmr["generic"] is False
    dns = next(e for e in discovery.catalog_entries() if e["resource"] == "dns_server")
    assert dns["generic"] is True and dns["tools"]["create"] == "pexip_create_resource"
    ssh = next(e for e in discovery.catalog_entries() if e["resource"] == "ssh_authorized_key")
    assert ssh["security_critical"] is True


async def test_describe_filters_by_api_and_query_and_detail():
    out = await discovery.describe_resources(_ctx(), api="status", query="teams")
    assert out["count"] == 2
    assert {e["resource"] for e in out["resources"]} == {"teamsnode", "teamsnode_call"}
    assert out["resources"][0]["tools"]["list"].startswith("pexip_list_teams")

    names = await discovery.describe_resources(_ctx(), query="sip proxy", detail="names")
    assert set(names["resources"]) == {"configuration/sip_proxy", "configuration/mssip_proxy"}

    full = await discovery.describe_resources(_ctx(), query="cdr", detail="full")
    assert (
        full["resources"][0]["resource"] == "participant"
        and "call_quality" in full["resources"][0]["filters"]
    )


async def test_describe_reports_enabled_toolsets():
    out = await discovery.describe_resources(_ctx(toolsets=frozenset({"core", "live"})))
    assert out["toolsets"]["live"]["enabled"] is True
    assert out["toolsets"]["rooms"]["enabled"] is False
    assert out["toolsets"]["core"]["tool_count"] == 3
    assert "pexip_get_resource_schema" in out["hint"]


async def test_describe_with_no_match_returns_empty_not_error():
    out = await discovery.describe_resources(_ctx(), query="zzz-no-such-thing")
    assert out["count"] == 0 and out["resources"] == []


def test_registry_resource_is_json_with_every_entry():
    body = json.loads(discovery.registry_resource())
    assert len(body["resources"]) == len(discovery.catalog_entries())
    assert body["toolsets"]["core"]["enabled"] is None  # static resource: deployment unknown


@respx.mock
async def test_schema_resource_fetches_live_schema(client):
    respx.get(f"{BASE_URL}/conference/schema/").mock(
        return_value=httpx.Response(200, json={"fields": {"name": {"type": "string"}}})
    )
    body = json.loads(await discovery.schema_resource("conference", _ctx(client)))
    assert body["fields"]["name"]["type"] == "string"


@respx.mock
async def test_schema_resource_reports_errors_as_json(client):
    respx.get(f"{BASE_URL}/nope/schema/").mock(return_value=httpx.Response(404, json={}))
    body = json.loads(await discovery.schema_resource("nope", _ctx(client)))
    assert body["resource"] == "nope" and "error" in body
