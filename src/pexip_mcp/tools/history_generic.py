"""Generic History API tools over the history registry (shared logic in _generic.py).

Conference and participant history keep typed tools (plus summarize_calls).
Past alarms, backplanes, registration events and node events are reached
through these two tools by naming the resource. pexip_describe_resources(
api="history") lists the names and filters. The Management Node keeps the
last 10,000 records per resource; older entries are deleted.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context

from pexip_mcp.mcp_app import mcp
from pexip_mcp.tools._catalog import HISTORY_REGISTRY
from pexip_mcp.tools._generic import GenericApi
from pexip_mcp.tools._helpers import get_client, read
from pexip_mcp.tools._shaping import ListResult, ResponseFormat

API = GenericApi("history", HISTORY_REGISTRY, max_records=10000)


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

    Time bounds apply to the resource's time field (alarm: time_raised,
    workervm_status_event: time) and are refused for resources without one.

    Args:
        resource: History resource name, e.g. "alarm", "registration_alias",
            "workervm_status_event", "backplane".
        start_time: Lower bound (inclusive), UTC ISO 8601 e.g. "2026-10-01T00:00:00".
        end_time: Upper bound (exclusive), UTC ISO 8601.
        name_contains: Case-insensitive substring match on the resource's name
            (or alias) field; refused for resources that have none.
        filters: Extra query filters as key-value pairs (e.g. {"level": "critical"}).
        limit: Max results per page (default 20).
        offset: Pagination offset.
        fetch_all: Walk all pages (up to 10,000 records) instead of one page.
        response_format: "concise" (default) or "detailed".
        fields: Explicit field names to return (overrides response_format).
    """
    return await API.list(
        get_client(ctx),
        resource,
        name_contains=name_contains,
        start_time=start_time,
        end_time=end_time,
        filters=filters,
        limit=limit,
        offset=offset,
        fetch_all=fetch_all,
        response_format=response_format,
        fields=fields,
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
    return await API.get(get_client(ctx), resource, id)
