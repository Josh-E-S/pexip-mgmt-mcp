"""Per-tool usage guidance applied at registration time.

Each tool's docstring says WHAT it does. This table adds the parts the model
needs to pick the right tool and fill it in correctly, in a shape that can be
linted (tests/test_catalog_quality.py) and tuned from eval transcripts without
touching fifteen modules:

  use_when   one sentence naming the situations this tool is the right answer for
  avoid      one sentence naming the sibling tool to use instead, and when
  docs       the Pexip Management API reference page (required for tools that
             take a caller-constructed payload or filter dict)
  examples   1-3 realistic argument sets for tools with several optional
             parameters, covering the formats JSON Schema cannot express
             (UTC ISO-8601 timestamps, name-or-id arguments, enum spellings).
             Emitted as `input_examples` in the tool's `_meta`.

Keys are the UNPREFIXED function names; mcp_app applies the `pexip_` prefix.

Rendered onto the description as:

    <docstring>

    Use when: ...
    Do not use when: ...
    API reference: <url>
"""

from __future__ import annotations

import re
from typing import Any, TypedDict

CONFIG_API = "https://docs.pexip.com/api_manage/api_configuration.htm"
STATUS_API = "https://docs.pexip.com/api_manage/api_status.htm"
HISTORY_API = "https://docs.pexip.com/api_manage/api_history.htm"
COMMAND_API = "https://docs.pexip.com/api_manage/api_command.htm"


class Guidance(TypedDict, total=False):
    use_when: str
    avoid: str
    docs: str
    examples: list[dict[str, Any]]


def _g(
    use_when: str,
    avoid: str,
    *,
    docs: str | None = None,
    examples: list[dict[str, Any]] | None = None,
) -> Guidance:
    g: Guidance = {"use_when": use_when, "avoid": avoid}
    if docs:
        g["docs"] = docs
    if examples:
        g["examples"] = examples
    return g


_TS = "2026-10-01T00:00:00"
_TS2 = "2026-10-08T00:00:00"

