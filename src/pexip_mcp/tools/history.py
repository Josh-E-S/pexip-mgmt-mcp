"""History API tools — completed conferences, participant CDRs, alarms, backplanes,
registrations, and node events.

These tools hit ``/api/admin/history/v1/...``, the post-call sibling of the
Status API. Pexip records every call after it ends: who joined, for how long,
on what protocol, with what call quality, why they disconnected. Also covers
alarm history, backplane history + media stats, registration history, and
Conferencing Node status events.

The Management Node retains up to 10,000 conference instances; older entries
are deleted FIFO. For long-term retention, export externally on a schedule.
For live in-progress calls, use ``status.py`` instead.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context

from pexip_mcp.client import PexipError
from pexip_mcp.mcp_app import mcp
from pexip_mcp.tools._shaping import ListResult, ResponseFormat, shape_list
from pexip_mcp.tools._helpers import (
    fk_uri,
    get_client,
    paginate_all,
    read,
    resolve_id_by_field,
)


# Use _list to share the "list one page or paginate to the retention limit" branch.
async def _list(client, resource, fetch_all: bool, **params: Any) -> dict[str, Any]:
    """List a history resource — paginate_all up to 10,000 records when fetch_all=True."""
    if fetch_all:
        return await paginate_all(client, resource, api="history", max_records=10000, **params)
    return await client.list(resource, api="history", **params)


@mcp.tool(annotations=read("List historical conferences"))
async def list_history_conferences(
    ctx: Context,
    start_time: str | None = None,
    end_time: str | None = None,
    name: str | None = None,
    service_type: str | None = None,
    tag: str | None = None,
    limit: int = 20,
    offset: int = 0,
    fetch_all: bool = False,
    response_format: ResponseFormat = "concise",
    fields: list[str] | None = None,
) -> ListResult:
    """List completed conference instances.

    Args:
        start_time: Lower bound (inclusive) on conference start_time.
            ISO 8601 in UTC, e.g. "2026-05-07T00:00:00".
        end_time: Upper bound (exclusive) on conference start_time. UTC ISO 8601.
        name: Filter by exact instance name.
        service_type: "conference" / "lecture" / etc.
        tag: Filter by service tag.
        limit, offset, fetch_all: Pagination controls.
        response_format: "concise" (default) returns the high-signal fields of each
            record; "detailed" returns every field Pexip stores.
        fields: Explicit list of field names to return (overrides response_format).
    """
    params: dict[str, Any] = {"limit": limit, "offset": offset, "order_by": "-start_time"}
    if start_time:
        params["start_time__gte"] = start_time
    if end_time:
        params["start_time__lt"] = end_time
    if name:
        params["name"] = name
    if service_type:
        params["service_type"] = service_type
    if tag:
        params["tag"] = tag
    return shape_list(
        await _list(get_client(ctx), "conference", fetch_all, **params),
        resource="history/conference",
        response_format=response_format,
        fields=fields,
    )


@mcp.tool(annotations=read("Get historical conference"))
async def get_history_conference(ctx: Context, conference_id: str | int) -> dict[str, Any]:
    """Retrieve one past conference instance by id."""
    return await get_client(ctx).get("conference", conference_id, api="history")


@mcp.tool(annotations=read("List historical participants"))
async def list_history_participants(
    ctx: Context,
    start_time: str | None = None,
    end_time: str | None = None,
    conference_name: str | None = None,
    call_direction: str | None = None,
    call_quality: str | None = None,
    protocol: str | None = None,
    disconnect_reason: str | None = None,
    location: str | int | None = None,
    service_tag: str | None = None,
    limit: int = 20,
    offset: int = 0,
    fetch_all: bool = False,
    response_format: ResponseFormat = "concise",
    fields: list[str] | None = None,
) -> ListResult:
    """List completed participant call legs (CDR-like records).

    Time bounds apply to participant.start_time. All times are UTC ISO 8601.

    Args:
        start_time: Lower bound (inclusive) on start_time.
        end_time: Upper bound (exclusive) on start_time.
        conference_name: Restrict to one conference name (string, not id).
        call_direction: "in" / "out".
        call_quality: "1_good" / "2_ok" / "3_bad" / "4_terrible".
        protocol: "sip" / "h323" / "mssip" / "webrtc" / "rtmp" / "teams" / etc.
        disconnect_reason: e.g. "Call disconnected", "Call failed", "Call rejected".
        location: system_location id or exact name.
        service_tag: Filter by tag carried from the parent conference.
        limit, offset, fetch_all: Pagination. fetch_all caps at 10,000.
        response_format: "concise" (default) returns the high-signal fields of each
            record; "detailed" returns every field Pexip stores.
        fields: Explicit list of field names to return (overrides response_format).
    """
    client = get_client(ctx)
    params: dict[str, Any] = {"limit": limit, "offset": offset, "order_by": "-start_time"}
    if start_time:
        params["start_time__gte"] = start_time
    if end_time:
        params["start_time__lt"] = end_time
    if conference_name:
        params["conference"] = conference_name
    if call_direction:
        params["call_direction"] = call_direction
    if call_quality:
        params["call_quality"] = call_quality
    if protocol:
        params["protocol"] = protocol
    if disconnect_reason:
        params["disconnect_reason"] = disconnect_reason
    if location is not None:
        loc_id = await resolve_id_by_field(client, "system_location", location, field="name")
        params["system_location"] = fk_uri("system_location", loc_id)
    if service_tag:
        params["service_tag"] = service_tag
    return shape_list(
        await _list(client, "participant", fetch_all, **params),
        resource="history/participant",
        response_format=response_format,
        fields=fields,
    )


@mcp.tool(annotations=read("Get historical participant"))
async def get_history_participant(ctx: Context, participant_id: str | int) -> dict[str, Any]:
    """Retrieve one past participant by id.

    Returns full quality forensics: `historic_call_quality` (per-window timeline)
    and `bucketed_call_quality` ([unknown, good, ok, bad, terrible] counts).
    These deep fields are only populated on individual GET, not list responses.
    """
    return await get_client(ctx).get("participant", participant_id, api="history")


_GROUP_BY_FIELDS = {
    "call_direction",
    "call_quality",
    "protocol",
    "service_tag",
    "system_location",
    "conference_name",
    "disconnect_reason",
    "vendor",
}


@mcp.tool(annotations=read("Summarize calls in a time window"))
async def summarize_calls(
    ctx: Context,
    start_time: str,
    end_time: str,
    group_by: str = "call_direction",
    conference_name: str | None = None,
    service_tag: str | None = None,
    call_direction: str | None = None,
    location: str | int | None = None,
    max_records: int = 10000,
) -> dict[str, Any]:
    """Summarize / report on call history — grouped counts and totals over a window.

    Returns aggregated counts and durations grouped by one field, not individual
    records; it walks pagination internally, so it is far cheaper than listing.

    Args:
        start_time: Lower bound (inclusive) on start_time. UTC ISO 8601 required.
        end_time: Upper bound (exclusive) on start_time. UTC ISO 8601 required.
        group_by: One of "call_direction", "call_quality", "protocol",
            "service_tag", "system_location", "conference_name",
            "disconnect_reason", "vendor".
        conference_name: Restrict to one conference name.
        service_tag: Restrict to one tag.
        call_direction: "in" or "out" — useful when group_by is something else.
        location: system_location filter (name or id).
        max_records: Hard cap on participants fetched. Defaults to 10,000
            (the platform retention limit).

    Returns total_calls, total_duration_seconds, average_duration_seconds,
    time_range, group_by, groups ({key: {count, duration_seconds}}) and
    truncated (true if max_records was hit before the window was exhausted).
    """
    if group_by not in _GROUP_BY_FIELDS:
        raise PexipError(
            400,
            {"group_by": [f"Must be one of {sorted(_GROUP_BY_FIELDS)}, got {group_by!r}"]},
        )

    client = get_client(ctx)
    params: dict[str, Any] = {"start_time__gte": start_time, "start_time__lt": end_time}
    if conference_name:
        params["conference"] = conference_name
    if service_tag:
        params["service_tag"] = service_tag
    if call_direction:
        params["call_direction"] = call_direction
    if location is not None:
        loc_id = await resolve_id_by_field(client, "system_location", location, field="name")
        params["system_location"] = fk_uri("system_location", loc_id)

    page = await paginate_all(
        client, "participant", api="history", max_records=max_records, **params
    )

    objects = page["objects"]
    groups: dict[str, dict[str, int]] = {}
    total_duration = 0
    for obj in objects:
        key = obj.get(group_by)
        bucket_key = str(key) if key not in (None, "") else "unknown"
        bucket = groups.setdefault(bucket_key, {"count": 0, "duration_seconds": 0})
        bucket["count"] += 1
        d = obj.get("duration") or 0
        bucket["duration_seconds"] += d
        total_duration += d

    sorted_groups = dict(sorted(groups.items(), key=lambda kv: kv[1]["count"], reverse=True))
    n = len(objects)
    return {
        "total_calls": n,
        "total_duration_seconds": total_duration,
        "average_duration_seconds": (total_duration / n) if n else 0,
        "time_range": {"start": start_time, "end": end_time},
        "group_by": group_by,
        "groups": sorted_groups,
        "truncated": page["truncated"],
        "server_total_count": page["meta"].get("total_count"),
    }
