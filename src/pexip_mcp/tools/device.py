"""Device registration tools — CRUD for provisioned registration aliases.

A `device` is an entry in Pexip's "Devices" registry (Users & Devices >
Devices): the alias a software/hardware endpoint registers with, plus the
credentials it authenticates with and which protocols it may use. Registering
a device here is what lets a Connect app or SIP/H.323 endpoint *register* to
the platform so it can be reached by name.

Two related-but-different things:
  - `device` (Configuration API, here) — the long-lived registration *record*:
    permitted alias + credentials + protocol flags.
  - currently-registered endpoints (Status API) — who is registered *right now*.
    Exposed read-only via `list_registrations`.

The alias is the natural handle; these tools accept either an integer id or the
exact alias string everywhere.
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
    paginate_all,
    read,
    redact_secrets,
    resolve_id_by_field,
    update,
)


# Use _resolve_device_id so callers can pass the device alias instead of looking up the id first.
async def _resolve_device_id(client, value: int | str) -> int:
    """Resolve `value` (int id, numeric string, or exact alias) to an int id."""
    return await resolve_id_by_field(client, "device", value, field="alias")


@mcp.tool(annotations=read("List devices"))
async def list_devices(
    ctx: Context,
    alias_contains: str | None = None,
    owner_email: str | None = None,
    tag: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """List provisioned devices (registration records).

    Args:
        alias_contains: Case-insensitive substring match on the device alias.
        owner_email: Filter by primary owner's email address (exact).
        tag: Filter by tag.
        limit: Max results.
        offset: Pagination offset.
    """
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if alias_contains:
        params["alias__icontains"] = alias_contains
    if owner_email:
        params["primary_owner_email_address"] = owner_email
    if tag:
        params["tag"] = tag
    return redact_secrets(await get_client(ctx).list("device", **params))


@mcp.tool(annotations=read("Get device"))
async def get_device(ctx: Context, device: int | str) -> dict[str, Any]:
    """Retrieve a device by integer id or by exact alias."""
    client = get_client(ctx)
    device_id = await _resolve_device_id(client, device)
    return redact_secrets(await client.get("device", device_id))


@mcp.tool(annotations=create("Create device"))
async def create_device(
    ctx: Context,
    alias: str,
    username: str | None = None,
    password: str | None = None,
    description: str | None = None,
    primary_owner_email_address: str | None = None,
    enable_sip: bool | None = None,
    enable_h323: bool | None = None,
    enable_infinity_connect: bool | None = None,
    tag: str | None = None,
) -> dict[str, Any]:
    """Register a new device (permitted registration alias + credentials).

    Args:
        alias: Required. The alias the endpoint registers with (SIP URI / E.164 / label).
        username: Registration username the device authenticates with.
        password: Registration password.
        description: Free-text description.
        primary_owner_email_address: Owning end user's email (links the device to a person).
        enable_sip: Allow SIP registration.
        enable_h323: Allow H.323 registration.
        enable_infinity_connect: Allow Connect (WebRTC) app registration.
        tag: Free-form grouping tag.
    """
    payload: dict[str, Any] = {"alias": alias}
    for field, value in (
        ("username", username),
        ("password", password),
        ("description", description),
        ("primary_owner_email_address", primary_owner_email_address),
        ("enable_sip", enable_sip),
        ("enable_h323", enable_h323),
        ("enable_infinity_connect", enable_infinity_connect),
        ("tag", tag),
    ):
        if value is not None:
            payload[field] = value

    client = get_client(ctx)
    location = await client.create("device", payload)
    return await client.get("device", extract_id_from_uri(location))


@mcp.tool(annotations=update("Update device"))
async def update_device(
    ctx: Context,
    device: int | str,
    alias: str | None = None,
    username: str | None = None,
    password: str | None = None,
    description: str | None = None,
    primary_owner_email_address: str | None = None,
    enable_sip: bool | None = None,
    enable_h323: bool | None = None,
    enable_infinity_connect: bool | None = None,
    tag: str | None = None,
) -> dict[str, Any]:
    """Patch a device by id or exact alias. Only provided fields are changed."""
    payload: dict[str, Any] = {}
    for field, value in (
        ("alias", alias),
        ("username", username),
        ("password", password),
        ("description", description),
        ("primary_owner_email_address", primary_owner_email_address),
        ("enable_sip", enable_sip),
        ("enable_h323", enable_h323),
        ("enable_infinity_connect", enable_infinity_connect),
        ("tag", tag),
    ):
        if value is not None:
            payload[field] = value
    if not payload:
        raise PexipError(400, {"detail": "No fields provided to update"})

    client = get_client(ctx)
    device_id = await _resolve_device_id(client, device)
    await client.update("device", device_id, payload)
    return await client.get("device", device_id)


@mcp.tool(annotations=delete("Delete device"))
async def delete_device(ctx: Context, device: int | str) -> dict[str, Any]:
    """Delete a device by id or exact alias. The endpoint can no longer register. Irreversible."""
    client = get_client(ctx)
    device_id = await _resolve_device_id(client, device)
    await client.delete("device", device_id)
    return {"deleted": True, "id": device_id}


@mcp.tool(annotations=read("List current registrations"))
async def list_registrations(
    ctx: Context,
    alias_contains: str | None = None,
    protocol: str | None = None,
    limit: int = 20,
    offset: int = 0,
    fetch_all: bool = False,
) -> dict[str, Any]:
    """List endpoints currently registered to the platform (live Status API read).

    This is the runtime counterpart to the device records: who is registered
    *right now*, on what node and protocol — not the configured allow-list.

    Args:
        alias_contains: Case-insensitive substring match on the registered alias.
        protocol: "sip" / "h323" / "mssip" / "webrtc".
        limit, offset, fetch_all: Pagination controls (fetch_all walks all pages).
    """
    client = get_client(ctx)
    params: dict[str, Any] = {}
    if alias_contains:
        params["alias__icontains"] = alias_contains
    if protocol:
        params["protocol"] = protocol
    if fetch_all:
        return await paginate_all(client, "registration", api="status", **params)
    params["limit"] = limit
    params["offset"] = offset
    return await client.list("registration", api="status", **params)
