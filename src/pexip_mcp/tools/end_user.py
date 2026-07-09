"""End user (directory) tools — CRUD for entries in Pexip's user directory.

An `end_user` is a person record (name, email, phone, department, avatar). Pexip
uses this directory for things like the "search for a contact" UX in clients and
for authorization checks. Entries can be created by hand here, or synced
automatically from LDAP (see ldap.py). The `primary_email_address` is the
unique handle — these tools accept either an integer id or that email everywhere.
"""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context

from pexip_mcp.client import PexipError, extract_id_from_uri
from pexip_mcp.mcp_app import mcp
from pexip_mcp.tools._helpers import create, delete, get_client, read, resolve_id_by_field, update


# Use _resolve_end_user_id so callers can pass the user's email instead of looking up the id first.
async def _resolve_end_user_id(client, value: int | str) -> int:
    """Resolve `value` (int id, numeric string, or primary_email_address) to an int id.

    Email is the natural handle here — most LLM-driven flows know a user's email
    long before they know the integer id, so we look it up automatically.
    """
    return await resolve_id_by_field(
        client, "end_user", value, field="primary_email_address"
    )


@mcp.tool(annotations=read("List end users"))
async def list_end_users(
    ctx: Context,
    email_contains: str | None = None,
    name_contains: str | None = None,
    sync_tag: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """List directory end users.

    Args:
        email_contains: Case-insensitive substring match on primary_email_address.
        name_contains: Case-insensitive substring match on display_name.
        sync_tag: Filter by LDAP sync tag.
        limit: Max results.
        offset: Pagination offset.
    """
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if email_contains:
        params["primary_email_address__icontains"] = email_contains
    if name_contains:
        params["display_name__icontains"] = name_contains
    if sync_tag:
        params["sync_tag"] = sync_tag
    return await get_client(ctx).list("end_user", **params)


@mcp.tool(annotations=read("Get end user"))
async def get_end_user(ctx: Context, user: int | str) -> dict[str, Any]:
    """Retrieve an end user by integer id or by primary_email_address."""
    client = get_client(ctx)
    user_id = await _resolve_end_user_id(client, user)
    return await client.get("end_user", user_id)


@mcp.tool(annotations=create("Create end user"))
async def create_end_user(
    ctx: Context,
    primary_email_address: str,
    first_name: str | None = None,
    last_name: str | None = None,
    display_name: str | None = None,
    telephone_number: str | None = None,
    mobile_number: str | None = None,
    title: str | None = None,
    department: str | None = None,
    avatar_url: str | None = None,
) -> dict[str, Any]:
    """Create a new directory end user.

    Args:
        primary_email_address: Required, must be unique.
        first_name, last_name, display_name: Name fields.
        telephone_number, mobile_number: Contact numbers.
        title, department: Organizational fields.
        avatar_url: URL to avatar image.
    """
    payload: dict[str, Any] = {"primary_email_address": primary_email_address}
    for field, value in (
        ("first_name", first_name),
        ("last_name", last_name),
        ("display_name", display_name),
        ("telephone_number", telephone_number),
        ("mobile_number", mobile_number),
        ("title", title),
        ("department", department),
        ("avatar_url", avatar_url),
    ):
        if value is not None:
            payload[field] = value

    client = get_client(ctx)
    location = await client.create("end_user", payload)
    return await client.get("end_user", extract_id_from_uri(location))


@mcp.tool(annotations=update("Update end user"))
async def update_end_user(
    ctx: Context,
    user: int | str,
    first_name: str | None = None,
    last_name: str | None = None,
    display_name: str | None = None,
    telephone_number: str | None = None,
    mobile_number: str | None = None,
    title: str | None = None,
    department: str | None = None,
    avatar_url: str | None = None,
) -> dict[str, Any]:
    """Patch an end user by id or primary_email_address."""
    payload: dict[str, Any] = {}
    for field, value in (
        ("first_name", first_name),
        ("last_name", last_name),
        ("display_name", display_name),
        ("telephone_number", telephone_number),
        ("mobile_number", mobile_number),
        ("title", title),
        ("department", department),
        ("avatar_url", avatar_url),
    ):
        if value is not None:
            payload[field] = value
    if not payload:
        raise PexipError(400, {"detail": "No fields provided to update"})

    client = get_client(ctx)
    user_id = await _resolve_end_user_id(client, user)
    await client.update("end_user", user_id, payload)
    return await client.get("end_user", user_id)


@mcp.tool(annotations=delete("Delete end user"))
async def delete_end_user(ctx: Context, user: int | str) -> dict[str, Any]:
    """Delete an end user by id or primary_email_address. Irreversible."""
    client = get_client(ctx)
    user_id = await _resolve_end_user_id(client, user)
    await client.delete("end_user", user_id)
    return {"deleted": True, "id": user_id}
