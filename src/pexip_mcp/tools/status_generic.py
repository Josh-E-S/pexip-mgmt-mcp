"""Generic Status API tools over the status registry.

The Status API has ~25 resources. A handful are hot paths and keep typed tools
(active conferences and participants, participant quality, alarms, licensing,
node status, registrations). Everything else is reached through these two
tools by naming the resource, exactly as the configuration API's generic CRUD
works. pexip_describe_resources(api="status") lists the names and filters.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context

from pexip_mcp.client import PexipError
from pexip_mcp.mcp_app import mcp
from pexip_mcp.tools._catalog import STATUS_REGISTRY, ResourceSpec
from pexip_mcp.tools._helpers import get_client, paginate_all, read
from pexip_mcp.tools._shaping import ListResult, ResponseFormat, shape_list
from pexip_mcp.tools.resource_crud import _validate_filters

# Resources addressed as a sub-path of one object (worker_vm/{id}/statistics):
# they are fetched with get_status(resource, id) and are not listable.
_SUBPATH = {name: spec for name, spec in STATUS_REGISTRY.items() if "{id}" in name}
_LISTABLE = {name: spec for name, spec in STATUS_REGISTRY.items() if "{id}" not in name}
_LISTABLE_NAMES = ", ".join(sorted(_LISTABLE))


def _spec(resource: str, *, listable: bool) -> ResourceSpec:
    table = _LISTABLE if listable else STATUS_REGISTRY
    spec = table.get(resource)
    if spec is None:
        raise PexipError(
            400,
            {
                "resource": [
                    f"Unknown status resource {resource!r}. Valid: {_LISTABLE_NAMES}"
                    + ("" if listable else ", " + ", ".join(sorted(_SUBPATH)))
                    + '. Use pexip_describe_resources(api="status") to search.'
                ]
            },
        )
    return spec


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
    """List any live Status API resource that has no dedicated tool (shards,
    backplanes, Management Node, conference sync, cloud overflow, Exchange
    scheduler, MJX, Teams Connector, registered aliases, location status).
    Status objects exist only while the call, node or integration is live.

    Args:
        resource: Status resource name, e.g. "teamsnode", "mjx_endpoint",
            "cloud_node", "conference_shard", "backplane", "system_location".
        name_contains: Case-insensitive substring match on the name field.
        filters: Extra query filters as key-value pairs; a key is a field name
            with at most one lookup suffix (e.g. {"conference": "All Hands"}).
        limit: Max results per page (default 20).
        offset: Pagination offset.
        fetch_all: Walk all pages (up to 5,000 records) instead of one page.
        response_format: "concise" (default) or "detailed".
        fields: Explicit field names to return (overrides response_format).
    """
    _spec(resource, listable=True)
    params: dict[str, Any] = {}
    if name_contains:
        params["name__icontains"] = name_contains
    if filters:
        params.update(_validate_filters(filters))
    client = get_client(ctx)
    if fetch_all:
        result = await paginate_all(client, resource, api="status", **params)
    else:
        result = await client.list(resource, api="status", limit=limit, offset=offset, **params)
    return shape_list(
        result, resource=f"status/{resource}", response_format=response_format, fields=fields
    )


@mcp.tool(annotations=read("Get status resource"))
async def get_status(ctx: Context, resource: str, id: str | int) -> dict[str, Any]:
    """Get one live Status API object by id, including per-object statistics.

    For sub-path resources pass the parent object's id: resource=
    "worker_vm/{id}/statistics" with the node id returns that node's load
    statistics; "system_location/{id}/statistics" a location's; "backplane/{id}/
    media_stream" a backplane's stream list.

    Args:
        resource: Status resource name (see pexip_list_status) or a sub-path
            resource containing "{id}".
        id: The object's id (UUID or integer as the resource uses).
    """
    _spec(resource, listable=False)
    client = get_client(ctx)
    if "{id}" in resource:
        path = resource.replace("{id}", str(id))
        return await client.list(path, api="status", limit=100)
    return await client.get(resource, id, api="status")
