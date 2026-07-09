"""Command API tools — actively control running conferences, participants, and platform.

The Command API (``/api/admin/command/v1/``) is Pexip's "do something live" surface.
Three scopes:

  - **participant** — dial, disconnect, mute, unmute, unlock, transfer, role
  - **conference** — disconnect, lock/unlock, mute/unmute guests, transform_layout,
    LDAP sync, provisioning emails
  - **platform** — backup create/restore, certificate import, cloud node start,
    snapshot, upgrade, software bundle upload

Conference-scoped tools accept the conference's **name or alias** (e.g.
"All Hands") as well as its runtime UUID — the server resolves a name to the
currently-running conference for you, so you do NOT need to call
list_active_conferences first when the user names the conference. (If the user
doesn't name one and several are live, list_active_conferences to pick the
right id.) Participant-scoped tools take the participant UUID from
list_active_participants.
"""
from __future__ import annotations

import re
from typing import Any

from mcp.server.fastmcp import Context

from pexip_mcp.client import PexipError
from pexip_mcp.mcp_app import mcp
from pexip_mcp.tools._helpers import control, get_client

# Runtime (status-API) ids are UUIDs. Anything that isn't a UUID is treated as a
# human name/alias and resolved against the live conference list.
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)


async def _resolve_active_conference_id(ctx: Context, conference: str) -> str:
    """Resolve a running-conference reference to its Status-API UUID.

    Accepts the UUID directly, or the name/alias of a currently-running
    conference (e.g. "All Hands"), looked up via the Status API. Raises
    PexipError(404) if nothing by that name is live, PexipError(409) if the
    name is ambiguous.
    """
    value = str(conference)
    if _UUID_RE.match(value):
        return value
    result = await get_client(ctx).list("conference", api="status", name=value, limit=2)
    objects = result.get("objects", [])
    if not objects:
        raise PexipError(
            404,
            {"conference": [
                f"No running conference named {value!r} — it may not be in "
                "progress right now (check list_active_conferences)."
            ]},
        )
    if len(objects) > 1:
        raise PexipError(
            409,
            {"conference": [
                f"Multiple running conferences named {value!r}; pass the UUID "
                "from list_active_conferences to disambiguate."
            ]},
        )
    return objects[0]["id"]


async def _resolve_active_participant_id(
    ctx: Context, participant: str, conference: str | None = None
) -> str:
    """Resolve a participant reference to its Status-API UUID.

    Accepts the UUID directly, or a participant display name (e.g. "Alice"),
    matched case-insensitively (exact first, then substring) against currently
    connected participants. Pass `conference` (name) to scope the search to one
    meeting when a display name might not be unique. Raises PexipError(404) for
    no match, PexipError(409) when the name is ambiguous.
    """
    value = str(participant)
    if _UUID_RE.match(value):
        return value
    params: dict[str, Any] = {"limit": 200}
    if conference:
        params["conference"] = conference
    result = await get_client(ctx).list("participant", api="status", **params)
    objects = result.get("objects", [])
    scope = f" in conference {conference!r}" if conference else ""
    exact = [o for o in objects if str(o.get("display_name", "")).strip().lower() == value.lower()]
    matches = exact or [
        o for o in objects if value.lower() in str(o.get("display_name", "")).lower()
    ]
    if not matches:
        raise PexipError(
            404,
            {"participant": [
                f"No active participant matching {value!r}{scope} — check "
                "list_active_participants."
            ]},
        )
    if len(matches) > 1:
        raise PexipError(
            409,
            {"participant": [
                f"Multiple active participants match {value!r}{scope}; pass the "
                "UUID, or a conference name, to disambiguate."
            ]},
        )
    return matches[0]["id"]


# ---------- Participant scope ----------


