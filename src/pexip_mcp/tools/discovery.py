"""Discovery: what resources exist, which tool reaches each, and what is enabled.

One tool and two MCP resources replace the habit of listing every resource
inside tool descriptions (which cost tokens on every request whether or not the
model needed them):

  pexip_describe_resources   searchable catalog of configuration, status and
                             history resources with the tool to use for each,
                             plus the toolsets enabled in this deployment
  pexip://registry           the same catalog as a cacheable MCP resource
  pexip://schema/{resource}  the live JSON schema of a configuration resource
"""

from __future__ import annotations

import json
from typing import Any, Literal

from mcp.server.fastmcp import Context

from pexip_mcp.client import PexipError
from pexip_mcp.mcp_app import TOOL_PREFIX, mcp
from pexip_mcp.tools._catalog import HISTORY_REGISTRY, STATUS_REGISTRY, TOOLSETS, ResourceSpec
from pexip_mcp.tools._helpers import get_client, read
from pexip_mcp.tools.resource_crud import RESOURCE_REGISTRY, SENSITIVE_RESOURCES

Api = Literal["configuration", "status", "history"]
Detail = Literal["names", "summary", "full"]

# Configuration resources that have dedicated typed tools (everything else in
# RESOURCE_REGISTRY goes through the generic pexip_*_resource tools).
CONFIG_DEDICATED: dict[str, dict[str, Any]] = {
    "conference": {
        "label": "Virtual Meeting Room",
        "list": "list_vmrs",
        "get": "get_vmr",
        "create": "create_vmr",
        "update": "update_vmr",
        "delete": "delete_vmr",
    },
    "conference_alias": {
        "label": "VMR dial alias",
        "list": "list_aliases",
        "create": "add_vmr_alias",
        "delete": "delete_alias",
    },
    "automatic_participant": {
        "label": "automatic participant",
        "list": "list_automatic_participants",
        "create": "add_automatic_participant",
        "delete": "delete_automatic_participant",
    },
    "end_user": {
        "label": "end user",
        "list": "list_end_users",
        "get": "get_end_user",
        "create": "create_end_user",
        "update": "update_end_user",
        "delete": "delete_end_user",
    },
    "device": {
        "label": "device (registration record)",
        "list": "list_devices",
        "get": "get_device",
        "create": "create_device",
        "update": "update_device",
        "delete": "delete_device",
    },
    "gateway_routing_rule": {
        "label": "gateway routing rule",
        "list": "list_gateway_rules",
        "get": "get_gateway_rule",
        "create": "create_gateway_rule",
        "update": "update_gateway_rule",
        "delete": "delete_gateway_rule",
    },
    "ldap_sync_source": {
        "label": "LDAP sync source",
        "list": "list_ldap_sources",
        "get": "get_ldap_source",
        "create": "create_ldap_source",
        "update": "update_ldap_source",
        "delete": "delete_ldap_source",
    },
    "system_location": {
        "label": "system location",
        "list": "list_locations",
        "get": "get_location",
    },
    "worker_vm": {
        "label": "Conferencing Node",
        "list": "list_conferencing_nodes",
        "get": "get_conferencing_node",
    },
    "ivr_theme": {"label": "IVR theme", "list": "list_ivr_themes", "get": "get_ivr_theme"},
    "global": {
        "label": "global settings",
        "get": "get_global_settings",
        "update": "update_global_settings",
    },
}


def _p(name: str | None) -> str | None:
    return f"{TOOL_PREFIX}{name}" if name else None


def _config_entries() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name, spec in CONFIG_DEDICATED.items():
        out.append(
            {
                "api": "configuration",
                "resource": name,
                "label": spec["label"],
                "tools": {k: _p(v) for k, v in spec.items() if k != "label"},
                "generic": False,
                "keywords": [],
            }
        )
    for name, meta in RESOURCE_REGISTRY.items():
        out.append(
            {
                "api": "configuration",
                "resource": name,
                "label": meta["label"],
                "tools": {
                    "list": _p("list_resources"),
                    "get": _p("get_resource"),
                    "create": _p("create_resource"),
                    "update": _p("update_resource"),
                    "delete": _p("delete_resource"),
                },
                "generic": True,
                "lookup_field": meta["lookup_field"],
                "security_critical": name in SENSITIVE_RESOURCES,
                "keywords": [],
            }
        )
    return out


