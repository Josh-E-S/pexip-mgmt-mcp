"""LDAP sync source tools — wire Pexip's directory to LDAP / Active Directory.

An `ldap_sync_source` tells Pexip to pull user records (name, email, phone)
from an external LDAP or AD server on a schedule and mirror them into the
end_user directory (see end_user.py). Each source is one LDAP server +
bind credentials + search scope; you can have several (e.g. one per region).

Sync results are visible via get_ldap_source — handy for answering "is LDAP
working?" without leaving the conversation.
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


# Use _resolve_source_id so callers can pass either an int id or the source's friendly name.
async def _resolve_source_id(client, source: int | str) -> int:
    """Resolve `source` (int id, numeric string, or exact name) to an int id."""
    return await resolve_id_by_field(client, "ldap_sync_source", source, field="name")


@mcp.tool(annotations=read("List LDAP sync sources"))
async def list_ldap_sources(
    ctx: Context,
    name_contains: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """List configured LDAP / Active Directory sync sources."""
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if name_contains:
        params["name__icontains"] = name_contains
    return redact_secrets(await get_client(ctx).list("ldap_sync_source", **params))


@mcp.tool(annotations=read("Get LDAP sync source"))
async def get_ldap_source(ctx: Context, source: int | str) -> dict[str, Any]:
    """Retrieve an ldap_sync_source by id or exact name.

    Includes last sync status / errors when available — useful for
    answering 'is LDAP sync working?'.
    """
    client = get_client(ctx)
    source_id = await _resolve_source_id(client, source)
    return redact_secrets(await client.get("ldap_sync_source", source_id))


@mcp.tool(annotations=create("Create LDAP sync source"))
async def create_ldap_source(
    ctx: Context,
    name: str,
    ldap_server: str,
    ldap_base_dn: str,
    bind_username: str | None = None,
    bind_password: str | None = None,
    ldap_user_filter: str | None = None,
    ldap_user_search_dn: str | None = None,
    ldap_user_search_filter: str | None = None,
    ldap_permitted_users_regex: str | None = None,
    sync_interval_minutes: int | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Register a new LDAP / AD sync source.

    Args:
        name: Required, unique label.
        ldap_server: Required. Hostname of the LDAP server.
        ldap_base_dn: Required. Base DN to start searches from.
        bind_username: Service account DN for binding to LDAP.
        bind_password: Password for the bind account.
        ldap_user_filter: LDAP filter for users (e.g. "(objectClass=user)").
        ldap_user_search_dn: DN under base to search for users.
        ldap_user_search_filter: Additional user search filter.
        ldap_permitted_users_regex: Regex restricting which users are imported.
        sync_interval_minutes: How often to sync (defaults to platform default).
        description: Free-text.
    """
    client = get_client(ctx)
    payload: dict[str, Any] = {
        "name": name,
        "ldap_server": ldap_server,
        "ldap_base_dn": ldap_base_dn,
    }
    for f, v in (
        ("bind_username", bind_username),
        ("bind_password", bind_password),
        ("ldap_user_filter", ldap_user_filter),
        ("ldap_user_search_dn", ldap_user_search_dn),
        ("ldap_user_search_filter", ldap_user_search_filter),
        ("ldap_permitted_users_regex", ldap_permitted_users_regex),
        ("sync_interval_minutes", sync_interval_minutes),
        ("description", description),
    ):
        if v is not None:
            payload[f] = v
    location = await client.create("ldap_sync_source", payload)
    return await client.get("ldap_sync_source", extract_id_from_uri(location))


@mcp.tool(annotations=update("Update LDAP sync source"))
async def update_ldap_source(
    ctx: Context,
    source: int | str,
    name: str | None = None,
    ldap_server: str | None = None,
    ldap_base_dn: str | None = None,
    bind_username: str | None = None,
    bind_password: str | None = None,
    ldap_user_filter: str | None = None,
    ldap_user_search_dn: str | None = None,
    ldap_user_search_filter: str | None = None,
    ldap_permitted_users_regex: str | None = None,
    sync_interval_minutes: int | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Patch an ldap_sync_source. Only provided fields are changed."""
    payload: dict[str, Any] = {}
    for f, v in (
        ("name", name),
        ("ldap_server", ldap_server),
        ("ldap_base_dn", ldap_base_dn),
        ("bind_username", bind_username),
        ("bind_password", bind_password),
        ("ldap_user_filter", ldap_user_filter),
        ("ldap_user_search_dn", ldap_user_search_dn),
        ("ldap_user_search_filter", ldap_user_search_filter),
        ("ldap_permitted_users_regex", ldap_permitted_users_regex),
        ("sync_interval_minutes", sync_interval_minutes),
        ("description", description),
    ):
        if v is not None:
            payload[f] = v
    if not payload:
        raise PexipError(400, {"detail": "No fields provided to update"})

    client = get_client(ctx)
    source_id = await _resolve_source_id(client, source)
    await client.update("ldap_sync_source", source_id, payload)
    return await client.get("ldap_sync_source", source_id)


@mcp.tool(annotations=delete("Delete LDAP sync source"))
async def delete_ldap_source(ctx: Context, source: int | str) -> dict[str, Any]:
    """Delete an ldap_sync_source by id or exact name."""
    client = get_client(ctx)
    source_id = await _resolve_source_id(client, source)
    await client.delete("ldap_sync_source", source_id)
    return {"deleted": True, "id": source_id}