@mcp.tool(annotations=control("Dial out to add a participant", idempotent=False))
async def dial_participant(
    ctx: Context,
    conference_alias: str,
    destination: str,
    protocol: str | None = None,
    call_type: str | None = None,
    role: str | None = None,
    system_location: int | str | None = None,
    streaming: bool | None = None,
    remote_display_name: str | None = None,
    dtmf_sequence: str | None = None,
) -> dict[str, Any]:
    """Dial out to add a new participant to a running conference.

    Each call places one new outbound call leg — repeated invocations dial
    repeatedly. Not idempotent.

    Args:
        conference_alias: Alias of the conference to dial INTO.
        destination: SIP URI / E.164 / H.323 alias of the participant to dial OUT to.
        protocol: "sip" / "h323" / "mssip" / "rtmp" / "teams" / "gms" / "auto".
        call_type: "audio" / "video" / "video-only" / "audio-video".
        role: "chair" or "guest".
        system_location: Routing location id or exact name.
        streaming: Mark this leg as a streaming endpoint.
        remote_display_name: Override the display name shown to others.
        dtmf_sequence: DTMF tones to send after connect.
    """
    client = get_client(ctx)
    body: dict[str, Any] = {
        "conference_alias": conference_alias,
        "destination": destination,
    }
    if system_location is not None:
        if isinstance(system_location, int) or (
            isinstance(system_location, str) and system_location.isdigit()
        ):
            loc_id = int(system_location)
            loc = await client.get("system_location", loc_id)
            body["system_location"] = loc["name"]
        else:
            body["system_location"] = system_location
    for f, v in (
        ("protocol", protocol),
        ("call_type", call_type),
        ("role", role),
        ("streaming", streaming),
        ("remote_display_name", remote_display_name),
        ("dtmf_sequence", dtmf_sequence),
    ):
        if v is not None:
            body[f] = v
    return await client.command("participant", "dial", body)


@mcp.tool(annotations=control("Disconnect (kick) a participant"))
async def disconnect_participant(
    ctx: Context, participant_id: str, conference: str | None = None
) -> dict[str, Any]:
    """Disconnect (kick) a single active participant from their call.

    Idempotent: returns success with `note: "already disconnected"` if the
    participant has already left.

    Args:
        participant_id: the participant's display name (e.g. "Alice") or their
            UUID — a name is resolved automatically, so you do NOT need to call
            list_active_participants first.
        conference: optional conference name to scope the name lookup when a
            display name might not be unique across meetings.
    """
    pid = await _resolve_active_participant_id(ctx, participant_id, conference)
    try:
        return await get_client(ctx).command(
            "participant", "disconnect", {"participant_id": pid}
        )
    except PexipError as e:
        if e.status_code == 404:
            return {
                "status": "success",
                "note": "already disconnected",
                "participant_id": pid,
            }
        raise


@mcp.tool(annotations=control("Audio-mute a participant"))
async def mute_participant(
    ctx: Context, participant_id: str, conference: str | None = None
) -> dict[str, Any]:
    """Audio-mute one participant. Idempotent.

    participant_id: the participant's display name (e.g. "Alice") or UUID — a
    name is resolved automatically. Pass `conference` (name) to scope if the
    name isn't unique.
    """
    pid = await _resolve_active_participant_id(ctx, participant_id, conference)
    return await get_client(ctx).command(
        "participant", "mute", {"participant_id": pid}
    )


@mcp.tool(annotations=control("Audio-unmute a participant"))
async def unmute_participant(
    ctx: Context, participant_id: str, conference: str | None = None
) -> dict[str, Any]:
    """Audio-unmute one participant. Idempotent.

    participant_id: the participant's display name or UUID (name auto-resolved).
    Pass `conference` (name) to scope if the name isn't unique.
    """
    pid = await _resolve_active_participant_id(ctx, participant_id, conference)
    return await get_client(ctx).command(
        "participant", "unmute", {"participant_id": pid}
    )


@mcp.tool(annotations=control("Set participant role (chair/guest)"))
async def set_participant_role(
    ctx: Context, participant_id: str, role: str, conference: str | None = None
) -> dict[str, Any]:
    """Change a participant's role. Idempotent.

    Args:
        participant_id: the participant's display name (e.g. "Alice") or UUID —
            a name is resolved automatically.
        role: "chair" or "guest".
        conference: optional conference name to scope the name lookup.
    """
    if role not in ("chair", "guest"):
        raise PexipError(400, {"role": [f"Must be 'chair' or 'guest', got {role!r}"]})
    pid = await _resolve_active_participant_id(ctx, participant_id, conference)
    return await get_client(ctx).command(
        "participant", "role", {"participant_id": pid, "role": role}
    )


@mcp.tool(annotations=control("Transfer a participant", idempotent=False))
async def transfer_participant(
    ctx: Context,
    participant_id: str,
    conference_alias: str,
    role: str | None = None,
    pin: str | None = None,
) -> dict[str, Any]:
    """Move a participant from their current conference to another one.

    Useful for breakout-room flows. Not idempotent — once transferred, calling
    again with the same participant_id will fail because they're no longer in
    the source conference.

    Args:
        participant_id: the participant's display name (e.g. "Alice") or UUID —
            a name is resolved automatically.
        conference_alias: Alias of the target conference.
        role: "chair" or "guest" in the target conference.
        pin: PIN for the target conference if it is PIN-protected.
    """
    if role is not None and role not in ("chair", "guest"):
        raise PexipError(400, {"role": [f"Must be 'chair' or 'guest', got {role!r}"]})
    pid = await _resolve_active_participant_id(ctx, participant_id)
    body: dict[str, Any] = {
        "participant_id": pid,
        "conference_alias": conference_alias,
    }
    if role is not None:
        body["role"] = role
    if pin is not None:
        body["pin"] = pin
    return await get_client(ctx).command("participant", "transfer", body)


