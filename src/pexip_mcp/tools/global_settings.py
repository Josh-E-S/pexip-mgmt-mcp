"""Platform-wide global settings (singleton at /configuration/v1/global/1/).

The `global` resource is a singleton — there is exactly one instance with
id=1. Use get_resource_schema('global') to discover available fields before
making updates.
"""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context

from pexip_mcp.client import PexipError
from pexip_mcp.mcp_app import mcp
from pexip_mcp.tools._helpers import get_client, read, redact_secrets, update


@mcp.tool(annotations=read("Get global platform settings"))
async def get_global_settings(ctx: Context) -> dict[str, Any]:
    """Retrieve the platform-wide global configuration singleton.

    Includes things like default themes, default join PIN behavior,
    bandwidth caps, banner text, MSSIP domain, and call-create permissions.
    """
    return redact_secrets(await get_client(ctx).get("global", 1))


@mcp.tool(annotations=update("Update global platform settings"))
async def update_global_settings(
    ctx: Context, updates: dict[str, Any]
) -> dict[str, Any]:
    """Patch one or more fields on the platform-wide global settings.

    The `updates` dict is sent as the PATCH body — keys are field names from
    the global schema, values are the new values. Use
    get_resource_schema('global') first to discover field names, types, and
    enum values.

    Args:
        updates: Mapping of field name to new value. At least one entry required.

    Example:
        update_global_settings(updates={
            "management_session_timeout_secs": 1800,
            "guests_only_timeout": 300,
        })
    """
    if not updates:
        raise PexipError(400, {"updates": ["At least one field is required"]})
    client = get_client(ctx)
    await client.update("global", 1, updates)
    return await client.get("global", 1)
