"""Generic History API tools over the history registry.

Conference and participant history keep typed tools (plus summarize_calls).
Past alarms, backplanes, registration events and node events are reached
through these two tools by naming the resource. pexip_describe_resources(
api="history") lists the names and filters. The Management Node keeps the
last 10,000 records per resource; older entries are deleted.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context

from pexip_mcp.client import PexipError
from pexip_mcp.mcp_app import mcp
from pexip_mcp.tools._catalog import HISTORY_REGISTRY, ResourceSpec
from pexip_mcp.tools._helpers import get_client, paginate_all, read
from pexip_mcp.tools._shaping import ListResult, ResponseFormat, shape_list
from pexip_mcp.tools.resource_crud import _validate_filters

_SUBPATH = {name: spec for name, spec in HISTORY_REGISTRY.items() if "{id}" in name}
_LISTABLE = {name: spec for name, spec in HISTORY_REGISTRY.items() if "{id}" not in name}
_LISTABLE_NAMES = ", ".join(sorted(_LISTABLE))


def _spec(resource: str, *, listable: bool) -> ResourceSpec:
    table = _LISTABLE if listable else HISTORY_REGISTRY
    spec = table.get(resource)
    if spec is None:
        raise PexipError(
            400,
            {
                "resource": [
                    f"Unknown history resource {resource!r}. Valid: {_LISTABLE_NAMES}"
                    + ("" if listable else ", " + ", ".join(sorted(_SUBPATH)))
                    + '. Use pexip_describe_resources(api="history") to search.'
                ]
            },
        )
    return spec


@mcp.tool(annotations=read("List history resources"))
async def list_history(
    ctx: Context,
    resource: str,
    start_time: str | None = None,
    end_time: str | None = None,
    name_contains: str | None = None,
    filters: dict[str, Any] | None = None,
    limit: int = 20,
    offset: int = 0,
    fetch_all: bool = False,
    response_format: ResponseFormat = "concise",
    fields: list[str] | None = None,
) -> ListResult:
    """List a History API resource that has no dedicated tool: past alarms,
    backplanes, registration events, Conferencing Node events.

    Newest first. Time bounds apply to the record's start_time where the
    resource has one (alarm, workervm_status_event); they are ignored otherwise.

    Args:
        resource: History resource name, e.g. "alarm", "registration_alias",
            "workervm_status_event", "backplane".
        start_time: Lower bound (inclusive), UTC ISO 8601 e.g. "2026-10-01T00:00:00".
        end_time: Upper bound (exclusive), UTC ISO 8601.
        name_contains: Case-insensitive substring match on the name/alias field.
        filters: Extra query filters as key-value pairs (e.g. {"level": "critical"}).
        limit: Max results per page (default 20).
        offset: Pagination offset.
        fetch_all: Walk all pages (up to 10,000 records) instead of one page.
        response_format: "concise" (default) or "detailed".
        fields: Explicit list of field names to return (overrides response_format).
    """
    spec = _spec(resource, listable=True)
    params: dict[str, Any] = {}
    if "start_time" in spec.filters:
        params["order_by"] = "-start_time"
        if start_time:
            params["start_time__gte"] = start_time
        if end_time:
            params["start_time__lt"] = end_time
    if name_contains:
        field = "alias" if resource == "registration_alias" else "name"
        params[f"{field}__icontains"] = name_contains
    if filters:
        params.update(_validate_filters(filters))
    client = get_client(ctx)
    if fetch_all:
        result = await paginate_all(client, resource, api="history", max_records=10000, **params)
    else:
        result = await client.list(resource, api="history", limit=limit, offset=offset, **params)
    return shape_list(
        result, resource=f"history/{resource}", response_format=response_format, fields=fields
    )


@mcp.tool(annotations=read("Get history resource"))
async def get_history(ctx: Context, resource: str, id: str | int) -> dict[str, Any]:
    """Get one History API record by id, including per-object statistics.

    For sub-path resources pass the parent's id: resource="backplane/{id}/
    media_stream" returns a past backplane's stream statistics.

    Args:
        resource: History resource name (see pexip_list_history) or a sub-path
            resource containing "{id}".
        id: The record's id.
    """
    _spec(resource, listable=False)
    client = get_client(ctx)
    if "{id}" in resource:
        path = resource.replace("{id}", str(id))
        return await client.list(path, api="history", limit=100)
    return await client.get(resource, id, api="history")
