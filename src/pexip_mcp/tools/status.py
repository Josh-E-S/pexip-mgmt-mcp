"""Status API tools — live runtime state of the Pexip platform.

These tools are read-only and hit ``/api/admin/status/v1/...``. Status objects
are ephemeral: a participant disappears the moment they hang up, a conference
disappears when the last participant leaves, and alarms clear themselves as the
underlying condition resolves. Use this module to answer "what's happening
right now?". For "what happened earlier today?", see ``history.py``.

Covers every Status API resource: conferences (including per-node shards),
participants + media streams, registrations + aliases, nodes + per-node stats,
locations + per-location stats, backplanes + media stats, management node,
alarms, licensing, conference sync, cloud overflow nodes/locations, Exchange
scheduler, MJX endpoints + meetings, and Teams Connector nodes + calls.
"""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context

from pexip_mcp.mcp_app import mcp
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
) -> dict[str, Any]:
    """List currently-running conference instances.

    Empty `objects` list = nothing is in progress right now.

    Args:
        name: Filter by exact instance name (the dialed alias).
        service_type: "conference" / "lecture" / "two_stage_dialing" / "gateway" / "test_call".
        tag: Filter by service tag.
        limit: Per-page limit (ignored if fetch_all).
        offset: Pagination offset (ignored if fetch_all).
        fetch_all: Walk all pages and return up to 5,000 records combined.
    """
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if name:
        params["name"] = name
    if service_type:
        params["service_type"] = service_type
    if tag:
        params["tag"] = tag
    return await _list(get_client(ctx), "conference", fetch_all, **params)


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
) -> dict[str, Any]:
    """List currently-connected participants (active call legs).

    Args:
        conference_name: Restrict to one running conference instance.
        role: "chair" or "guest".
        protocol: "api" / "sip" / "h323" / "mssip" / "webrtc" / "rtmp" / "teams" / "gms".
        is_muted: Filter by mute state.
        limit, offset, fetch_all: Pagination controls.
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
    return await _list(get_client(ctx), "participant", fetch_all, **params)


@mcp.tool(annotations=read("Get active participant"))
async def get_active_participant(
    ctx: Context, participant_id: str, conference: str | None = None
) -> dict[str, Any]:
    """Retrieve a single active participant.

    Args:
        participant_id: UUID, or the participant's display name (e.g. "Bob") —
            names are resolved against currently connected participants
            automatically, so there is no need to call
            list_active_participants first.
        conference: Optional conference name to scope a display-name lookup
            when the name might not be unique across meetings.
    """
    pid = await _resolve_active_participant_id(ctx, participant_id, conference)
    return await get_client(ctx).get("participant", pid, api="status")


@mcp.tool(annotations=read("List active alarms"))
async def list_alarms(
    ctx: Context,
    level: str | None = None,
    node_name: str | None = None,
    limit: int = 20,
    offset: int = 0,
    fetch_all: bool = False,
) -> dict[str, Any]:
    """List active platform alarms.

    Args:
        level: "error" / "warning" / "info".
        node_name: Restrict to one Conferencing Node by name.
        limit, offset, fetch_all: Pagination controls.
    """
    client = get_client(ctx)
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if level:
        params["level"] = level
    if node_name:
        node_id = await resolve_id_by_field(client, "worker_vm", node_name, field="name")
        params["node"] = fk_uri("worker_vm", node_id)
    return await _list(client, "alarm", fetch_all, **params)


@mcp.tool(annotations=read("List node status"))
async def list_node_status(
    ctx: Context,
    location: str | int | None = None,
    name_contains: str | None = None,
    limit: int = 20,
    offset: int = 0,
    fetch_all: bool = False,
) -> dict[str, Any]:
    """Live status (load, sync, version, boot time) for each Conferencing Node.

    Args:
        location: Filter to one system_location by name or id.
        name_contains: Case-insensitive substring match on node name.
        limit, offset, fetch_all: Pagination controls.
    """
    client = get_client(ctx)
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if location is not None:
        loc_id = await resolve_id_by_field(client, "system_location", location, field="name")
        params["system_location"] = fk_uri("system_location", loc_id)
    if name_contains:
        params["name__icontains"] = name_contains
    return await _list(client, "worker_vm", fetch_all, **params)


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
    ctx: Context, participant_id: str, conference: str | None = None
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
        participant_id: UUID, or the participant's display name (e.g. "Bob") —
            names are resolved against currently connected participants
            automatically, so there is no need to call
            list_active_participants first.
        conference: Optional conference name to scope a display-name lookup
            when the name might not be unique across meetings.
    """
    pid = await _resolve_active_participant_id(ctx, participant_id, conference)
    client = get_client(ctx)
    participant = await client.get("participant", pid, api="status")
    streams = await client.list(
        "participant_media_stream",
        api="status",
        participant=f"/api/admin/status/v1/participant/{pid}/",
        limit=100,
    )
    return {"participant": participant, "media_streams": streams.get("objects", [])}


