"""Status API tools — live runtime state of the Pexip platform.

These tools are read-only and hit ``/api/admin/status/v1/...``. Status objects
are ephemeral: a participant disappears the moment they hang up, a conference
disappears when the last participant leaves, and alarms clear themselves as the
underlying condition resolves. Use this module to answer "what's happening
right now?". For "what happened earlier today?", see ``history.py``.

Typed tools for the hot paths: conferences, participants + media streams, registrations + aliases, nodes + per-node stats,
locations + per-location stats, backplanes + media stats, management node,
alarms, licensing, conference sync, cloud overflow nodes/locations, Exchange
scheduler, MJX endpoints + meetings, and Teams Connector nodes + calls.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context

from pexip_mcp.mcp_app import mcp
from pexip_mcp.tools._shaping import ListResult, ResponseFormat, shape_list
from pexip_mcp.tools._helpers import (
    fk_uri,
    get_client,
    paginate_all,
    read,
    resolve_id_by_field,
)
from pexip_mcp.tools.command import _resolve_active_participant_id


# Use _list to share the "list one page or all pages" branch across every status tool.
async def _list(client, resource, fetch_all: bool, **params: Any) -> dict[str, Any]:
    """List a status resource — paginate_all when fetch_all=True, otherwise one page."""
    if fetch_all:
        return await paginate_all(client, resource, api="status", **params)
    return await client.list(resource, api="status", **params)


@mcp.tool(annotations=read("List active conferences"))
async def list_active_conferences(
    ctx: Context,
    name: str | None = None,
    service_type: str | None = None,
    tag: str | None = None,
    limit: int = 20,
    offset: int = 0,
    fetch_all: bool = False,
    response_format: ResponseFormat = "concise",
    fields: list[str] | None = None,
) -> ListResult:
    """List currently-running conference instances.

    Empty `objects` list = nothing is in progress right now.

    Args:
        name: Filter by exact instance name (the dialed alias).
        service_type: "conference" / "lecture" / "two_stage_dialing" / "gateway" / "test_call".
        tag: Filter by service tag.
        limit: Per-page limit (ignored if fetch_all).
        offset: Pagination offset (ignored if fetch_all).
        fetch_all: Walk all pages and return up to 5,000 records combined.
        response_format: "concise" (default) returns the high-signal fields of each
            record; "detailed" returns every field Pexip stores.
        fields: Explicit list of field names to return (overrides response_format).
    """
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if name:
        params["name"] = name
    if service_type:
        params["service_type"] = service_type
    if tag:
        params["tag"] = tag
    return shape_list(
        await _list(get_client(ctx), "conference", fetch_all, **params),
        resource="status/conference",
        response_format=response_format,
        fields=fields,
    )


@mcp.tool(annotations=read("List active participants"))
async def list_active_participants(
    ctx: Context,
    conference_name: str | None = None,
    role: str | None = None,
    protocol: str | None = None,
    is_muted: bool | None = None,
    limit: int = 20,
    offset: int = 0,
    fetch_all: bool = False,
    response_format: ResponseFormat = "concise",
    fields: list[str] | None = None,
) -> ListResult:
    """List currently-connected participants (active call legs).

    Args:
        conference_name: Restrict to one running conference instance.
        role: "chair" or "guest".
        protocol: "api" / "sip" / "h323" / "mssip" / "webrtc" / "rtmp" / "teams" / "gms".
        is_muted: Filter by mute state.
        limit, offset, fetch_all: Pagination controls.
        response_format: "concise" (default) returns the high-signal fields of each
            record; "detailed" returns every field Pexip stores.
        fields: Explicit list of field names to return (overrides response_format).
    """
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if conference_name:
        params["conference"] = conference_name
    if role:
        params["role"] = role
    if protocol:
        params["protocol"] = protocol
    if is_muted is not None:
        params["is_muted"] = "True" if is_muted else "False"
    return shape_list(
        await _list(get_client(ctx), "participant", fetch_all, **params),
        resource="status/participant",
        response_format=response_format,
        fields=fields,
    )


@mcp.tool(annotations=read("Get active participant"))
async def get_active_participant(
    ctx: Context, participant: str, conference: str | None = None
) -> dict[str, Any]:
    """Retrieve a single active participant.

    Args:
        participant: UUID, or the participant's display name (e.g. "Bob") —
            names are resolved against currently connected participants
            automatically, so there is no need to call
            list_active_participants first.
        conference: Optional conference name to scope a display-name lookup
            when the name might not be unique across meetings.
    """
    pid = await _resolve_active_participant_id(ctx, participant, conference)
    return await get_client(ctx).get("participant", pid, api="status")


@mcp.tool(annotations=read("List active alarms"))
async def list_alarms(
    ctx: Context,
    level: str | None = None,
    node_name: str | None = None,
    limit: int = 20,
    offset: int = 0,
    fetch_all: bool = False,
    response_format: ResponseFormat = "concise",
    fields: list[str] | None = None,
) -> ListResult:
    """List active platform alarms.

    Args:
        level: "error" / "warning" / "info".
        node_name: Restrict to one Conferencing Node by name.
        limit, offset, fetch_all: Pagination controls.
        response_format: "concise" (default) returns the high-signal fields of each
            record; "detailed" returns every field Pexip stores.
        fields: Explicit list of field names to return (overrides response_format).
    """
    client = get_client(ctx)
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if level:
        params["level"] = level
    if node_name:
        node_id = await resolve_id_by_field(client, "worker_vm", node_name, field="name")
        params["node"] = fk_uri("worker_vm", node_id)
    return shape_list(
        await _list(client, "alarm", fetch_all, **params),
        resource="status/alarm",
        response_format=response_format,
        fields=fields,
    )


@mcp.tool(annotations=read("List node status"))
async def list_node_status(
    ctx: Context,
    location: str | int | None = None,
    name_contains: str | None = None,
    limit: int = 20,
    offset: int = 0,
    fetch_all: bool = False,
    response_format: ResponseFormat = "concise",
    fields: list[str] | None = None,
) -> ListResult:
    """Live status (load, sync, version, boot time) for each Conferencing Node.

    Args:
        location: Filter to one system_location by name or id.
        name_contains: Case-insensitive substring match on node name.
        limit, offset, fetch_all: Pagination controls.
        response_format: "concise" (default) returns the high-signal fields of each
            record; "detailed" returns every field Pexip stores.
        fields: Explicit list of field names to return (overrides response_format).
    """
    client = get_client(ctx)
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if location is not None:
        loc_id = await resolve_id_by_field(client, "system_location", location, field="name")
        params["system_location"] = fk_uri("system_location", loc_id)
    if name_contains:
        params["name__icontains"] = name_contains
    return shape_list(
        await _list(client, "worker_vm", fetch_all, **params),
        resource="status/worker_vm",
        response_format=response_format,
        fields=fields,
    )


@mcp.tool(annotations=read("Get node status"))
async def get_node_status(ctx: Context, node: str | int) -> dict[str, Any]:
    """Get live status for one Conferencing Node by integer id or exact name."""
    client = get_client(ctx)
    node_id = await resolve_id_by_field(client, "worker_vm", node, field="name")
    return await client.get("worker_vm", node_id, api="status")


@mcp.tool(annotations=read("Get licensing status"))
async def get_licensing_status(ctx: Context) -> dict[str, Any]:
    """Current concurrent port usage vs entitlement (audio + video ports, per location)."""
    return await get_client(ctx).list("licensing", api="status", limit=1000)


@mcp.tool(annotations=read("Get live participant quality"))
async def get_participant_quality(
    ctx: Context, participant: str, conference: str | None = None
) -> dict[str, Any]:
    """Live call quality for one active participant.

    Combines two Status API endpoints into one response:
    - the participant record (call_quality, connect_time, conference, role,
      protocol, remote_address, location, current packet loss summary)
    - all media streams for the participant (per-stream rx/tx bitrate,
      packet loss, jitter, codec, resolution).

    For "is Alice's call OK right now?" use cases — pass the name directly.
    For post-call quality forensics, use get_history_participant which
    exposes bucketed_call_quality.

    Args:
        participant: UUID, or the participant's display name (e.g. "Bob") —
            names are resolved against currently connected participants
            automatically, so there is no need to call
            list_active_participants first.
        conference: Optional conference name to scope a display-name lookup
            when the name might not be unique across meetings.
    """
    pid = await _resolve_active_participant_id(ctx, participant, conference)
    client = get_client(ctx)
    record = await client.get("participant", pid, api="status")
    streams = await client.list(
        "participant_media_stream",
        api="status",
        participant=f"/api/admin/status/v1/participant/{pid}/",
        limit=100,
    )
    return {"participant": record, "media_streams": streams.get("objects", [])}