GUIDANCE: dict[str, Guidance] = {
    # ── VMRs (conference.py) ─────────────────────────────────────────────────
    "list_vmrs": _g(
        "the user wants to see, count, or search Virtual Meeting Rooms (persistent rooms), "
        "optionally by name fragment or tag.",
        "the question is about a meeting happening right now (list_active_conferences) or "
        "about past calls (list_history_conferences).",
        examples=[{"name_contains": "standup", "limit": 20}, {"tag": "finance"}],
    ),
    "get_vmr": _g(
        "the user names one VMR and wants its full configuration (PINs are masked).",
        "the user wants the room's live participants (list_active_participants) or "
        "wants to change it (update_vmr).",
    ),
    "create_vmr": _g(
        "the user asks for a new persistent meeting room; pass aliases in the same call so "
        "the room is dialable immediately.",
        "the room already exists (update_vmr / add_vmr_alias), or the user wants a one-off "
        "dial-out (dial_participant).",
        examples=[
            {"name": "Engineering Standup", "aliases": ["standup@example.com"], "pin": "4821"},
            {
                "name": "Town Hall",
                "aliases": ["townhall@example.com", "1234"],
                "pin": "778812",
                "guest_pin": "4455",
                "allow_guests": True,
                "host_view": "one_main_zero_pips",
            },
            {"name": "Open Lab", "aliases": ["lab@example.com"], "allow_no_pin": True},
        ],
    ),
    "update_vmr": _g(
        "the user wants to change a VMR's PIN, description, tag, layout or guest policy; pass "
        "the room's name directly as `vmr`.",
        "the change is to aliases (add_vmr_alias / delete_alias) or to a live meeting's layout "
        "(set_conference_layout).",
        examples=[
            {"vmr": "Boardroom", "description": "Executive meetings only"},
            {"vmr": 42, "pin": "991122", "guest_pin": "3344", "allow_guests": True},
        ],
    ),
    "delete_vmr": _g(
        "the user explicitly asks to remove a VMR; confirm the name first because the "
        "deletion cannot be undone.",
        "the user only wants to end a meeting in progress (disconnect_conference).",
    ),
    # ── Aliases (alias.py) ───────────────────────────────────────────────────
    "list_aliases": _g(
        "the user wants to know which dial strings reach a VMR, or to find the alias id "
        "before deleting one.",
        "the user wants registered endpoint aliases (list_status(resource='registration_alias')).",
        examples=[{"vmr": "Boardroom"}, {"alias_contains": "@example.com", "limit": 50}],
    ),
    "add_vmr_alias": _g(
        "the user wants an extra dial string (SIP URI, number, name) to reach an existing VMR.",
        "the VMR does not exist yet (create_vmr with `aliases`).",
    ),
    "delete_alias": _g(
        "the user wants to remove one dial string from a VMR; find its id with list_aliases.",
        "the user wants to remove the whole room (delete_vmr).",
    ),
    # ── Automatic participants (automatic_participant.py) ────────────────────
    "list_automatic_participants": _g(
        "the user asks which recorders, streamers or dial-out endpoints are attached to VMRs.",
        "the user asks who is in a meeting right now (list_active_participants).",
        examples=[{"vmr": "Town Hall"}, {"alias_contains": "recorder"}],
    ),
    "add_automatic_participant": _g(
        "the user wants a VMR to automatically dial an endpoint (recorder, streaming server, "
        "room system) whenever the room starts.",
        "the user wants to dial someone into a meeting that is already running (dial_participant).",
        examples=[
            {"vmr": "Town Hall", "alias": "sip:recorder@media.example.com", "role": "guest"},
            {
                "vmr": "All Hands",
                "alias": "rtmp://stream.example.com/live/allhands",
                "protocol": "rtmp",
                "streaming": True,
                "remote_display_name": "Live stream",
            },
        ],
    ),
    "delete_automatic_participant": _g(
        "the user wants a VMR to stop auto-dialing an endpoint; find the id with "
        "list_automatic_participants.",
        "the user wants to drop a participant from a live call (disconnect_participant).",
    ),
    # ── End users (end_user.py) ──────────────────────────────────────────────
    "list_end_users": _g(
        "the user wants to find or count directory users, by email or name fragment or by "
        "LDAP sync tag.",
        "the user means provisioned devices/endpoints (list_devices) or people in a call "
        "(list_active_participants).",
        examples=[{"email_contains": "@example.com", "limit": 50}, {"name_contains": "Alice"}],
    ),
    "get_end_user": _g(
        "the user names one directory user (by email or id) and wants the record.",
        "the user wants to modify the record (update_end_user).",
    ),
    "create_end_user": _g(
        "the user asks to add a person to the Pexip directory; primary_email_address is the "
        "identity.",
        "the user is managed by LDAP sync (create_resource(resource='ldap_sync_source') / sync) or is a device "
        "(create_device).",
        examples=[
            {
                "primary_email_address": "alice@example.com",
                "first_name": "Alice",
                "last_name": "Ng",
            },
            {
                "primary_email_address": "bob@example.com",
                "display_name": "Bob Lee",
                "department": "Sales",
                "title": "Account Executive",
            },
        ],
    ),
    "update_end_user": _g(
        "the user wants to change a directory user's name, phone, title or department; pass "
        "the email as `user`.",
        "the field is the email itself (delete and recreate) or the user is LDAP-synced.",
        examples=[{"user": "alice@example.com", "department": "Platform"}],
    ),
    "delete_end_user": _g(
        "the user explicitly asks to remove a directory user; irreversible.",
        "the user only wants to deactivate a device (update_device / delete_device).",
    ),
    # ── Devices (device.py) ──────────────────────────────────────────────────
    "list_devices": _g(
        "the user wants provisioned device records (registration aliases with credentials).",
        "the user wants to know which endpoints are registered RIGHT NOW (list_registrations).",
        examples=[{"alias_contains": "room", "limit": 50}, {"owner_email": "alice@example.com"}],
    ),
    "list_registrations": _g(
        "the user asks which endpoints are currently registered, or whether a specific room "
        "system is online.",
        "the user wants the provisioning records themselves (list_devices) or history "
        "(list_history(resource='registration_alias')).",
        examples=[{"alias_contains": "boardroom"}, {"protocol": "sip", "fetch_all": True}],
    ),
    "get_device": _g(
        "the user names one device (by alias or id) and wants its record (password masked).",
        "the user wants to change it (update_device).",
    ),
    "create_device": _g(
        "the user wants to let a new endpoint register; alias is the registration identity.",
        "the user is a person (create_end_user) or wants a meeting room (create_vmr).",
        examples=[
            {"alias": "boardroom@example.com", "username": "boardroom", "password": "Str0ng-Pass!"},
            {
                "alias": "lobby-sign@example.com",
                "description": "Lobby display",
                "primary_owner_email_address": "facilities@example.com",
                "enable_sip": True,
                "enable_h323": False,
            },
        ],
    ),
    "update_device": _g(
        "the user wants to rotate a device password, change its alias/owner, or toggle "
        "protocols; pass the alias as `device`.",
        "the endpoint is only offline (check list_registrations) rather than misconfigured.",
        examples=[{"device": "boardroom@example.com", "password": "N3w-Str0ng!"}],
    ),
    "delete_device": _g(
        "the user explicitly asks to remove a device record so it can no longer register.",
        "the user only wants to see or change the record.",
    ),
    # ── Gateway rules (gateway_rule.py) ──────────────────────────────────────
    "list_gateway_rules": _g(
        "the user asks how calls are routed, which dial-plan rules exist, or which rule a "
        "pattern would match (rules return ordered by priority).",
        "the user asks about a VMR's aliases (list_aliases).",
        examples=[{"enabled_only": True}, {"name_contains": "teams", "limit": 50}],
    ),
    "get_gateway_rule": _g(
        "the user names one routing rule and wants its match/replace pattern and target.",
        "the user wants to change it (update_gateway_rule).",
    ),
    "create_gateway_rule": _g(
        "the user wants calls matching a pattern routed to a protocol/location; lower "
        "priority wins; match_string is a regex.",
        "the destination is a VMR (add_vmr_alias) or the rule already exists "
        "(update_gateway_rule).",
        examples=[
            {
                "name": "Teams dial-in",
                "priority": 100,
                "match_string": r"^teams\.(.+)$",
                "replace_string": r"\1",
                "outgoing_protocol": "teams",
            },
            {
                "name": "PSTN out",
                "priority": 200,
                "match_string": r"^\+?[0-9]{7,15}$",
                "outgoing_protocol": "sip",
                "outgoing_location": "London",
                "enable": True,
            },
        ],
    ),
    "update_gateway_rule": _g(
        "the user wants to change a rule's pattern, priority, target or enabled state; pass "
        "the rule name as `rule`.",
        "the user wants a new rule alongside (create_gateway_rule).",
        examples=[{"rule": "PSTN out", "enable": False}, {"rule": 7, "priority": 50}],
    ),
    "delete_gateway_rule": _g(
        "the user explicitly asks to remove a routing rule; prefer `enable: false` via "
        "update_gateway_rule when they may want it back.",
        "the user wants to disable temporarily (update_gateway_rule).",
    ),
    # ── LDAP (ldap.py) ───────────────────────────────────────────────────────
    # ── Infrastructure (infrastructure.py) ───────────────────────────────────
    "list_locations": _g(
        "the user asks which system locations (data centres / regions) exist, or needs a "
        "location name for another tool.",
        "the user asks about current load per location (list_status(resource='system_location')).",
        examples=[{}, {"name_contains": "EU", "fields": ["name", "description"]}],
    ),
    "get_location": _g(
        "the user names one system location and wants its configuration.",
        "the user wants live load or status for it (get_status(resource='system_location') / "
        "get_status(resource='system_location/{id}/statistics')).",
    ),
    "list_conferencing_nodes": _g(
        "the user asks which Conferencing Nodes exist, in which location, or of which type "
        "(CONFERENCING vs PROXYING).",
        "the user asks whether nodes are healthy or loaded right now (list_node_status).",
        examples=[{"location": "London"}, {"node_type": "PROXYING", "limit": 50}],
    ),
    "get_conferencing_node": _g(
        "the user names one Conferencing Node and wants its configuration.",
        "the user wants its live load (get_status(resource='worker_vm/{id}/statistics')) or status (get_node_status).",
    ),
    # ── IVR themes (ivr_theme.py) ────────────────────────────────────────────
    # ── Global settings (global_settings.py) ─────────────────────────────────
    # ── Generic configuration CRUD (resource_crud.py) ────────────────────────
    "list_resources": _g(
        "the configuration resource has no dedicated tool (SIP/H.323 proxies, TURN/STUN, DNS/"
        "NTP/syslog, certificates, Teams/Google integrations, MJX, backups, policy, ...).",
        "a dedicated tool exists: VMRs (list_vmrs), aliases, devices, end users, gateway "
        "rules, LDAP sources, locations, nodes, themes.",
        docs=CONFIG_API,
        examples=[
            {"resource": "sip_proxy"},
            {"resource": "dns_server", "filters": {"address__icontains": "10.0"}},
            {"resource": "system_backup", "limit": 5},
        ],
    ),
    "get_resource": _g(
        "the user names one generic configuration object (by name or id) that has no "
        "dedicated get tool.",
        "a dedicated tool exists for the resource type.",
    ),
    "create_resource": _g(
        "the user wants a new generic configuration object; simple ones need only their "
        "obvious fields (a DNS server is {'address': ...}).",
        "a dedicated create tool exists, or the resource is security-critical and the server "
        "is not started with PEXIP_ALLOW_SECURITY_RESOURCES=true.",
        docs=CONFIG_API,
        examples=[
            {"resource": "dns_server", "settings": {"address": "10.0.0.53"}},
            {"resource": "syslog_server", "settings": {"address": "10.0.0.99", "port": 514}},
        ],
    ),
    "update_resource": _g(
        "the user wants to change fields on a generic configuration object; only the given "
        "fields change.",
        "a dedicated update tool exists for the resource type.",
        docs=CONFIG_API,
        examples=[
            {
                "resource": "ntp_server",
                "id": "pool.ntp.org",
                "settings": {"address": "time.example.com"},
            }
        ],
    ),
    "delete_resource": _g(
        "the user explicitly asks to remove a generic configuration object; irreversible.",
        "a dedicated delete tool exists for the resource type.",
        docs=CONFIG_API,
    ),
    # ── Discovery and health (discovery.py, health.py) ───────────────────────
    "describe_resources": _g(
        "you are unsure which tool or resource name covers a request, the user asks what "
        "the server can do, or a tool you expected is missing (it reports enabled toolsets).",
        "you already know the tool; call it directly.",
        examples=[
            {"query": "teams"},
            {"api": "status", "detail": "names"},
            {"query": "sip proxy", "detail": "full"},
        ],
    ),
    "get_platform_health": _g(
        "the user asks whether the platform is OK, healthy, or has problems right now; it "
        "replaces four separate calls with one summary and a verdict.",
        "the user wants one specific list (list_alarms, list_node_status, "
        "get_licensing_status) or historical health (list_history(resource='alarm')).",
    ),
    # ── Generic status / history (status_generic.py, history_generic.py) ─────
    "list_status": _g(
        "the live-state question is about a resource with no dedicated tool: Teams Connector, "
        "One-Touch Join, cloud overflow, backplanes, shards, conference sync, Exchange "
        "scheduler, Management Node, registered aliases, or location status.",
        "a dedicated tool exists (list_active_conferences, list_active_participants, "
        "list_alarms, list_node_status, list_registrations, get_licensing_status).",
        docs=STATUS_API,
        examples=[
            {"resource": "teamsnode"},
            {"resource": "mjx_endpoint", "name_contains": "boardroom"},
            {"resource": "conference_shard", "filters": {"conference": "All Hands"}},
        ],
    ),
    "get_status": _g(
        "the user wants one live status object by id, or a per-object statistics sub-resource "
        "such as a node's load (worker_vm/{id}/statistics) or a location's.",
        "the user wants a list (list_status) or one of the typed tools (get_node_status, "
        "get_active_participant).",
        docs=STATUS_API,
        examples=[
            {"resource": "worker_vm/{id}/statistics", "id": 3},
            {"resource": "teamsnode", "id": "tc-01"},
        ],
    ),
    "list_history": _g(
        "the user asks about past alarms, past backplanes, registration/unregistration events, "
        "or Conferencing Node up/down events.",
        "the question is about calls (list_history_conferences, list_history_participants, "
        "summarize_calls) or current state (list_alarms, list_status).",
        docs=HISTORY_API,
        examples=[
            {
                "resource": "alarm",
                "start_time": _TS,
                "end_time": _TS2,
                "filters": {"level": "critical"},
            },
            {"resource": "registration_alias", "name_contains": "boardroom"},
            {"resource": "workervm_status_event", "start_time": _TS, "end_time": _TS2},
        ],
    ),
    "get_history": _g(
        "the user wants one past alarm, backplane, registration event or node event by id, or a "
        "past backplane's media streams (backplane/{id}/media_stream).",
        "the record is a call (get_history_conference, get_history_participant).",
        docs=HISTORY_API,
    ),
    "send_provisioning_email": _g(
        "the user wants a VMR owner or a device owner emailed their provisioning details.",
        "the user wants to change the owner (update_vmr / update_device).",
        docs=COMMAND_API,
    ),
    "run_platform_command": _g(
        "the user explicitly asks for a platform-lifecycle action: take a backup or diagnostic "
        "snapshot, restore a backup, import certificates, start a cloud overflow node, upload a "
        "software bundle, or start an upgrade.",
        "anything that is not an explicit, confirmed request: these commands can replace or "
        "compromise the whole deployment, and backups/bundles are listed with list_resources.",
        docs=COMMAND_API,
        examples=[
            {"command": "backup_create"},
            {"command": "backup_restore", "params": {"backup_id": 12}},
        ],
    ),
    # ── Schema (schema.py) ───────────────────────────────────────────────────
    "get_resource_schema": _g(
        "you are about to create or update a resource and are unsure of its field names, "
        "required fields, or enum values; schemas drift between Pexip versions.",
        "the field is already documented in the tool you are about to call.",
        docs=CONFIG_API,
    ),
    # ── Status: live state (status.py) ───────────────────────────────────────
    "list_active_conferences": _g(
        "the user asks what meetings are happening now, or needs to confirm a conference is "
        "live before a control action with an ambiguous name.",
        "the meeting is over (list_history_conferences) or the question is about room "
        "configuration (list_vmrs).",
        examples=[{}, {"name": "All Hands"}, {"service_type": "gateway", "fetch_all": True}],
    ),
    "list_active_participants": _g(
        "the user asks who is in a meeting right now, how many are connected, or who joined "
        "late; filter by conference_name.",
        "the call has ended (list_history_participants) or the user wants to act on one "
        "person by name (the control tools resolve names themselves).",
        examples=[{"conference_name": "All Hands"}, {"role": "guest", "is_muted": False}],
    ),
    "get_active_participant": _g(
        "the user wants details of one connected participant (protocol, address, role, "
        "connect time); pass the display name.",
        "the user wants media quality numbers (get_participant_quality).",
    ),
    "get_participant_quality": _g(
        "someone reports a bad call RIGHT NOW and the user wants bitrate, packet loss, jitter "
        "and codec per stream; pass the display name.",
        "the call has ended (get_history_participant has bucketed_call_quality).",
    ),
    "list_alarms": _g(
        "the user asks whether the platform is healthy or what is currently alarming.",
        "the user asks what alarmed in the past (list_history(resource='alarm')).",
        examples=[{}, {"level": "critical"}, {"node_name": "conf-node-1"}],
    ),
    "get_licensing_status": _g(
        "the user asks how many ports/licences are in use or how close to the cap the platform is.",
        "the user wants licence configuration objects (list_resources resource='licence').",
    ),
    "list_node_status": _g(
        "the user asks whether Conferencing Nodes are up, in sync, or how loaded they are.",
        "the user wants node configuration (list_conferencing_nodes).",
        examples=[{}, {"location": "London"}, {"name_contains": "proxy"}],
    ),
    "get_node_status": _g(
        "the user names one Conferencing Node and asks if it is healthy.",
        "the user wants numeric load (get_status(resource='worker_vm/{id}/statistics')).",
    ),
    # ── History / CDRs (history.py) ──────────────────────────────────────────
    "summarize_calls": _g(
        "the user asks how many calls, total/average duration, or a breakdown by direction, "
        "quality, protocol, tag, location, conference or disconnect reason over a time window.",
        "the user wants individual records (list_history_participants) or live calls "
        "(list_active_conferences).",
        examples=[
            {"start_time": _TS, "end_time": _TS2, "group_by": "call_direction"},
            {"start_time": _TS, "end_time": _TS2, "group_by": "call_quality", "location": "London"},
            {
                "start_time": _TS,
                "end_time": _TS2,
                "group_by": "conference_name",
                "call_direction": "in",
            },
        ],
    ),
    "list_history_conferences": _g(
        "the user asks which meetings took place in a window, or when a named room was last used.",
        "the user wants totals (summarize_calls) or per-person legs (list_history_participants).",
        examples=[{"start_time": _TS, "end_time": _TS2}, {"name": "All Hands", "limit": 5}],
    ),
    "get_history_conference": _g(
        "the user wants one past conference instance by its history id.",
        "the user wants the room configuration (get_vmr).",
    ),
    "list_history_participants": _g(
        "the user wants individual call legs (CDRs): who called, how long, from where, with "
        "what quality or disconnect reason.",
        "the user wants aggregates (summarize_calls).",
        examples=[
            {"start_time": _TS, "end_time": _TS2, "call_quality": "3_bad"},
            {"conference_name": "All Hands", "limit": 100, "fetch_all": True},
        ],
    ),
    "get_history_participant": _g(
        "the user wants forensic detail on one past call leg, including bucketed call "
        "quality over the call.",
        "the call is live (get_participant_quality).",
    ),
    # ── Command: live control (command.py) ───────────────────────────────────
    "dial_participant": _g(
        "the user wants to call someone (SIP/H.323/phone/Teams) INTO a running conference.",
        "the user wants an endpoint dialed every time the room starts "
        "(add_automatic_participant), or the person is already connected.",
        examples=[
            {"conference_alias": "allhands@example.com", "destination": "sip:alice@example.com"},
            {
                "conference_alias": "standup@example.com",
                "destination": "+14155550123",
                "protocol": "sip",
                "role": "guest",
                "remote_display_name": "Alice (phone)",
            },
        ],
    ),
    "disconnect_participant": _g(
        "the user wants to remove (kick) one person from a live call; pass the display name, "
        "scoped by `conference` if the name could be in several meetings.",
        "the user wants to end the whole meeting (disconnect_conference) or only silence "
        "someone (mute_participant).",
    ),
    "mute_participant": _g(
        "the user wants one person's audio muted; pass the display name.",
        "the user wants all guests muted (mute_guests).",
    ),
    "unmute_participant": _g(
        "the user wants one person's audio unmuted; pass the display name.",
        "the user wants all guests unmuted (unmute_guests).",
    ),
    "set_participant_role": _g(
        "the user wants to promote someone to host/chair or demote to guest in a live call.",
        "the change should persist for the room (update_vmr PINs decide roles at join).",
    ),
    "transfer_participant": _g(
        "the user wants to move a connected person into a different conference (breakout, "
        "escalation).",
        "the user wants to add a NEW person (dial_participant).",
    ),
    "unlock_participant": _g(
        "the user wants to admit someone held in the lobby of a locked conference.",
        "the user wants to unlock the whole conference (unlock_conference).",
    ),
    "disconnect_conference": _g(
        "the user explicitly wants to end a live meeting for everyone; pass the conference "
        "name or alias.",
        "the user wants to remove one person (disconnect_participant) or delete the room "
        "(delete_vmr).",
    ),
    "lock_conference": _g(
        "the user wants to stop new people joining a live meeting; latecomers wait in the lobby.",
        "the user wants to make the room permanently PIN-protected (update_vmr).",
    ),
    "unlock_conference": _g(
        "the user wants to let people join a meeting that was locked.",
        "the user wants to admit one specific waiting person (unlock_participant).",
    ),
    "mute_guests": _g(
        "the user wants everyone except hosts/chairs muted in a live meeting.",
        "the user wants one person muted (mute_participant).",
    ),
    "unmute_guests": _g(
        "the user wants guests to be able to speak again.",
        "the user wants one person unmuted (unmute_participant).",
    ),
    "set_conference_layout": _g(
        "the user wants to change how participants are arranged on screen in a LIVE meeting.",
        "the change should be the room's default (update_vmr host_view / guest_view).",
        docs=COMMAND_API,
    ),
    "sync_conference_ldap": _g(
        "the user wants an LDAP conference sync template to run now; `template_id` is the "
        "conference sync template's integer id.",
        "the user wants user directory sync (LDAP sources) rather than conference templates.",
        docs=COMMAND_API,
    ),
    # ── Command: platform lifecycle (gated by PEXIP_ALLOW_PLATFORM_TOOLS) ────
}


