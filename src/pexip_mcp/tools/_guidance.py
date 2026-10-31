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
        "the user wants registered endpoint aliases (list_registration_aliases).",
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
        "the user is managed by LDAP sync (create_ldap_source / sync) or is a device "
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
        "(list_registration_history).",
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
    "list_ldap_sources": _g(
        "the user asks which directories (AD/LDAP) sync users into Pexip.",
        "the user wants the synced users themselves (list_end_users).",
    ),
    "get_ldap_source": _g(
        "the user names one LDAP sync source and wants its settings (bind password masked).",
        "the user wants to change it (update_ldap_source).",
    ),
    "create_ldap_source": _g(
        "the user wants Pexip to pull users from an AD/LDAP server on a schedule.",
        "the user wants to add one person by hand (create_end_user).",
        docs=CONFIG_API,
        examples=[
            {
                "name": "Corp AD",
                "ldap_server": "ldaps://dc1.example.com",
                "ldap_base_dn": "DC=example,DC=com",
                "bind_username": "CN=pexip-sync,OU=Service,DC=example,DC=com",
                "bind_password": "s3cret",
            }
        ],
    ),
    "update_ldap_source": _g(
        "the user wants to change an LDAP source's server, base DN, bind credentials or "
        "filters; pass its name as `source`.",
        "the user wants to trigger a sync now (sync_conference_ldap for conference templates).",
        docs=CONFIG_API,
        examples=[{"source": "Corp AD", "bind_password": "r0tated"}],
    ),
    "delete_ldap_source": _g(
        "the user explicitly asks to stop syncing from a directory.",
        "the user only wants to pause (update_ldap_source with a long interval).",
    ),
    # ── Infrastructure (infrastructure.py) ───────────────────────────────────
    "list_locations": _g(
        "the user asks which system locations (data centres / regions) exist, or needs a "
        "location name for another tool.",
        "the user asks about current load per location (list_location_status).",
    ),
    "get_location": _g(
        "the user names one system location and wants its configuration.",
        "the user wants live load or status for it (get_location_status / "
        "get_location_statistics).",
    ),
    "list_conferencing_nodes": _g(
        "the user asks which Conferencing Nodes exist, in which location, or of which type "
        "(CONFERENCING vs PROXYING).",
        "the user asks whether nodes are healthy or loaded right now (list_node_status).",
        examples=[{"location": "London"}, {"node_type": "PROXYING", "limit": 50}],
    ),
    "get_conferencing_node": _g(
        "the user names one Conferencing Node and wants its configuration.",
        "the user wants its live load (get_node_statistics) or status (get_node_status).",
    ),
    # ── IVR themes (ivr_theme.py) ────────────────────────────────────────────
    "list_ivr_themes": _g(
        "the user asks which branding/IVR themes exist, or needs a theme name to assign to a VMR.",
        "the user wants to change a VMR's layout (update_vmr host_view/guest_view).",
    ),
    "get_ivr_theme": _g(
        "the user names one theme and wants its details.",
        "the user wants the list (list_ivr_themes).",
    ),
    # ── Global settings (global_settings.py) ─────────────────────────────────
    "get_global_settings": _g(
        "the user asks about platform-wide defaults (bandwidth, PIN policy, media settings).",
        "the setting belongs to one VMR, device or location (use that resource's get tool).",
    ),
    "update_global_settings": _g(
        "the user wants to change a platform-wide default; call get_resource_schema('global') "
        "first if unsure of the field name.",
        "the change should apply to one resource only.",
        docs=CONFIG_API,
        examples=[{"updates": {"max_pixels_per_second": "fullhd"}}],
    ),
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
        "the user asks what alarmed in the past (list_alarm_history).",
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
        "the user wants numeric load (get_node_statistics).",
    ),
    "get_node_statistics": _g(
        "the user wants CPU / media load / call counts for one Conferencing Node.",
        "the user wants a yes/no health answer (get_node_status).",
    ),
    "list_location_status": _g(
        "the user asks about live state per data centre / region.",
        "the user wants location configuration (list_locations).",
        examples=[{}, {"name_contains": "EU"}],
    ),
    "get_location_status": _g(
        "the user names one location and asks about its live state.",
        "the user wants load numbers (get_location_statistics).",
    ),
    "get_location_statistics": _g(
        "the user wants call counts / port usage for one location.",
        "the user wants a health summary (get_location_status).",
    ),
    "list_management_node_status": _g(
        "the user asks whether the Management Node itself is healthy.",
        "the question is about Conferencing Nodes (list_node_status).",
    ),
    "get_management_node_status": _g(
        "the user asks for one Management Node's live status by id.",
        "the user wants the list (list_management_node_status).",
    ),
    "list_registration_aliases": _g(
        "the user asks which aliases are currently registered to the platform.",
        "the user wants VMR dial aliases (list_aliases) or device records (list_devices).",
        examples=[{"alias_contains": "@example.com"}],
    ),
    "get_registration_alias": _g(
        "the user wants one currently registered alias by id.",
        "the user wants the list (list_registration_aliases).",
    ),
    "list_conference_shards": _g(
        "the user asks how a live conference is spread across Conferencing Nodes.",
        "the user just wants the conference list (list_active_conferences).",
        examples=[{"conference_name": "All Hands"}],
    ),
    "get_conference_shard": _g(
        "the user wants one shard record by id.",
        "the user wants the list (list_conference_shards).",
    ),
    "list_backplanes": _g(
        "the user asks about inter-node media connections for live conferences.",
        "the call has ended (list_backplane_history).",
    ),
    "get_backplane": _g(
        "the user wants one live backplane by id.",
        "the user wants its media statistics (get_backplane_media_streams).",
    ),
    "get_backplane_media_streams": _g(
        "the user wants per-stream statistics for one live backplane.",
        "the backplane is historical (get_backplane_history_media_streams).",
    ),
    "list_conference_sync_status": _g(
        "the user asks about the state of conference synchronization.",
        "the user asks about LDAP user sync (list_ldap_sources).",
    ),
    "get_conference_sync_status": _g(
        "the user wants one conference sync entry by id.",
        "the user wants the list (list_conference_sync_status).",
    ),
    "list_cloud_nodes": _g(
        "the user asks which cloud overflow (bursting) nodes exist or are running.",
        "the user asks about permanent Conferencing Nodes (list_node_status).",
    ),
    "get_cloud_node": _g(
        "the user wants one cloud overflow node by id.",
        "the user wants the list (list_cloud_nodes).",
    ),
    "list_cloud_overflow_locations": _g(
        "the user asks which locations can burst into the cloud.",
        "the user asks which locations are being monitored for bursting "
        "(list_cloud_monitored_locations).",
    ),
    "get_cloud_overflow_location": _g(
        "the user wants one cloud overflow location by id.",
        "the user wants the list (list_cloud_overflow_locations).",
    ),
    "list_cloud_monitored_locations": _g(
        "the user asks which locations are monitored to trigger cloud bursting.",
        "the user asks where overflow nodes are placed (list_cloud_overflow_locations).",
    ),
    "get_cloud_monitored_location": _g(
        "the user wants one cloud monitored location by id.",
        "the user wants the list (list_cloud_monitored_locations).",
    ),
    "list_exchange_scheduler_status": _g(
        "the user asks about the Secure Scheduler for Exchange integration state.",
        "the question is about One-Touch Join (list_mjx_endpoint_status).",
    ),
    "get_exchange_scheduler_status": _g(
        "the user wants one Exchange scheduler entry by id.",
        "the user wants the list (list_exchange_scheduler_status).",
    ),
    "list_mjx_endpoint_status": _g(
        "the user asks whether One-Touch Join room endpoints are connected.",
        "the user asks about MJX meetings (list_mjx_meeting_status) or MJX configuration "
        "(list_resources resource='mjx_endpoint').",
        examples=[{}, {"name_contains": "boardroom"}],
    ),
    "get_mjx_endpoint_status": _g(
        "the user wants one MJX endpoint's live status by id.",
        "the user wants the list (list_mjx_endpoint_status).",
    ),
    "list_mjx_meeting_status": _g(
        "the user asks which upcoming meetings One-Touch Join has detected.",
        "the user asks about endpoints (list_mjx_endpoint_status).",
    ),
    "get_mjx_meeting_status": _g(
        "the user wants one MJX meeting by id.",
        "the user wants the list (list_mjx_meeting_status).",
    ),
    "list_teams_node_status": _g(
        "the user asks whether Teams Connector nodes are healthy.",
        "the user asks about Teams calls (list_teams_node_call_status).",
    ),
    "get_teams_node_status": _g(
        "the user wants one Teams Connector node by id.",
        "the user wants the list (list_teams_node_status).",
    ),
    "list_teams_node_call_status": _g(
        "the user asks about calls currently going through Teams Connectors.",
        "the user asks about the connector nodes themselves (list_teams_node_status).",
    ),
    "get_teams_node_call_status": _g(
        "the user wants one Teams Connector call by id.",
        "the user wants the list (list_teams_node_call_status).",
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
    "list_alarm_history": _g(
        "the user asks what alarms were raised in the past.",
        "the user asks what is alarming now (list_alarms).",
        examples=[{"start_time": _TS, "end_time": _TS2, "level": "critical"}],
    ),
    "get_alarm_history": _g(
        "the user wants one past alarm by id.",
        "the user wants the list (list_alarm_history).",
    ),
    "list_backplane_history": _g(
        "the user asks about inter-node connections for past conferences.",
        "the conference is live (list_backplanes).",
    ),
    "get_backplane_history": _g(
        "the user wants one past backplane by id.",
        "the user wants its stream statistics (get_backplane_history_media_streams).",
    ),
    "get_backplane_history_media_streams": _g(
        "the user wants per-stream statistics for one past backplane.",
        "the backplane is live (get_backplane_media_streams).",
    ),
    "list_registration_history": _g(
        "the user asks when an endpoint registered or unregistered in the past.",
        "the user asks what is registered now (list_registrations).",
        examples=[{"alias_contains": "boardroom", "limit": 50}],
    ),
    "get_registration_history": _g(
        "the user wants one past registration event by id.",
        "the user wants the list (list_registration_history).",
    ),
    "list_node_event_history": _g(
        "the user asks when Conferencing Nodes went up/down or changed state.",
        "the user asks about node status now (list_node_status).",
        examples=[{"start_time": _TS, "end_time": _TS2}],
    ),
    "get_node_event_history": _g(
        "the user wants one node event by id.",
        "the user wants the list (list_node_event_history).",
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
    "send_conference_email": _g(
        "the user wants the VMR owner emailed their room details; `vmr_id` is the VMR's "
        "integer configuration id.",
        "the recipient is a device owner (send_device_email).",
        docs=COMMAND_API,
    ),
    "send_device_email": _g(
        "the user wants a device owner emailed their provisioning details.",
        "the recipient is a VMR owner (send_conference_email).",
        docs=COMMAND_API,
    ),
    # ── Command: platform lifecycle (gated by PEXIP_ALLOW_PLATFORM_TOOLS) ────
    "backup_create": _g(
        "the user explicitly asks for a platform backup to be taken now.",
        "the user wants to see existing backups (list_resources resource='system_backup').",
        docs=COMMAND_API,
    ),
    "backup_restore": _g(
        "the user explicitly asks to restore a specific backup and has confirmed they "
        "understand current state is replaced.",
        "anything else; this replaces the whole platform configuration.",
        docs=COMMAND_API,
    ),
    "certificates_import": _g(
        "the user explicitly asks to import TLS/CA certificates and supplies the payload.",
        "the user wants to see installed certificates (list_resources "
        "resource='tls_certificate' or 'ca_certificate').",
        docs=COMMAND_API,
    ),
    "start_cloud_node": _g(
        "the user explicitly asks to start a cloud overflow (bursting) node now.",
        "the user asks which cloud nodes exist (list_cloud_nodes).",
        docs=COMMAND_API,
    ),
    "take_snapshot": _g(
        "Pexip support asked for a diagnostic snapshot, or the user explicitly requests one.",
        "the user wants a backup (backup_create).",
        docs=COMMAND_API,
    ),
    "platform_upgrade": _g(
        "the user explicitly asks to start a platform upgrade and the software bundle is "
        "already uploaded.",
        "anything else; this initiates a software upgrade of the whole deployment.",
        docs=COMMAND_API,
    ),
    "upload_software_bundle": _g(
        "the user explicitly asks to upload an upgrade bundle and supplies the payload.",
        "the user wants to see uploaded bundles (list_resources resource='software_bundle').",
        docs=COMMAND_API,
    ),
}


_BARE_NAME_RE = re.compile(
    r"(?<![\w.])(" + "|".join(sorted(map(re.escape, GUIDANCE), key=len, reverse=True)) + r")\b"
)


def _prefix_tool_names(text: str, prefix: str) -> str:
    """Rewrite bare sibling tool names (list_vmrs) to their published form (pexip_list_vmrs)."""
    if not prefix:
        return text
    return _BARE_NAME_RE.sub(
        lambda m: m.group(1) if m.group(0).startswith(prefix) else prefix + m.group(1), text
    )


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
