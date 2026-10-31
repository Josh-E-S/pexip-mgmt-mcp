"""Generic Status API tools over the status registry (shared logic in _generic.py).

The Status API has ~25 resources. A handful are hot paths and keep typed tools
(active conferences and participants, participant quality, alarms, licensing,
node status, registrations). Everything else is reached through these two
tools by naming the resource, exactly as the configuration API's generic CRUD
works. pexip_describe_resources(api="status") lists the names and filters.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context

from pexip_mcp.mcp_app import mcp
from pexip_mcp.tools._catalog import STATUS_REGISTRY
from pexip_mcp.tools._generic import GenericApi
from pexip_mcp.tools._helpers import get_client, read
from pexip_mcp.tools._shaping import ListResult, ResponseFormat

API = GenericApi("status", STATUS_REGISTRY, max_records=5000)


@mcp.tool(annotations=read("List status resources"))
async def list_status(
    ctx: Context,
    resource: str,
    name_contains: str | None = None,
    filters: dict[str, Any] | None = None,
    limit: int = 20,
    offset: int = 0,
    fetch_all: bool = False,
    response_format: ResponseFormat = "concise",
    fields: list[str] | None = None,
) -> ListResult:
    """List any live Status API resource that has no dedicated tool. Status
    objects exist only while the call, node or integration is live.

    Args:
        resource: Status resource name, e.g. "teamsnode", "mjx_endpoint",
            "cloud_node", "conference_shard", "backplane", "system_location".
        name_contains: Case-insensitive substring match on the resource's name
            (or alias) field; refused for resources that have none.
        filters: Extra query filters as key-value pairs; a key is a field name
            with at most one lookup suffix (e.g. {"conference": "All Hands"}).
        limit: Max results per page (default 20).
        offset: Pagination offset.
        fetch_all: Walk all pages (up to 5,000 records) instead of one page.
        response_format: "concise" (default) or "detailed".
        fields: Explicit field names to return (overrides response_format).
    """
    return await API.list(
        get_client(ctx),
        resource,
        name_contains=name_contains,
        filters=filters,
        limit=limit,
        offset=offset,
        fetch_all=fetch_all,
        response_format=response_format,
        fields=fields,
    )


@mcp.tool(annotations=read("Get status resource"))
async def get_status(ctx: Context, resource: str, id: str | int) -> dict[str, Any]:
    """Get one live Status API object by id, including per-object statistics.

    For sub-path resources pass the parent object's id or configured name:
    resource="worker_vm/{id}/statistics" with id="conf-node-1" returns that
    node's load statistics; "system_location/{id}/statistics" a location's;
    "backplane/{id}/media_stream" a backplane's stream list.

    Args:
        resource: Status resource name (see pexip_list_status) or a sub-path
            resource containing "{id}".
        id: The object's id (UUID or integer), or the configured name for
            worker_vm / system_location based resources.
    """
    return await API.get(get_client(ctx), resource, id)