# A bare tool name: not part of a larger identifier, dotted attribute, or URL
# path segment (so `/platform/certificates_import/schema/` is left alone).
_BARE_NAME_RE = re.compile(
    r"(?<![\w./-])("
    + "|".join(sorted(map(re.escape, GUIDANCE), key=len, reverse=True))
    + r")(?![\w/])"
)


def _prefix_tool_names(text: str, prefix: str) -> str:
    """Rewrite bare sibling tool names (list_vmrs) to their published form (pexip_list_vmrs).

    The lookbehind already excludes `_`, so an occurrence that is part of
    `pexip_list_vmrs` never matches and is never double-prefixed.
    """
    if not prefix:
        return text
    return _BARE_NAME_RE.sub(lambda m: prefix + m.group(1), text)


def render_description(
    docstring: str | None, guidance: Guidance | None, *, prefix: str = ""
) -> str:
    """Append the guidance block to a tool's docstring-derived description.

    Sibling tool names in the docstring and guidance are rewritten with `prefix`
    so the model sees the names it can actually call.
    """
    base = (docstring or "").rstrip()
    lines = [base]
    if guidance:
        lines += ["", f"Use when: {guidance['use_when']}", f"Do not use when: {guidance['avoid']}"]
        if guidance.get("docs"):
            lines.append(f"API reference: {guidance['docs']}")
    return _prefix_tool_names("\n".join(lines).strip(), prefix)
