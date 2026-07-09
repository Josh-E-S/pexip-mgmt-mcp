"""IVR theme read-only tools.

An IVR theme is the audio + visual branding pack a VMR plays at the lobby
(waiting room) and IVR voice prompts: hold music, the "your conference is
locked" voice, splash images, color scheme. Themes are uploaded via the admin
UI (binary assets aren't a great fit for an API); this module exposes
list/get so the LLM can pick an existing one by name when calling create_vmr.
"""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context

from pexip_mcp.mcp_app import mcp
from pexip_mcp.tools._helpers import get_client, read, resolve_id_by_field


@mcp.tool(annotations=read("List IVR themes"))
async def list_ivr_themes(
    ctx: Context,
    name_contains: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """List IVR themes (branding bundles assignable to VMRs)."""
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if name_contains:
        params["name__icontains"] = name_contains
    return await get_client(ctx).list("ivr_theme", **params)


@mcp.tool(annotations=read("Get IVR theme"))
async def get_ivr_theme(ctx: Context, theme: int | str) -> dict[str, Any]:
    """Retrieve an IVR theme by id or exact name."""
    client = get_client(ctx)
    theme_id = await resolve_id_by_field(client, "ivr_theme", theme, field="name")
    return await client.get("ivr_theme", theme_id)
