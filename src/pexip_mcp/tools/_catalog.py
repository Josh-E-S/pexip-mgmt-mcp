"""The catalog: toolsets, and the status/history resource registries.

This is the declarative half of the tool surface. Tool modules still implement
behaviour; this module says how the surface is grouped and discovered:

  TOOLSETS        name -> which bare tool names belong to it, plus a one-line
                  description and whether it is on by default. Selection is
                  PEXIP_TOOLSETS / PEXIP_TOOLS / PEXIP_DENY_TOOLS (see mcp_app).
  STATUS_REGISTRY / HISTORY_REGISTRY
                  every Status / History API resource the server knows, with a
                  label, filters and the dedicated tool (if any). Phase 4's
                  generic pexip_list_status / pexip_list_history tools are
                  driven by these; pexip_describe_resources reads them today.

Keep the bare (unprefixed) function names here; mcp_app applies the prefix.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Toolset:
    name: str
    description: str
    tools: frozenset[str]
    default: bool = True


TOOLSETS: dict[str, Toolset] = {
    ts.name: ts
    for ts in (
        Toolset(
            "core",
            "Discovery and schema: always on.",
            frozenset({"describe_resources", "get_resource_schema", "get_platform_health"}),
        ),
        Toolset(
            "rooms",
            "Virtual Meeting Rooms, their dial aliases and automatic participants.",
            frozenset(
                {
                    "list_vmrs",
                    "get_vmr",
                    "create_vmr",
                    "update_vmr",
                    "delete_vmr",
                    "list_aliases",
                    "add_vmr_alias",
                    "delete_alias",
                    "list_automatic_participants",
                    "add_automatic_participant",
                    "delete_automatic_participant",
                    "list_ivr_themes",
                    "get_ivr_theme",
                }
            ),
        ),
        Toolset(
            "directory",
            "End users and registered devices.",
            frozenset(
                {
                    "list_end_users",
                    "get_end_user",
                    "create_end_user",
                    "update_end_user",
                    "delete_end_user",
                    "list_devices",
                    "get_device",
                    "create_device",
                    "update_device",
                    "delete_device",
                    "list_registrations",
                }
            ),
        ),
        Toolset(
            "dialplan",
            "Gateway routing rules, locations and Conferencing Node configuration.",
            frozenset(
                {
                    "list_gateway_rules",
                    "get_gateway_rule",
                    "create_gateway_rule",
                    "update_gateway_rule",
                    "delete_gateway_rule",
                    "list_locations",
                    "get_location",
                    "list_conferencing_nodes",
                    "get_conferencing_node",
                }
            ),
            default=False,
        ),
        Toolset(
            "config",
            "Generic CRUD over every other configuration resource, LDAP sources and global settings.",
            frozenset(
                {
                    "list_resources",
                    "get_resource",
                    "create_resource",
                    "update_resource",
                    "delete_resource",
                    "list_ldap_sources",
                    "get_ldap_source",
                    "create_ldap_source",
                    "update_ldap_source",
                    "delete_ldap_source",
                    "get_global_settings",
                    "update_global_settings",
                }
            ),
        ),
        Toolset(
            "live",
            "What is happening now and live call control.",
            frozenset(
                {
                    "list_active_conferences",
                    "list_active_participants",
                    "get_active_participant",
                    "get_participant_quality",
                    "dial_participant",
                    "disconnect_participant",
                    "mute_participant",
                    "unmute_participant",
                    "set_participant_role",
                    "transfer_participant",
                    "unlock_participant",
                    "disconnect_conference",
                    "lock_conference",
                    "unlock_conference",
                    "mute_guests",
                    "unmute_guests",
                    "set_conference_layout",
                    "list_conference_shards",
                    "get_conference_shard",
                }
            ),
        ),
        Toolset(
            "health",
            "Alarms, licensing, node and location status, registrations, integrations status.",
            frozenset(
                {
                    "list_alarms",
                    "get_licensing_status",
                    "list_node_status",
                    "get_node_status",
                    "get_node_statistics",
                    "list_location_status",
                    "get_location_status",
                    "get_location_statistics",
                    "list_management_node_status",
                    "get_management_node_status",
                    "list_registration_aliases",
                    "get_registration_alias",
                    "list_backplanes",
                    "get_backplane",
                    "get_backplane_media_streams",
                    "list_conference_sync_status",
                    "get_conference_sync_status",
                    "list_cloud_nodes",
                    "get_cloud_node",
                    "list_cloud_overflow_locations",
                    "get_cloud_overflow_location",
                    "list_cloud_monitored_locations",
                    "get_cloud_monitored_location",
                    "list_exchange_scheduler_status",
                    "get_exchange_scheduler_status",
                    "list_mjx_endpoint_status",
                    "get_mjx_endpoint_status",
                    "list_mjx_meeting_status",
                    "get_mjx_meeting_status",
                    "list_teams_node_status",
                    "get_teams_node_status",
                    "list_teams_node_call_status",
                    "get_teams_node_call_status",
                }
            ),
        ),
        Toolset(
            "history",
            "Completed calls (CDRs), reports, and past alarms / registrations / node events.",
            frozenset(
                {
                    "summarize_calls",
                    "list_history_conferences",
                    "get_history_conference",
                    "list_history_participants",
                    "get_history_participant",
                    "list_alarm_history",
                    "get_alarm_history",
                    "list_backplane_history",
                    "get_backplane_history",
                    "get_backplane_history_media_streams",
                    "list_registration_history",
                    "get_registration_history",
                    "list_node_event_history",
                    "get_node_event_history",
                }
            ),
        ),
        Toolset(
            "platform",
            "Platform lifecycle commands (also gated by PEXIP_ALLOW_PLATFORM_TOOLS) and "
            "provisioning / sync commands.",
            frozenset(
                {
                    "backup_create",
                    "backup_restore",
                    "certificates_import",
                    "start_cloud_node",
                    "take_snapshot",
                    "platform_upgrade",
                    "upload_software_bundle",
                    "sync_conference_ldap",
                    "send_conference_email",
                    "send_device_email",
                }
            ),
            default=False,
        ),
    )
}

TOOLSET_OF: dict[str, str] = {tool: ts.name for ts in TOOLSETS.values() for tool in ts.tools}
DEFAULT_TOOLSETS: frozenset[str] = frozenset(ts.name for ts in TOOLSETS.values() if ts.default)


def resolve_toolsets(spec: str | None) -> set[str]:
    """Turn a PEXIP_TOOLSETS value into a set of toolset names.

    "" / None / "default" -> the default set; "all" -> every toolset; a comma
    list may include "default" to extend it. Unknown names raise ValueError so a
    typo fails at startup instead of silently hiding tools. "core" is always on.
    """
    if not spec or spec.strip().lower() == "default":
        chosen = set(DEFAULT_TOOLSETS)
    else:
        chosen = set()
        for raw in spec.split(","):
            name = raw.strip().lower()
            if not name:
                continue
            if name == "all":
                chosen |= set(TOOLSETS)
            elif name == "default":
                chosen |= set(DEFAULT_TOOLSETS)
            elif name in TOOLSETS:
                chosen.add(name)
            else:
                raise ValueError(
                    f"Unknown toolset {name!r} in PEXIP_TOOLSETS. "
                    f"Known: {', '.join(sorted(TOOLSETS))}, plus 'default' and 'all'."
                )
    chosen.add("core")
    return chosen


# ── Status / History resource registries ─────────────────────────────────────


@dataclass(frozen=True)
class ResourceSpec:
    """One API resource as the discovery tool (and phase 4's generic tools) see it."""

    name: str
    label: str
    api: str  # "status" | "history"
    filters: tuple[str, ...] = ()
    dedicated_list_tool: str | None = None
    dedicated_get_tool: str | None = None
    keywords: tuple[str, ...] = field(default_factory=tuple)


def _s(name, label, filters=(), lt=None, gt=None, kw=()):
    return ResourceSpec(name, label, "status", tuple(filters), lt, gt, tuple(kw))


def _h(name, label, filters=(), lt=None, gt=None, kw=()):
    return ResourceSpec(name, label, "history", tuple(filters), lt, gt, tuple(kw))


STATUS_REGISTRY: dict[str, ResourceSpec] = {
    r.name: r
    for r in (
        _s(
            "conference",
            "live conference instances",
            ("name", "service_type", "tag"),
            "list_active_conferences",
            None,
            ("meeting", "running", "now"),
        ),
        _s(
            "participant",
            "connected participants (call legs)",
            ("conference", "role", "protocol", "is_muted", "display_name"),
            "list_active_participants",
            "get_active_participant",
            ("who is in", "attendee"),
        ),
        _s(
            "participant_media_stream",
            "per-participant media streams (quality)",
            ("participant",),
            None,
            "get_participant_quality",
            ("bitrate", "packet loss", "jitter"),
        ),
        _s(
            "conference_shard",
            "conference instances per Conferencing Node",
            ("conference",),
            "list_conference_shards",
            "get_conference_shard",
        ),
        _s("alarm", "active alarms", ("level", "node"), "list_alarms", None, ("alert", "warning")),
        _s(
            "licensing",
            "concurrent port usage vs entitlement",
            (),
            None,
            "get_licensing_status",
            ("licence", "license", "ports"),
        ),
        _s(
            "worker_vm",
            "Conferencing Node status and load",
            ("system_location", "name"),
            "list_node_status",
            "get_node_status",
            ("node", "load", "capacity"),
        ),
        _s(
            "worker_vm/{id}/statistics", "per-node load statistics", (), None, "get_node_statistics"
        ),
        _s(
            "system_location",
            "location status",
            ("name",),
            "list_location_status",
            "get_location_status",
            ("datacentre", "region"),
        ),
        _s(
            "system_location/{id}/statistics",
            "per-location statistics",
            (),
            None,
            "get_location_statistics",
        ),
        _s(
            "management_vm",
            "Management Node status",
            (),
            "list_management_node_status",
            "get_management_node_status",
        ),
        _s(
            "registration",
            "registered endpoints",
            ("alias", "protocol"),
            "list_registrations",
            None,
            ("endpoint", "registered", "online"),
        ),
        _s(
            "registration_alias",
            "registered aliases",
            ("alias",),
            "list_registration_aliases",
            "get_registration_alias",
        ),
        _s("backplane", "inter-node media connections", (), "list_backplanes", "get_backplane"),
        _s(
            "backplane/{id}/media_stream",
            "backplane media streams",
            (),
            None,
            "get_backplane_media_streams",
        ),
        _s(
            "conference_sync",
            "conference synchronization",
            (),
            "list_conference_sync_status",
            "get_conference_sync_status",
        ),
        _s(
            "cloud_node",
            "cloud overflow (bursting) nodes",
            (),
            "list_cloud_nodes",
            "get_cloud_node",
            ("burst", "overflow", "aws", "azure", "gcp"),
        ),
        _s(
            "cloud_overflow_location",
            "cloud overflow locations",
            (),
            "list_cloud_overflow_locations",
            "get_cloud_overflow_location",
        ),
        _s(
            "cloud_monitored_location",
            "locations monitored for bursting",
            (),
            "list_cloud_monitored_locations",
            "get_cloud_monitored_location",
        ),
        _s(
            "exchange_scheduler",
            "Secure Scheduler for Exchange",
            (),
            "list_exchange_scheduler_status",
            "get_exchange_scheduler_status",
            ("outlook",),
        ),
        _s(
            "mjx_endpoint",
            "One-Touch Join endpoints",
            ("name",),
            "list_mjx_endpoint_status",
            "get_mjx_endpoint_status",
            ("otj", "room system"),
        ),
        _s(
            "mjx_meeting",
            "One-Touch Join detected meetings",
            (),
            "list_mjx_meeting_status",
            "get_mjx_meeting_status",
        ),
        _s(
            "teamsnode",
            "Teams Connector nodes",
            (),
            "list_teams_node_status",
            "get_teams_node_status",
            ("microsoft", "cvi"),
        ),
        _s(
            "teamsnode_call",
            "Teams Connector calls",
            (),
            "list_teams_node_call_status",
            "get_teams_node_call_status",
        ),
    )
}

HISTORY_REGISTRY: dict[str, ResourceSpec] = {
    r.name: r
    for r in (
        _h(
            "conference",
            "completed conference instances",
            ("start_time", "end_time", "name", "service_type", "tag"),
            "list_history_conferences",
            "get_history_conference",
            ("past meetings", "when"),
        ),
        _h(
            "participant",
            "completed participant call legs (CDRs)",
            (
                "start_time",
                "end_time",
                "conference_name",
                "call_direction",
                "call_quality",
                "protocol",
                "disconnect_reason",
                "location",
                "service_tag",
            ),
            "list_history_participants",
            "get_history_participant",
            ("cdr", "call records", "billing"),
        ),
        _h(
            "alarm",
            "past alarms",
            ("start_time", "end_time", "level"),
            "list_alarm_history",
            "get_alarm_history",
        ),
        _h(
            "backplane",
            "past inter-node connections",
            (),
            "list_backplane_history",
            "get_backplane_history",
        ),
        _h(
            "backplane/{id}/media_stream",
            "past backplane media streams",
            (),
            None,
            "get_backplane_history_media_streams",
        ),
        _h(
            "registration_alias",
            "registration / unregistration events",
            ("alias",),
            "list_registration_history",
            "get_registration_history",
        ),
        _h(
            "workervm_status_event",
            "Conferencing Node up/down events",
            ("start_time", "end_time"),
            "list_node_event_history",
            "get_node_event_history",
        ),
    )
}
