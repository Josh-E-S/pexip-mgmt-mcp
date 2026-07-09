"""Read-only tools for infrastructure resources — system locations and Conferencing Nodes.

Two key Pexip nouns live here:

  - Conferencing Node (`worker_vm` in the API): a media-handling worker VM. This
    is where the actual audio/video mixing happens for calls. Two flavors —
    "CONFERENCING" nodes mix media, "PROXYING" nodes only proxy signaling /
    media on behalf of edge clients.
  - system_location: a logical bucket of those nodes, typically one per
    datacenter or cloud region. Gateway rules and dial-outs target a location,
    and Pexip picks an actual node from inside it.

Configuration changes for these resources typically happen via deployment
tooling (cloud bursting, manual node bring-up) and are intentionally NOT
exposed as MCP tools — only reads.
"""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context

from pexip_mcp.mcp_app import mcp
from pexip_mcp.tools._helpers import fk_uri, get_client, read, resolve_id_by_field


@mcp.tool(annotations=read("List system locations"))
async def list_locations(
    ctx: Context,
    name_contains: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """List system locations (logical groupings of Conferencing Nodes,
    typically per datacenter / region)."""
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if name_contains:
        params["name__icontains"] = name_contains
    return await get_client(ctx).list("system_location", **params)


@mcp.tool(annotations=read("Get system location"))
async def get_location(ctx: Context, location: int | str) -> dict[str, Any]:
    """Retrieve a system location by integer id or by exact name."""
    client = get_client(ctx)
    loc_id = await resolve_id_by_field(client, "system_location", location, field="name")
    return await client.get("system_location", loc_id)


@mcp.tool(annotations=read("List conferencing nodes"))
async def list_conferencing_nodes(
    ctx: Context,
    location: int | str | None = None,
    name_contains: str | None = None,
    node_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """List Conferencing Nodes (the worker_vm resource).

    Args:
        location: System location id or exact name to filter by.
        name_contains: Case-insensitive substring match on node name.
        node_type: "CONFERENCING" or "PROXYING".
        limit: Max results.
        offset: Pagination offset.
    """
    client = get_client(ctx)
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if location is not None:
        loc_id = await resolve_id_by_field(client, "system_location", location, field="name")
        params["system_location"] = fk_uri("system_location", loc_id)
    if name_contains:
        params["name__icontains"] = name_contains
    if node_type:
        params["node_type"] = node_type
    return await client.list("worker_vm", **params)


@mcp.tool(annotations=read("Get conferencing node"))
async def get_conferencing_node(ctx: Context, node: int | str) -> dict[str, Any]:
    """Retrieve a Conferencing Node by integer id or by exact name."""
    client = get_client(ctx)
    node_id = await resolve_id_by_field(client, "worker_vm", node, field="name")
    return await client.get("worker_vm", node_id)
