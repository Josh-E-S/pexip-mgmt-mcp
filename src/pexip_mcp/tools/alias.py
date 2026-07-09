"""Conference alias tools — CRUD for the dial strings that point at a VMR.

A `conference_alias` is the actual string a caller dials to reach a VMR: an
E.164 number ("+155501234"), a SIP URI ("meet@example.com"), or any arbitrary
label. One VMR can have many aliases (e.g. an internal short code plus a full
SIP URI). When matching against incoming calls, Pexip looks aliases up exactly,
so spelling/punctuation matters.
"""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context

from pexip_mcp.client import extract_id_from_uri
from pexip_mcp.mcp_app import mcp
from pexip_mcp.tools._helpers import create, delete, fk_uri, get_client, read, resolve_id_by_field


@mcp.tool(annotations=read("List conference aliases"))
async def list_aliases(
    ctx: Context,
    vmr: int | str | None = None,
    alias: str | None = None,
    alias_contains: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """List conference aliases, optionally scoped to one VMR.

    Args:
        vmr: VMR id or exact name to filter by. Omit for all aliases.
        alias: Exact alias match.
        alias_contains: Case-insensitive substring match.
        limit: Max results.
        offset: Pagination offset.
    """
    client = get_client(ctx)
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if vmr is not None:
        vmr_id = await resolve_id_by_field(
            client, "conference", vmr, field="name", service_type="conference"
        )
        params["conference"] = fk_uri("conference", vmr_id)
    if alias:
        params["alias"] = alias
    if alias_contains:
        params["alias__icontains"] = alias_contains
    return await client.list("conference_alias", **params)


@mcp.tool(annotations=create("Add conference alias"))
async def add_vmr_alias(
    ctx: Context,
    vmr: int | str,
    alias: str,
    description: str | None = None,
) -> dict[str, Any]:
    """Add a conference_alias to a VMR.

    Args:
        vmr: VMR id or exact name.
        alias: The dial string (E.164, URI, or arbitrary).
        description: Optional description.
    """
    client = get_client(ctx)
    vmr_id = await resolve_id_by_field(
        client, "conference", vmr, field="name", service_type="conference"
    )
    payload: dict[str, Any] = {"alias": alias, "conference": fk_uri("conference", vmr_id)}
    if description is not None:
        payload["description"] = description
    location = await client.create("conference_alias", payload)
    return await client.get("conference_alias", extract_id_from_uri(location))


@mcp.tool(annotations=delete("Delete conference alias"))
async def delete_alias(ctx: Context, alias_id: int) -> dict[str, Any]:
    """Delete a conference_alias by id. Use list_aliases first to find the id."""
    await get_client(ctx).delete("conference_alias", alias_id)
    return {"deleted": True, "id": alias_id}