def _spec_entry(spec: ResourceSpec) -> dict[str, Any]:
    tools: dict[str, str] = {}
    if spec.dedicated_list_tool:
        tools["list"] = _p(spec.dedicated_list_tool)  # type: ignore[assignment]
    if spec.dedicated_get_tool:
        tools["get"] = _p(spec.dedicated_get_tool)  # type: ignore[assignment]
    return {
        "api": spec.api,
        "resource": spec.name,
        "label": spec.label,
        "tools": tools,
        "filters": list(spec.filters),
        "keywords": list(spec.keywords),
    }


def catalog_entries() -> list[dict[str, Any]]:
    """Every resource the server knows, across the three read APIs."""
    return (
        _config_entries()
        + [_spec_entry(s) for s in STATUS_REGISTRY.values()]
        + [_spec_entry(s) for s in HISTORY_REGISTRY.values()]
    )


def _matches(entry: dict[str, Any], query: str) -> bool:
    q = query.lower()
    hay = " ".join(
        [entry["resource"], entry["label"], " ".join(entry.get("keywords", []))]
        + [t for t in entry["tools"].values() if t]
    ).lower()
    return all(term in hay for term in q.split())


def _shape(entry: dict[str, Any], detail: Detail) -> Any:
    if detail == "names":
        return f"{entry['api']}/{entry['resource']}"
    if detail == "summary":
        return {
            "api": entry["api"],
            "resource": entry["resource"],
            "label": entry["label"],
            "tools": {k: v for k, v in entry["tools"].items() if v},
        }
    return entry


def toolset_overview(enabled: set[str] | frozenset[str] | None) -> dict[str, Any]:
    return {
        name: {
            "description": ts.description,
            "enabled": (name in enabled) if enabled is not None else None,
            "tool_count": len(ts.tools),
        }
        for name, ts in TOOLSETS.items()
    }


@mcp.tool(annotations=read("Describe resources and tools"))
async def describe_resources(
    ctx: Context,
    api: Api | None = None,
    query: str | None = None,
    detail: Detail = "summary",
) -> dict[str, Any]:
    """Search the catalog of Pexip resources and find the tool that reaches each one.

    Covers all three read APIs: configuration (VMRs, devices, dial plan, ~80
    generic resources), status (live state) and history (CDRs, past alarms). Each
    entry names the resource, a label, and the pexip_* tool for list / get /
    create / update / delete. Also reports which toolsets are enabled in this
    deployment, so a missing tool can be explained rather than guessed at.

    Args:
        api: Restrict to "configuration", "status" or "history".
        query: Space-separated terms matched against resource name, label,
            keywords and tool names (all terms must match), e.g. "teams",
            "sip proxy", "cdr".
        detail: "names" (just api/resource strings), "summary" (default: resource,
            label, tools) or "full" (adds filters, lookup field, security flag).
    """
    entries = catalog_entries()
    if api:
        entries = [e for e in entries if e["api"] == api]
    if query:
        entries = [e for e in entries if _matches(e, query)]
    lifespan = ctx.request_context.lifespan_context
    enabled = getattr(lifespan, "toolsets", None)
    return {
        "count": len(entries),
        "resources": [_shape(e, detail) for e in entries],
        "toolsets": toolset_overview(enabled),
        "hint": (
            "Configuration resources marked generic are reached with pexip_list_resources / "
            "pexip_get_resource / pexip_create_resource / pexip_update_resource / "
            "pexip_delete_resource by passing resource=<name>. Call "
            "pexip_get_resource_schema(resource) for field names before create/update."
        ),
    }


@mcp.resource(
    "pexip://registry",
    name="Pexip resource catalog",
    description="Every configuration, status and history resource with the tool that reaches it.",
    mime_type="application/json",
)
def registry_resource() -> str:
    return json.dumps(
        {"resources": catalog_entries(), "toolsets": toolset_overview(None)}, indent=2
    )


@mcp.resource(
    "pexip://schema/{resource}",
    name="Live configuration schema",
    description="Live JSON schema of one configuration resource from the Management Node.",
    mime_type="application/json",
)
async def schema_resource(resource: str, ctx: Context) -> str:
    try:
        return json.dumps(await get_client(ctx).schema(resource), indent=2)
    except PexipError as e:
        return json.dumps({"error": str(e), "resource": resource})