# ── conference_shard (per-node conference instances) ─────────────────────────


@mcp.tool(annotations=read("List conference shards"))
async def list_conference_shards(
    ctx: Context,
    conference_name: str | None = None,
    limit: int = 20,
    offset: int = 0,
    fetch_all: bool = False,
) -> dict[str, Any]:
    """List conference instances broken out per Conferencing Node (shards).

    Args:
        conference_name: Filter by conference name.
        limit, offset, fetch_all: Pagination controls.
    """
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if conference_name:
        params["conference_name"] = conference_name
    return await _list(get_client(ctx), "conference_shard", fetch_all, **params)


@mcp.tool(annotations=read("Get conference shard"))
async def get_conference_shard(ctx: Context, shard_id: str) -> dict[str, Any]:
    """Retrieve a single conference shard by id."""
    return await get_client(ctx).get("conference_shard", shard_id, api="status")


# ── registration_alias (registered aliases) ──────────────────────────────────


@mcp.tool(annotations=read("List registered aliases"))
async def list_registration_aliases(
    ctx: Context,
    alias_contains: str | None = None,
    limit: int = 20,
    offset: int = 0,
    fetch_all: bool = False,
) -> dict[str, Any]:
    """List currently registered aliases on the platform.

    Args:
        alias_contains: Case-insensitive substring match on the alias.
        limit, offset, fetch_all: Pagination controls.
    """
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if alias_contains:
        params["alias__icontains"] = alias_contains
    return await _list(get_client(ctx), "registration_alias", fetch_all, **params)


@mcp.tool(annotations=read("Get registered alias"))
async def get_registration_alias(ctx: Context, alias_id: str) -> dict[str, Any]:
    """Retrieve a single registered alias by id."""
    return await get_client(ctx).get("registration_alias", alias_id, api="status")


# ── system_location status + statistics ──────────────────────────────────────


@mcp.tool(annotations=read("List location status"))
async def list_location_status(
    ctx: Context,
    name_contains: str | None = None,
    limit: int = 20,
    offset: int = 0,
    fetch_all: bool = False,
) -> dict[str, Any]:
    """List live status for system locations.

    Args:
        name_contains: Case-insensitive substring match on location name.
        limit, offset, fetch_all: Pagination controls.
    """
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if name_contains:
        params["name__icontains"] = name_contains
    return await _list(get_client(ctx), "system_location", fetch_all, **params)


@mcp.tool(annotations=read("Get location status"))
async def get_location_status(ctx: Context, location: str | int) -> dict[str, Any]:
    """Get live status for one system location by id or exact name."""
    client = get_client(ctx)
    loc_id = await resolve_id_by_field(client, "system_location", location, field="name")
    return await client.get("system_location", loc_id, api="status")


@mcp.tool(annotations=read("Get location load statistics"))
async def get_location_statistics(ctx: Context, location: str | int) -> dict[str, Any]:
    """Get load statistics for one system location (call counts, port usage).

    Args:
        location: Location id or exact name.
    """
    client = get_client(ctx)
    loc_id = await resolve_id_by_field(client, "system_location", location, field="name")
    return await client.list(
        f"system_location/{loc_id}/statistics", api="status", limit=100
    )


# ── worker_vm statistics (per-node load) ─────────────────────────────────────


@mcp.tool(annotations=read("Get node load statistics"))
async def get_node_statistics(ctx: Context, node: str | int) -> dict[str, Any]:
    """Get load statistics for one Conferencing Node (CPU, media load, call counts).

    Args:
        node: Node id or exact name.
    """
    client = get_client(ctx)
    node_id = await resolve_id_by_field(client, "worker_vm", node, field="name")
    return await client.list(
        f"worker_vm/{node_id}/statistics", api="status", limit=100
    )