# ---------- Conference scope ----------


@mcp.tool(annotations=control("End a conference (disconnect everyone)"))
async def disconnect_conference(ctx: Context, conference_id: str) -> dict[str, Any]:
    """Disconnect all participants in a conference, ending the meeting.

    DESTRUCTIVE: every connected participant is dropped. Confirm with the
    user before invoking unless they were unambiguous.

    Args:
        conference_id: The running conference's name/alias (e.g. "All Hands")
            or its UUID. A name is resolved to the live conference for you —
            no need to call list_active_conferences first.
    """
    conf_id = await _resolve_active_conference_id(ctx, conference_id)
    try:
        return await get_client(ctx).command(
            "conference", "disconnect", {"conference_id": conf_id}
        )
    except PexipError as e:
        if e.status_code == 404:
            return {
                "status": "success",
                "note": "conference already ended",
                "conference_id": conf_id,
            }
        raise


@mcp.tool(annotations=control("Lock a conference"))
async def lock_conference(ctx: Context, conference_id: str) -> dict[str, Any]:
    """Lock a running conference. New joiners are held at the
    'Waiting for host' screen until unlocked. Idempotent.

    conference_id: the conference name/alias (e.g. "All Hands") or its UUID —
    a name is resolved automatically; no need to list active conferences first.
    """
    conf_id = await _resolve_active_conference_id(ctx, conference_id)
    return await get_client(ctx).command(
        "conference", "lock", {"conference_id": conf_id}
    )


@mcp.tool(annotations=control("Unlock a conference"))
async def unlock_conference(ctx: Context, conference_id: str) -> dict[str, Any]:
    """Unlock a conference, allowing new joiners again. Idempotent.

    conference_id: the conference name/alias or its UUID (name auto-resolved).
    """
    conf_id = await _resolve_active_conference_id(ctx, conference_id)
    return await get_client(ctx).command(
        "conference", "unlock", {"conference_id": conf_id}
    )


@mcp.tool(annotations=control("Mute all guests in a conference"))
async def mute_guests(ctx: Context, conference_id: str) -> dict[str, Any]:
    """Audio-mute every participant with role=guest. Hosts/chairs are
    unaffected. Idempotent.

    conference_id: the conference name/alias (e.g. "All Hands") or its UUID —
    a name is resolved automatically; no need to list active conferences first.
    """
    conf_id = await _resolve_active_conference_id(ctx, conference_id)
    return await get_client(ctx).command(
        "conference", "mute_guests", {"conference_id": conf_id}
    )


@mcp.tool(annotations=control("Unmute all guests in a conference"))
async def unmute_guests(ctx: Context, conference_id: str) -> dict[str, Any]:
    """Audio-unmute every guest. Idempotent.

    conference_id: the conference name/alias or its UUID (name auto-resolved).
    """
    conf_id = await _resolve_active_conference_id(ctx, conference_id)
    return await get_client(ctx).command(
        "conference", "unmute_guests", {"conference_id": conf_id}
    )


@mcp.tool(annotations=control("Change a conference's layout"))
async def set_conference_layout(
    ctx: Context,
    conference_id: str,
    host_layout: str | None = None,
    guest_layout: str | None = None,
) -> dict[str, Any]:
    """Change the active layout for a running conference.

    Uses transform_layout under the hood. Pass at least one layout field.
    Common layout values: "one_main_zero_pips", "two_mains_seven_pips",
    "four_mains_zero_pips", "nine_equal", "sixteen_equal".

    Args:
        conference_id: the conference name/alias (e.g. "All Hands") or its UUID —
            a name is resolved automatically; no need to list first.
        host_layout: Layout for participants with role=chair.
        guest_layout: Layout for participants with role=guest.
    """
    transforms: dict[str, Any] = {}
    if host_layout is not None:
        transforms["host_layout"] = host_layout
    if guest_layout is not None:
        transforms["guest_layout"] = guest_layout
    if not transforms:
        raise PexipError(
            400, {"detail": "At least one of host_layout / guest_layout is required"}
        )
    conf_id = await _resolve_active_conference_id(ctx, conference_id)
    return await get_client(ctx).command(
        "conference",
        "transform_layout",
        {"conference_id": conf_id, "transforms": transforms},
    )


