"""Conference (VMR) tools — CRUD for Virtual Meeting Rooms.

A VMR (Virtual Meeting Room) is Pexip's persistent meeting room: a long-lived
room with a name, optional PIN, allowed layouts, and one or more aliases that
let people dial in. Under the hood it's a `conference` resource with
`service_type="conference"` (Pexip's `conference` table also holds VAEs and
gateway calls — we always filter to service_type=conference here).

Aliases (the actual dial strings) live in a sibling resource — see `alias.py`.
"""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context

from pexip_mcp.client import PexipError, extract_id_from_uri
from pexip_mcp.mcp_app import mcp
from pexip_mcp.tools._helpers import (
    create,
    delete,
    get_client,
    read,
    redact_secrets,
    resolve_id_by_field,
    update,
)


# Use _resolve_vmr_id to turn a friendly VMR name (or numeric id) into the int id Pexip wants.
async def _resolve_vmr_id(client, vmr: int | str) -> int:
    """Resolve `vmr` (int id, numeric string, or exact name) to a VMR integer id."""
    return await resolve_id_by_field(
        client, "conference", vmr, field="name", service_type="conference"
    )


@mcp.tool(annotations=read("List VMRs"))
async def list_vmrs(
    ctx: Context,
    name: str | None = None,
    name_contains: str | None = None,
    tag: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """List VMRs (Pexip conference objects with service_type=conference).

    Args:
        name: Exact name match.
        name_contains: Case-insensitive substring match on name.
        tag: Filter by tag.
        limit: Max results (default 20). Use 0 to return all (avoid on large platforms).
        offset: Pagination offset.
    """
    params: dict[str, Any] = {"service_type": "conference", "limit": limit, "offset": offset}
    if name:
        params["name"] = name
    if name_contains:
        params["name__icontains"] = name_contains
    if tag:
        params["tag"] = tag
    return redact_secrets(await get_client(ctx).list("conference", **params))


@mcp.tool(annotations=read("Get VMR"))
async def get_vmr(ctx: Context, vmr: int | str) -> dict[str, Any]:
    """Retrieve a VMR by integer id or by exact name."""
    client = get_client(ctx)
    vmr_id = await _resolve_vmr_id(client, vmr)
    # Read paths mask PINs (like every secret field); create/update return them
    # raw so the caller can confirm the value it just set.
    return redact_secrets(await client.get("conference", vmr_id))


@mcp.tool(annotations=create("Create VMR"))
async def create_vmr(
    ctx: Context,
    name: str,
    aliases: list[str] | None = None,
    pin: str | None = None,
    guest_pin: str | None = None,
    allow_guests: bool | None = None,
    description: str | None = None,
    tag: str | None = None,
    host_view: str | None = None,
    guest_view: str | None = None,
    allow_no_pin: bool = False,
) -> dict[str, Any]:
    """Create a new VMR.

    Secure by default: creating a room with no host PIN and no guest PIN is
    refused unless you pass allow_no_pin=True. A PIN-less room can be joined by
    anyone who learns the alias, so an open room must be an explicit choice.

    Args:
        name: Admin-facing label (must be unique).
        aliases: Optional list of dial strings to attach. Each becomes a conference_alias.
        pin: Host PIN.
        guest_pin: Guest PIN.
        allow_guests: Whether guests are allowed.
        description: Free-text description.
        tag: Free-form grouping tag.
        host_view: Host layout name (e.g. "one_main_zero_pips").
        guest_view: Guest layout name.
        allow_no_pin: Set True to intentionally create an unprotected (PIN-less)
            room. Leave False (default) to require at least one PIN.
    """
    if pin is None and guest_pin is None and not allow_no_pin:
        raise PexipError(
            400,
            {
                "pin": [
                    "Refusing to create a VMR with no PIN. Set a `pin` (and/or "
                    "`guest_pin`), or pass allow_no_pin=True to deliberately create "
                    "an open room joinable by anyone who knows the alias."
                ]
            },
        )
    payload: dict[str, Any] = {"name": name, "service_type": "conference"}
    if aliases:
        payload["aliases"] = [{"alias": a} for a in aliases]
    for field, value in (
        ("pin", pin),
        ("guest_pin", guest_pin),
        ("allow_guests", allow_guests),
        ("description", description),
        ("tag", tag),
        ("host_view", host_view),
        ("guest_view", guest_view),
    ):
        if value is not None:
            payload[field] = value

    client = get_client(ctx)
    location = await client.create("conference", payload)
    return await client.get("conference", extract_id_from_uri(location))


@mcp.tool(annotations=update("Update VMR"))
async def update_vmr(
    ctx: Context,
    vmr: int | str,
    name: str | None = None,
    pin: str | None = None,
    guest_pin: str | None = None,
    allow_guests: bool | None = None,
    description: str | None = None,
    tag: str | None = None,
    host_view: str | None = None,
    guest_view: str | None = None,
) -> dict[str, Any]:
    """Patch a VMR's fields. Only provided fields are changed.

    Pass the VMR's name directly as `vmr` (e.g. "Boardroom") — this tool resolves
    the name to its id internally, so do NOT call get_vmr/list_vmrs first.

    To modify aliases, use add_vmr_alias / delete_alias rather than this tool.
    """
    payload: dict[str, Any] = {}
    for field, value in (
        ("name", name),
        ("pin", pin),
        ("guest_pin", guest_pin),
        ("allow_guests", allow_guests),
        ("description", description),
        ("tag", tag),
        ("host_view", host_view),
        ("guest_view", guest_view),
    ):
        if value is not None:
            payload[field] = value
    if not payload:
        raise PexipError(400, {"detail": "No fields provided to update"})

    client = get_client(ctx)
    vmr_id = await _resolve_vmr_id(client, vmr)
    await client.update("conference", vmr_id, payload)
    return await client.get("conference", vmr_id)


@mcp.tool(annotations=delete("Delete VMR"))
async def delete_vmr(ctx: Context, vmr: int | str) -> dict[str, Any]:
    """Delete a VMR by id or exact name. Irreversible.

    Pass the VMR name directly as `vmr` — resolved to its id internally, so do
    NOT call get_vmr/list_vmrs first.
    """
    client = get_client(ctx)
    vmr_id = await _resolve_vmr_id(client, vmr)
    await client.delete("conference", vmr_id)
    return {"deleted": True, "id": vmr_id}