# ── backplane + media stats ──────────────────────────────────────────────────


@mcp.tool(annotations=read("List backplanes"))
async def list_backplanes(
    ctx: Context, limit: int = 20, offset: int = 0, fetch_all: bool = False
) -> dict[str, Any]:
    """List backplane status (inter-node media connections)."""
    return await _list(get_client(ctx), "backplane", fetch_all, limit=limit, offset=offset)


@mcp.tool(annotations=read("Get backplane"))
async def get_backplane(ctx: Context, backplane_id: str) -> dict[str, Any]:
    """Retrieve a single backplane by id."""
    return await get_client(ctx).get("backplane", backplane_id, api="status")


@mcp.tool(annotations=read("Get backplane media streams"))
async def get_backplane_media_streams(ctx: Context, backplane_id: str) -> dict[str, Any]:
    """Get media stream statistics for a backplane connection.

    Args:
        backplane_id: Backplane id from list_backplanes.
    """
    return await get_client(ctx).list(
        f"backplane/{backplane_id}/media_stream", api="status", limit=100
    )


# ── management_vm status ─────────────────────────────────────────────────────


@mcp.tool(annotations=read("List management node status"))
async def list_management_node_status(
    ctx: Context, limit: int = 20, offset: int = 0
) -> dict[str, Any]:
    """List Management Node live status."""
    return await get_client(ctx).list("management_vm", api="status", limit=limit, offset=offset)


@mcp.tool(annotations=read("Get management node status"))
async def get_management_node_status(ctx: Context, node_id: int) -> dict[str, Any]:
    """Retrieve live status for a specific Management Node."""
    return await get_client(ctx).get("management_vm", node_id, api="status")


# ── conference_sync ──────────────────────────────────────────────────────────


@mcp.tool(annotations=read("List conference sync status"))
async def list_conference_sync_status(
    ctx: Context, limit: int = 20, offset: int = 0, fetch_all: bool = False
) -> dict[str, Any]:
    """List conference synchronization status."""
    return await _list(get_client(ctx), "conference_sync", fetch_all, limit=limit, offset=offset)


@mcp.tool(annotations=read("Get conference sync status"))
async def get_conference_sync_status(ctx: Context, sync_id: str) -> dict[str, Any]:
    """Retrieve a single conference sync entry by id."""
    return await get_client(ctx).get("conference_sync", sync_id, api="status")


# ── cloud overflow / dynamic bursting ────────────────────────────────────────


@mcp.tool(annotations=read("List cloud overflow nodes"))
async def list_cloud_nodes(
    ctx: Context, limit: int = 20, offset: int = 0, fetch_all: bool = False
) -> dict[str, Any]:
    """List all cloud overflow Conferencing Nodes (dynamic bursting)."""
    return await _list(get_client(ctx), "cloud_node", fetch_all, limit=limit, offset=offset)


@mcp.tool(annotations=read("Get cloud overflow node"))
async def get_cloud_node(ctx: Context, node_id: str) -> dict[str, Any]:
    """Retrieve a single cloud overflow node by id."""
    return await get_client(ctx).get("cloud_node", node_id, api="status")


@mcp.tool(annotations=read("List cloud monitored locations"))
async def list_cloud_monitored_locations(
    ctx: Context, limit: int = 20, offset: int = 0, fetch_all: bool = False
) -> dict[str, Any]:
    """List all locations monitored for dynamic bursting."""
    return await _list(
        get_client(ctx), "cloud_monitored_location", fetch_all, limit=limit, offset=offset
    )


@mcp.tool(annotations=read("Get cloud monitored location"))
async def get_cloud_monitored_location(ctx: Context, location_id: str) -> dict[str, Any]:
    """Retrieve a single cloud monitored location by id."""
    return await get_client(ctx).get("cloud_monitored_location", location_id, api="status")


@mcp.tool(annotations=read("List cloud overflow locations"))
async def list_cloud_overflow_locations(
    ctx: Context, limit: int = 20, offset: int = 0, fetch_all: bool = False
) -> dict[str, Any]:
    """List all locations containing Conferencing Nodes for dynamic bursting."""
    return await _list(
        get_client(ctx), "cloud_overflow_location", fetch_all, limit=limit, offset=offset
    )


