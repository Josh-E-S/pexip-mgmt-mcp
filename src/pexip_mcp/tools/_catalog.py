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
                }
            ),
        ),
        Toolset(
            "directory",
            "End users and device records (who may register).",
            frozenset(
                {
                    "create_device",
                    "create_end_user",
                    "delete_device",
                    "delete_end_user",
                    "get_device",
                    "get_end_user",
                    "list_devices",
                    "list_end_users",
                    "update_device",
                    "update_end_user",
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
            "Generic CRUD over every configuration resource without a dedicated tool "
            "(LDAP sources, IVR themes, global settings, proxies, certificates, ...).",
            frozenset(
                {
                    "list_resources",
                    "get_resource",
                    "create_resource",
                    "update_resource",
                    "delete_resource",
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
                }
            ),
        ),
        Toolset(
            "health",
            "Alarms, licensing, node and location status, registrations, integrations status.",
            frozenset(
                {
                    "get_licensing_status",
                    "get_node_status",
                    "get_status",
                    "list_alarms",
                    "list_node_status",
                    "list_registrations",
                    "list_status",
                }
            ),
        ),
        Toolset(
            "history",
            "Completed calls (CDRs), reports, and past alarms / registrations / node events.",
            frozenset(
                {
                    "get_history",
                    "get_history_conference",
                    "get_history_participant",
                    "list_history",
                    "list_history_conferences",
                    "list_history_participants",
                    "summarize_calls",
                }
            ),
        ),
        Toolset(
            "platform",
            "run_platform_command (gated by PEXIP_ALLOW_PLATFORM_TOOLS), provisioning emails "
            "and LDAP template sync.",
            frozenset(
                {
                    "run_platform_command",
                    "send_provisioning_email",
                    "sync_conference_ldap",
                }
            ),
            default=False,
        ),
    )
}

TOOLSET_OF: dict[str, str] = {tool: ts.name for ts in TOOLSETS.values() for tool in ts.tools}

# Platform-lifecycle commands removed unless PEXIP_ALLOW_PLATFORM_TOOLS=true,
# even with writes enabled and the platform toolset selected. Misuse of any of
# these can replace or compromise the whole deployment. Defined here, next to
# the toolset they belong to, so there is one list to maintain.
PLATFORM_GATED: frozenset[str] = frozenset({"run_platform_command"})
assert PLATFORM_GATED <= TOOLSETS["platform"].tools
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
            None,
            None,
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
        _s("worker_vm/{id}/statistics", "per-node load statistics", (), None, None),
        _s(
            "system_location",
            "location status",
            ("name",),
            None,
            None,
            ("datacentre", "region"),
        ),
        _s(
            "system_location/{id}/statistics",
            "per-location statistics",
            (),
            None,
            None,
        ),
        _s(
            "management_vm",
            "Management Node status",
            (),
            None,
            None,
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
            None,
            None,
        ),
        _s("backplane", "inter-node media connections", (), None, None),
        _s(
            "backplane/{id}/media_stream",
            "backplane media streams",
            (),
            None,
            None,
        ),
        _s(
            "conference_sync",
            "conference synchronization",
            (),
            None,
            None,
        ),
        _s(
            "cloud_node",
            "cloud overflow (bursting) nodes",
            (),
            None,
            None,
            ("burst", "overflow", "aws", "azure", "gcp"),
        ),
        _s(
            "cloud_overflow_location",
            "cloud overflow locations",
            (),
            None,
            None,
        ),
        _s(
            "cloud_monitored_location",
            "locations monitored for bursting",
            (),
            None,
            None,
        ),
        _s(
            "exchange_scheduler",
            "Secure Scheduler for Exchange",
            (),
            None,
            None,
            ("outlook",),
        ),
        _s(
            "mjx_endpoint",
            "One-Touch Join endpoints",
            ("name",),
            None,
            None,
            ("otj", "room system"),
        ),
        _s(
            "mjx_meeting",
            "One-Touch Join detected meetings",
            (),
            None,
            None,
        ),
        _s(
            "teamsnode",
            "Teams Connector nodes",
            (),
            None,
            None,
            ("microsoft", "cvi"),
        ),
        _s(
            "teamsnode_call",
            "Teams Connector calls",
            (),
            None,
            None,
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
            None,
            None,
        ),
        _h(
            "backplane",
            "past inter-node connections",
            (),
            None,
            None,
        ),
        _h(
            "backplane/{id}/media_stream",
            "past backplane media streams",
            (),
            None,
            None,
        ),
        _h(
            "registration_alias",
            "registration / unregistration events",
            ("alias",),
            None,
            None,
        ),
        _h(
            "workervm_status_event",
            "Conferencing Node up/down events",
            ("start_time", "end_time"),
            None,
            None,
        ),
    )
}