# ---------- Participant unlock ----------


@mcp.tool(annotations=control("Unlock a participant"))
async def unlock_participant(
    ctx: Context, participant_id: str, conference: str | None = None
) -> dict[str, Any]:
    """Unlock a participant who is waiting in the lobby.

    Args:
        participant_id: the participant's display name (e.g. "Alice") or UUID —
            a name is resolved automatically.
        conference: optional conference name to scope the name lookup.
    """
    pid = await _resolve_active_participant_id(ctx, participant_id, conference)
    return await get_client(ctx).command(
        "participant", "unlock", {"participant_id": pid}
    )


# ---------- Conference: LDAP sync ----------


@mcp.tool(annotations=control("Sync LDAP conference template", idempotent=False))
async def sync_conference_ldap(
    ctx: Context, conference_id: int
) -> dict[str, Any]:
    """Trigger an LDAP sync for a conference sync template.

    Args:
        conference_id: Integer id of the conference sync template (Configuration API id).
    """
    return await get_client(ctx).command(
        "conference", "sync", {"conference_id": conference_id}
    )


# ---------- Conference: provisioning emails ----------


@mcp.tool(annotations=control("Send VMR provisioning email", idempotent=False))
async def send_conference_email(
    ctx: Context, conference_id: int
) -> dict[str, Any]:
    """Send a provisioning email to the owner of a VMR.

    Args:
        conference_id: Integer id of the conference/VMR (Configuration API id).
    """
    return await get_client(ctx).command(
        "conference", "send_conference_email", {"conference_id": conference_id}
    )


@mcp.tool(annotations=control("Send device provisioning email", idempotent=False))
async def send_device_email(
    ctx: Context, conference_id: int
) -> dict[str, Any]:
    """Send a provisioning email to the owner of a device.

    Args:
        conference_id: Integer id of the conference/VMR (Configuration API id).
    """
    return await get_client(ctx).command(
        "conference", "send_device_email", {"conference_id": conference_id}
    )


# ---------- Platform commands ----------


@mcp.tool(annotations=control("Create platform backup", idempotent=False))
async def backup_create(ctx: Context) -> dict[str, Any]:
    """Create a system backup of the Pexip platform."""
    return await get_client(ctx).command("platform", "backup_create")


@mcp.tool(annotations=control("Restore platform backup", idempotent=False))
async def backup_restore(
    ctx: Context, backup_id: int
) -> dict[str, Any]:
    """Restore a system backup. DESTRUCTIVE — replaces current platform state.

    Args:
        backup_id: Integer id of the backup to restore.
    """
    return await get_client(ctx).command(
        "platform", "backup_restore", {"backup_id": backup_id}
    )


@mcp.tool(annotations=control("Import certificates", idempotent=False))
async def certificates_import(
    ctx: Context, settings: dict[str, Any]
) -> dict[str, Any]:
    """Upload and import TLS/CA certificates.

    Args:
        settings: Certificate import payload. Discover fields with the
            command schema at /api/admin/command/v1/platform/certificates_import/schema/.
    """
    return await get_client(ctx).command(
        "platform", "certificates_import", settings
    )


@mcp.tool(annotations=control("Start cloud overflow node", idempotent=False))
async def start_cloud_node(
    ctx: Context, settings: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Start an overflow Conferencing Node (dynamic bursting).

    Args:
        settings: Optional cloud node parameters.
    """
    return await get_client(ctx).command(
        "platform", "start_cloudnode", settings or {}
    )


@mcp.tool(annotations=control("Take system snapshot", idempotent=False))
async def take_snapshot(ctx: Context) -> dict[str, Any]:
    """Take a system snapshot of the Pexip platform for diagnostics."""
    return await get_client(ctx).command("platform", "snapshot")


@mcp.tool(annotations=control("Trigger platform upgrade", idempotent=False))
async def platform_upgrade(
    ctx: Context, settings: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Trigger a platform upgrade. DESTRUCTIVE — initiates software upgrade.

    Args:
        settings: Optional upgrade parameters.
    """
    return await get_client(ctx).command(
        "platform", "upgrade", settings or {}
    )


@mcp.tool(annotations=control("Upload software bundle", idempotent=False))
async def upload_software_bundle(
    ctx: Context, settings: dict[str, Any]
) -> dict[str, Any]:
    """Upload a software bundle to the platform.

    Args:
        settings: Software bundle upload payload.
    """
    return await get_client(ctx).command(
        "platform", "software_bundle", settings
    )