@mcp.tool(annotations=read("Get cloud overflow location"))
async def get_cloud_overflow_location(ctx: Context, location_id: str) -> dict[str, Any]:
    """Retrieve a single cloud overflow location by id."""
    return await get_client(ctx).get("cloud_overflow_location", location_id, api="status")


# ── exchange_scheduler ───────────────────────────────────────────────────────


@mcp.tool(annotations=read("List Exchange scheduler status"))
async def list_exchange_scheduler_status(
    ctx: Context, limit: int = 20, offset: int = 0, fetch_all: bool = False
) -> dict[str, Any]:
    """List Secure Scheduler for Exchange integration status."""
    return await _list(
        get_client(ctx), "exchange_scheduler", fetch_all, limit=limit, offset=offset
    )


@mcp.tool(annotations=read("Get Exchange scheduler status"))
async def get_exchange_scheduler_status(ctx: Context, scheduler_id: str) -> dict[str, Any]:
    """Retrieve a single Exchange scheduler entry by id."""
    return await get_client(ctx).get("exchange_scheduler", scheduler_id, api="status")


# ── MJX status (endpoints + meetings) ────────────────────────────────────────


@mcp.tool(annotations=read("List MJX endpoint status"))
async def list_mjx_endpoint_status(
    ctx: Context,
    name_contains: str | None = None,
    limit: int = 20,
    offset: int = 0,
    fetch_all: bool = False,
) -> dict[str, Any]:
    """List One-Touch Join endpoint live status.

    Args:
        name_contains: Case-insensitive substring match on endpoint name.
        limit, offset, fetch_all: Pagination controls.
    """
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if name_contains:
        params["name__icontains"] = name_contains
    return await _list(get_client(ctx), "mjx_endpoint", fetch_all, **params)


@mcp.tool(annotations=read("Get MJX endpoint status"))
async def get_mjx_endpoint_status(ctx: Context, endpoint_id: str) -> dict[str, Any]:
    """Retrieve live status for a single MJX endpoint by id."""
    return await get_client(ctx).get("mjx_endpoint", endpoint_id, api="status")


@mcp.tool(annotations=read("List MJX meeting status"))
async def list_mjx_meeting_status(
    ctx: Context, limit: int = 20, offset: int = 0, fetch_all: bool = False
) -> dict[str, Any]:
    """List One-Touch Join meeting status (upcoming meetings detected by MJX)."""
    return await _list(get_client(ctx), "mjx_meeting", fetch_all, limit=limit, offset=offset)


@mcp.tool(annotations=read("Get MJX meeting status"))
async def get_mjx_meeting_status(ctx: Context, meeting_id: str) -> dict[str, Any]:
    """Retrieve status for a single MJX meeting by id."""
    return await get_client(ctx).get("mjx_meeting", meeting_id, api="status")


# ── Teams Connector status ───────────────────────────────────────────────────


@mcp.tool(annotations=read("List Teams Connector node status"))
async def list_teams_node_status(
    ctx: Context, limit: int = 20, offset: int = 0, fetch_all: bool = False
) -> dict[str, Any]:
    """List Teams Connector node status."""
    return await _list(get_client(ctx), "teamsnode", fetch_all, limit=limit, offset=offset)


@mcp.tool(annotations=read("Get Teams Connector node status"))
async def get_teams_node_status(ctx: Context, node_id: str) -> dict[str, Any]:
    """Retrieve status for a single Teams Connector node by id."""
    return await get_client(ctx).get("teamsnode", node_id, api="status")


@mcp.tool(annotations=read("List Teams Connector call status"))
async def list_teams_node_call_status(
    ctx: Context, limit: int = 20, offset: int = 0, fetch_all: bool = False
) -> dict[str, Any]:
    """List Teams Connector call status."""
    return await _list(get_client(ctx), "teamsnode_call", fetch_all, limit=limit, offset=offset)


@mcp.tool(annotations=read("Get Teams Connector call status"))
async def get_teams_node_call_status(ctx: Context, call_id: str) -> dict[str, Any]:
    """Retrieve status for a single Teams Connector call by id."""
    return await get_client(ctx).get("teamsnode_call", call_id, api="status")
