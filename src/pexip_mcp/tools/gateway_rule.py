"""Gateway routing rule (dial plan) tools.

Gateway rules are Pexip's dial plan: when a call comes in on one protocol
(SIP / H.323 / MS-SIP / Teams / RTMP, etc.) and doesn't match any VMR alias,
these rules decide whether to bridge it somewhere else. A rule has a regex
that matches the dialed string, an optional replacement, a destination
protocol, and a target system_location.

Rules evaluate in ascending `priority` order — first match wins. Same idea
as Asterisk extensions or an Avaya dial plan: the regex/replace pattern is
the part that takes the most thought.
"""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context

from pexip_mcp.client import PexipError, extract_id_from_uri
from pexip_mcp.mcp_app import mcp
from pexip_mcp.tools._helpers import (
    create,
    delete,
    fk_uri,
    get_client,
    read,
    resolve_id_by_field,
    update,
)


# Use _resolve_rule_id so callers can pass either a numeric id or the rule's name.
async def _resolve_rule_id(client, value: int | str) -> int:
    """Resolve `value` (int id, numeric string, or exact rule name) to an int id."""
    return await resolve_id_by_field(client, "gateway_routing_rule", value, field="name")


# Use _resolve_location_uri to turn a friendly location name/id into the FK URI Pexip expects.
async def _resolve_location_uri(client, location: int | str | None) -> str | None:
    """Resolve a system_location reference to its FK URI string, or None if not provided."""
    if location is None:
        return None
    location_id = await resolve_id_by_field(client, "system_location", location, field="name")
    return fk_uri("system_location", location_id)


@mcp.tool(annotations=read("List gateway routing rules"))
async def list_gateway_rules(
    ctx: Context,
    name_contains: str | None = None,
    enabled_only: bool = False,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """List dial plan gateway routing rules, ordered by priority ascending.

    Args:
        name_contains: Case-insensitive substring match on rule name.
        enabled_only: If true, returns only enabled rules.
        limit: Max results.
        offset: Pagination offset.
    """
    params: dict[str, Any] = {"limit": limit, "offset": offset, "order_by": "priority"}
    if name_contains:
        params["name__icontains"] = name_contains
    if enabled_only:
        params["enable"] = "True"
    return await get_client(ctx).list("gateway_routing_rule", **params)


@mcp.tool(annotations=read("Get gateway routing rule"))
async def get_gateway_rule(ctx: Context, rule: int | str) -> dict[str, Any]:
    """Retrieve a gateway routing rule by integer id or exact name."""
    client = get_client(ctx)
    rule_id = await _resolve_rule_id(client, rule)
    return await client.get("gateway_routing_rule", rule_id)


@mcp.tool(annotations=create("Create gateway routing rule"))
async def create_gateway_rule(
    ctx: Context,
    name: str,
    priority: int,
    match_string: str,
    replace_string: str | None = None,
    called_device_type: str | None = None,
    outgoing_protocol: str | None = None,
    outgoing_location: int | str | None = None,
    call_type: str | None = None,
    crypto_mode: str | None = None,
    enable: bool = True,
    description: str | None = None,
) -> dict[str, Any]:
    """Create a new gateway routing rule.

    Rules are evaluated in ascending priority order; the first match wins.

    Args:
        name: Required, unique. Admin-facing label.
        priority: Lower = evaluated earlier. Required.
        match_string: Regex matched against the dialed alias. Required.
        replace_string: Regex replacement applied to derive the destination.
        called_device_type: e.g. "mssip", "lync", "external", "registration", "gms".
        outgoing_protocol: e.g. "sip", "h323", "mssip", "rtmp", "teams".
        outgoing_location: Target system_location id or exact name.
        call_type: "audio" / "video" / "video-only".
        crypto_mode: "best_effort" / "required" / "none".
        enable: Whether the rule is active. Defaults to True.
        description: Free-text description.
    """
    client = get_client(ctx)
    payload: dict[str, Any] = {
        "name": name,
        "priority": priority,
        "match_string": match_string,
        "enable": enable,
    }
    location_uri = await _resolve_location_uri(client, outgoing_location)
    for field, value in (
        ("replace_string", replace_string),
        ("called_device_type", called_device_type),
        ("outgoing_protocol", outgoing_protocol),
        ("outgoing_location", location_uri),
        ("call_type", call_type),
        ("crypto_mode", crypto_mode),
        ("description", description),
    ):
        if value is not None:
            payload[field] = value
    location = await client.create("gateway_routing_rule", payload)
    return await client.get("gateway_routing_rule", extract_id_from_uri(location))


@mcp.tool(annotations=update("Update gateway routing rule"))
async def update_gateway_rule(
    ctx: Context,
    rule: int | str,
    name: str | None = None,
    priority: int | None = None,
    match_string: str | None = None,
    replace_string: str | None = None,
    called_device_type: str | None = None,
    outgoing_protocol: str | None = None,
    outgoing_location: int | str | None = None,
    call_type: str | None = None,
    crypto_mode: str | None = None,
    enable: bool | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Patch a gateway routing rule. Only provided fields are changed.

    Pass the rule's name directly as `rule` — resolved to its id internally, so
    do NOT call get_gateway_rule/list_gateway_rules first. To disable a rule,
    call this with enable=false.

    To re-prioritize a rule, set `priority`. Other rules' priorities are
    not auto-shifted; manage collisions yourself.
    """
    client = get_client(ctx)
    payload: dict[str, Any] = {}
    location_uri = await _resolve_location_uri(client, outgoing_location)
    for field, value in (
        ("name", name),
        ("priority", priority),
        ("match_string", match_string),
        ("replace_string", replace_string),
        ("called_device_type", called_device_type),
        ("outgoing_protocol", outgoing_protocol),
        ("outgoing_location", location_uri),
        ("call_type", call_type),
        ("crypto_mode", crypto_mode),
        ("enable", enable),
        ("description", description),
    ):
        if value is not None:
            payload[field] = value
    if not payload:
        raise PexipError(400, {"detail": "No fields provided to update"})

    rule_id = await _resolve_rule_id(client, rule)
    await client.update("gateway_routing_rule", rule_id, payload)
    return await client.get("gateway_routing_rule", rule_id)


@mcp.tool(annotations=delete("Delete gateway routing rule"))
async def delete_gateway_rule(ctx: Context, rule: int | str) -> dict[str, Any]:
    """Delete a gateway routing rule by id or exact name. Irreversible.

    Pass the rule name directly as `rule` — resolved to its id internally, so do
    NOT call get_gateway_rule/list_gateway_rules first.
    """
    client = get_client(ctx)
    rule_id = await _resolve_rule_id(client, rule)
    await client.delete("gateway_routing_rule", rule_id)
    return {"deleted": True, "id": rule_id}
