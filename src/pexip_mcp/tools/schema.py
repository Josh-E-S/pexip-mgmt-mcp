"""Schema introspection tool.

Pexip's Management API self-describes — every resource exposes a JSON Schema at
/<api>/v1/<resource>/schema/ that lists its fields, types, required-ness, enums,
and help text. This tool exposes that to the LLM so it can discover what a
resource looks like before trying to CRUD it.
"""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context

from pexip_mcp.mcp_app import mcp
from pexip_mcp.tools._helpers import get_client, read


@mcp.tool(annotations=read("Get resource schema"))
async def get_resource_schema(ctx: Context, resource: str) -> dict[str, Any]:
    """Fetch the live JSON schema for a Pexip configuration resource.

    Use this to discover available fields, types, required vs optional
    (`nullable: false` = required), allowed enum values, filtering options,
    and help text for any resource. Pass the resource name as it appears in
    the URL path, e.g. "conference", "conference_alias", "end_user",
    "system_location", "worker_vm", "gateway_routing_rule",
    "automatic_participant".
    """
    return await get_client(ctx).schema(resource)
