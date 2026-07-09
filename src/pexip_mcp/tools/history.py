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
) -> dict[str, Any]:
    """List completed conference instances.

    Args:
        start_time: Lower bound (inclusive) on conference start_time.
            ISO 8601 in UTC, e.g. "2026-05-07T00:00:00".
        end_time: Upper bound (exclusive) on conference start_time. UTC ISO 8601.
        name: Filter by exact instance name.
        service_type: "conference" / "lecture" / etc.
        tag: Filter by service tag.
        limit, offset, fetch_all: Pagination controls.
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
    return await _list(get_client(ctx), "conference", fetch_all, **params)


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
) -> dict[str, Any]:
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
    return await _list(client, "participant", fetch_all, **params)


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

    USE THIS for any "summarize", "report", "breakdown", "how many calls by X",
    "stats", or "totals" request. Returns aggregated counts + durations grouped
    by a field — NOT individual records. Prefer this over
    list_history_conferences / list_history_participants whenever the user wants
    aggregates rather than a raw list; it walks pagination internally and is far
    cheaper on context and tool calls than fetching individual records.

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

    Returns:
        {
          "total_calls": int,
          "total_duration_seconds": int,
          "average_duration_seconds": float,
          "time_range": {"start": ..., "end": ...},
          "group_by": str,
          "groups": {<key>: {"count": int, "duration_seconds": int}, ...},
          "truncated": bool   # true if max_records was hit before exhausting results
        }
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


# ── alarm history ────────────────────────────────────────────────────────────


@mcp.tool(annotations=read("List alarm history"))
async def list_alarm_history(
    ctx: Context,
    start_time: str | None = None,
    end_time: str | None = None,
    level: str | None = None,
    limit: int = 20,
    offset: int = 0,
    fetch_all: bool = False,
) -> dict[str, Any]:
    """List historical alarms.

    Args:
        start_time: Lower bound (inclusive) on time_raised. UTC ISO 8601.
        end_time: Upper bound (exclusive) on time_raised. UTC ISO 8601.
        level: "error" / "warning" / "info".
        limit, offset, fetch_all: Pagination controls.
    """
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if start_time:
        params["time_raised__gte"] = start_time
    if end_time:
        params["time_raised__lt"] = end_time
    if level:
        params["level"] = level
    return await _list(get_client(ctx), "alarm", fetch_all, **params)


@mcp.tool(annotations=read("Get historical alarm"))
async def get_alarm_history(ctx: Context, alarm_id: str | int) -> dict[str, Any]:
    """Retrieve one historical alarm by id."""
    return await get_client(ctx).get("alarm", alarm_id, api="history")


# ── backplane history + media stats ──────────────────────────────────────────


@mcp.tool(annotations=read("List backplane history"))
async def list_backplane_history(
    ctx: Context, limit: int = 20, offset: int = 0, fetch_all: bool = False
) -> dict[str, Any]:
    """List historical backplane connections."""
    return await _list(get_client(ctx), "backplane", fetch_all, limit=limit, offset=offset)


@mcp.tool(annotations=read("Get backplane history"))
async def get_backplane_history(ctx: Context, backplane_id: str | int) -> dict[str, Any]:
    """Retrieve one historical backplane connection by id."""
    return await get_client(ctx).get("backplane", backplane_id, api="history")


@mcp.tool(annotations=read("Get backplane history media streams"))
async def get_backplane_history_media_streams(
    ctx: Context, backplane_id: str | int
) -> dict[str, Any]:
    """Get media stream statistics for a historical backplane connection.

    Args:
        backplane_id: Backplane id from list_backplane_history.
    """
    return await get_client(ctx).list(
        f"backplane/{backplane_id}/media_stream", api="history", limit=100
    )


# ── registration_alias history ───────────────────────────────────────────────


@mcp.tool(annotations=read("List registration history"))
async def list_registration_history(
    ctx: Context,
    alias_contains: str | None = None,
    limit: int = 20,
    offset: int = 0,
    fetch_all: bool = False,
) -> dict[str, Any]:
    """List historical registration events.

    Args:
        alias_contains: Case-insensitive substring match on the alias.
        limit, offset, fetch_all: Pagination controls.
    """
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if alias_contains:
        params["alias__icontains"] = alias_contains
    return await _list(get_client(ctx), "registration_alias", fetch_all, **params)


@mcp.tool(annotations=read("Get registration history"))
async def get_registration_history(ctx: Context, entry_id: str | int) -> dict[str, Any]:
    """Retrieve one historical registration entry by id."""
    return await get_client(ctx).get("registration_alias", entry_id, api="history")


# ── workervm_status_event (Conferencing Node events) ─────────────────────────


@mcp.tool(annotations=read("List node event history"))
async def list_node_event_history(
    ctx: Context,
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int = 20,
    offset: int = 0,
    fetch_all: bool = False,
) -> dict[str, Any]:
    """List Conferencing Node status event history.

    Args:
        start_time: Lower bound (inclusive). UTC ISO 8601.
        end_time: Upper bound (exclusive). UTC ISO 8601.
        limit, offset, fetch_all: Pagination controls.
    """
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if start_time:
        params["time__gte"] = start_time
    if end_time:
        params["time__lt"] = end_time
    return await _list(get_client(ctx), "workervm_status_event", fetch_all, **params)


@mcp.tool(annotations=read("Get node event history"))
async def get_node_event_history(ctx: Context, event_id: str | int) -> dict[str, Any]:
    """Retrieve one Conferencing Node status event by id."""
    return await get_client(ctx).get("workervm_status_event", event_id, api="history")
