"""Workflow tool: one call that answers "is the platform OK right now?".

The most common operator question used to take four tool calls (alarms,
licensing, node status, active conferences). This composes them and returns a
compact summary with an overall verdict, so the agent can answer directly and
only drill down when something looks wrong.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from typing import Any, TypedDict

from mcp.server.fastmcp import Context

from pexip_mcp.mcp_app import mcp
from pexip_mcp.tools._helpers import get_client, read


class AlarmSummary(TypedDict):
    total: int
    by_level: dict[str, int]
    top: list[dict[str, Any]]


class NodeSummary(TypedDict):
    total: int
    by_sync_status: dict[str, int]
    in_maintenance: int
    max_media_load: float | None
    busiest: list[dict[str, Any]]


class PlatformHealth(TypedDict):
    verdict: str
    reasons: list[str]
    alarms: AlarmSummary
    licensing: list[dict[str, Any]]
    nodes: NodeSummary
    active_conferences: int | None
    active_participants: int | None


_LEVEL_RANK = {"critical": 0, "error": 1, "warning": 2, "info": 3}


def _severity(alarm: dict[str, Any]) -> int:
    return _LEVEL_RANK.get(str(alarm.get("level", "")).lower(), 9)


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@mcp.tool(annotations=read("Get platform health summary"))
async def get_platform_health(ctx: Context) -> PlatformHealth:
    """Summarize platform health in one call: alarms, licensing, node load, live usage.

    Returns a verdict ("ok", "degraded" or "critical") with the reasons, the
    active alarms grouped by level (plus the first few), licence usage, a
    Conferencing Node summary (sync status, maintenance, busiest nodes) and the
    current number of active conferences and participants. Drill into
    pexip_list_alarms, pexip_list_node_status or pexip_get_licensing_status when a
    reason needs detail.
    """
    client = get_client(ctx)
    alarm_page, licensing_page, node_page, conferences, participants = await asyncio.gather(
        client.list("alarm", api="status", limit=1000),
        client.list("licensing", api="status", limit=1000),
        client.list("worker_vm", api="status", limit=1000),
        client.list("conference", api="status", limit=1),
        client.list("participant", api="status", limit=1),
    )
    alarms = alarm_page.get("objects", [])
    licensing = licensing_page.get("objects", [])
    nodes = node_page.get("objects", [])

    reasons: list[str] = []
    by_level = Counter(str(a.get("level", "unknown")).lower() for a in alarms)
    if by_level.get("critical"):
        reasons.append(f"{by_level['critical']} critical alarm(s)")
    elif by_level.get("error") or by_level.get("warning"):
        reasons.append(
            f"{by_level.get('error', 0)} error / {by_level.get('warning', 0)} warning alarm(s)"
        )

    sync = Counter(str(n.get("sync_status", "unknown")).lower() for n in nodes)
    # Only a reported, non-OK status counts; a record without the field is "unknown".
    unsynced = sum(
        c for s, c in sync.items() if s not in ("synchronized", "synced", "ok", "unknown")
    )
    if nodes and unsynced:
        reasons.append(f"{unsynced} Conferencing Node(s) not synchronized")
    maintenance = sum(1 for n in nodes if n.get("maintenance_mode") in (True, "true", "True"))
    if maintenance:
        reasons.append(f"{maintenance} node(s) in maintenance mode")
    loads = [(_num(n.get("media_load")), n) for n in nodes]
    loads = [(load, n) for load, n in loads if load is not None]
    max_load = max((load for load, _ in loads), default=None)
    if max_load is not None and max_load >= 90:
        reasons.append(f"a node is at {max_load:.0f}% media load")

    # Pexip reports licence usage as <kind>_count / <kind>_total pairs
    # (port_count/port_total, audio_count/audio_total, vmr_count/vmr_total, ...).
    for lic in licensing:
        for key, raw_total in lic.items():
            if not str(key).endswith("_total"):
                continue
            kind = str(key)[: -len("_total")]
            used = _num(lic.get(f"{kind}_count", lic.get(f"{kind}_used")))
            total = _num(raw_total)
            if used is not None and total:
                pct = used / total * 100
                if pct >= 90:
                    reasons.append(f"{kind} licences at {pct:.0f}% of entitlement")

    if by_level.get("critical") or unsynced:
        verdict = "critical"
    elif reasons:
        verdict = "degraded"
    else:
        verdict = "ok"

    busiest = sorted(loads, key=lambda t: -t[0])[:5]
    return {
        "verdict": verdict,
        "reasons": reasons,
        "alarms": {
            "total": len(alarms),
            "by_level": dict(by_level),
            "top": [
                {
                    "name": a.get("name"),
                    "level": a.get("level"),
                    "node": a.get("node"),
                    "time_raised": a.get("time_raised"),
                }
                for a in sorted(alarms, key=_severity)[:5]
            ],
        },
        "licensing": licensing,
        "nodes": {
            "total": len(nodes),
            "by_sync_status": dict(sync),
            "in_maintenance": maintenance,
            "max_media_load": max_load,
            "busiest": [
                {
                    "name": n.get("name"),
                    "media_load": load,
                    "system_location": n.get("system_location"),
                }
                for load, n in busiest
            ],
        },
        "active_conferences": (conferences.get("meta") or {}).get("total_count"),
        "active_participants": (participants.get("meta") or {}).get("total_count"),
    }
