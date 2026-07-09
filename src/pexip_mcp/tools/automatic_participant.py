"""Automatic participant tools — per-VMR auto-dial entries.

An "automatic participant" is a participant Pexip should dial OUT to whenever a
given VMR starts. Typical uses: a recorder, a streaming endpoint, a phone
bridge, or a meeting-room SIP endpoint that should always be pulled in. It's
configured once on the VMR; Pexip handles the dialing every time the meeting
runs. Compare with the Command API's `dial_participant`, which adds a
participant to a single live call on demand.
"""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context

from pexip_mcp.client import extract_id_from_uri
from pexip_mcp.mcp_app import mcp
from pexip_mcp.tools._helpers import create, delete, fk_uri, get_client, read, resolve_id_by_field


@mcp.tool(annotations=read("List automatic participants"))
async def list_automatic_participants(
    ctx: Context,
    vmr: int | str | None = None,
    alias_contains: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """List automatic participants, optionally scoped to one VMR.

    Args:
        vmr: VMR id or name to filter by (pass the name directly — resolved
            internally, no need to list_vmrs first). Omit for all.
        alias_contains: Case-insensitive substring match on alias.
        limit: Max results.
        offset: Pagination offset.
    """
    client = get_client(ctx)
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if vmr is not None:
        vmr_id = await resolve_id_by_field(
            client, "conference", vmr, field="name", service_type="conference"
        )
        params["conference"] = fk_uri("conference", vmr_id)
    if alias_contains:
        params["alias__icontains"] = alias_contains
    return await client.list("automatic_participant", **params)


@mcp.tool(annotations=create("Add automatic participant"))
async def add_automatic_participant(
    ctx: Context,
    vmr: int | str,
    alias: str,
    protocol: str | None = None,
    call_type: str | None = None,
    role: str | None = None,
    system_location: int | str | None = None,
    dtmf_sequence: str | None = None,
    streaming: bool | None = None,
    keep_conference_alive: str | None = None,
    routing: str | None = None,
    remote_display_name: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Attach an automatic participant (recorder, streamer, dial-out endpoint) to a VMR.

    The participant is dialed when the conference starts.

    Args:
        vmr: VMR id or name (pass the name directly, e.g. "Boardroom" — resolved
            internally, no need to list_vmrs first).
        alias: Dial string for the auto-participant. Required.
        protocol: "sip" / "h323" / "mssip" / "rtmp" / "gms" / "teams" / "auto".
        call_type: "audio" / "video" / "video-only".
        role: "chair" or "guest".
        system_location: Routing location id or name.
        dtmf_sequence: DTMF tones to send after connect.
        streaming: Marks the participant as a streaming endpoint.
        keep_conference_alive:
            "always" / "if_multiple_other" / "if_one_other_no_chair" / "never".
        routing: "auto" or "manual".
        remote_display_name: Override the display name shown to others.
        description: Free-text description.
    """
    client = get_client(ctx)
    vmr_id = await resolve_id_by_field(
        client, "conference", vmr, field="name", service_type="conference"
    )
    payload: dict[str, Any] = {"alias": alias, "conference": fk_uri("conference", vmr_id)}
    location_uri: str | None = None
    if system_location is not None:
        loc_id = await resolve_id_by_field(
            client, "system_location", system_location, field="name"
        )
        location_uri = fk_uri("system_location", loc_id)
    for field, value in (
        ("protocol", protocol),
        ("call_type", call_type),
        ("role", role),
        ("system_location", location_uri),
        ("dtmf_sequence", dtmf_sequence),
        ("streaming", streaming),
        ("keep_conference_alive", keep_conference_alive),
        ("routing", routing),
        ("remote_display_name", remote_display_name),
        ("description", description),
    ):
        if value is not None:
            payload[field] = value
    location = await client.create("automatic_participant", payload)
    return await client.get("automatic_participant", extract_id_from_uri(location))


@mcp.tool(annotations=delete("Delete automatic participant"))
async def delete_automatic_participant(ctx: Context, participant_id: int) -> dict[str, Any]:
    """Delete an automatic_participant by id. Use list_automatic_participants to find it."""
    await get_client(ctx).delete("automatic_participant", participant_id)
    return {"deleted": True, "id": participant_id}
