"""pexip_get_platform_health: composes four status reads into one verdict."""

from __future__ import annotations

import httpx
import respx

from pexip_mcp.tools import health

from .conftest import PEXIP_HOST

STATUS = f"https://{PEXIP_HOST}/api/admin/status/v1"


def _page(objects, total=None):
    return httpx.Response(
        200,
        json={
            "objects": objects,
            "meta": {"total_count": total if total is not None else len(objects)},
        },
    )


def _mock(alarms=(), licensing=(), nodes=(), conferences=0, participants=0):
    respx.get(f"{STATUS}/alarm/").mock(return_value=_page(list(alarms)))
    respx.get(f"{STATUS}/licensing/").mock(return_value=_page(list(licensing)))
    respx.get(f"{STATUS}/worker_vm/").mock(return_value=_page(list(nodes)))
    respx.get(f"{STATUS}/conference/").mock(return_value=_page([], total=conferences))
    respx.get(f"{STATUS}/participant/").mock(return_value=_page([], total=participants))


@respx.mock
async def test_healthy_platform_is_ok(ctx):
    _mock(
        nodes=[
            {
                "name": "n1",
                "sync_status": "synchronized",
                "media_load": "12",
                "maintenance_mode": False,
            }
        ],
        licensing=[{"port_count": 4, "port_total": 100, "audio_count": 1, "audio_total": 50}],
        conferences=3,
        participants=11,
    )
    out = await health.get_platform_health(ctx)
    assert out["verdict"] == "ok" and out["reasons"] == []
    assert out["active_conferences"] == 3 and out["active_participants"] == 11
    assert out["nodes"]["busiest"][0]["name"] == "n1"
    assert out["alarms"]["total"] == 0


@respx.mock
async def test_warnings_and_high_load_are_degraded(ctx):
    _mock(
        alarms=[{"name": "disk", "level": "warning", "node": "n1", "time_raised": "t"}],
        nodes=[{"name": "n1", "sync_status": "synchronized", "media_load": "95"}],
        licensing=[{"port_count": 95, "port_total": 100}],
    )
    out = await health.get_platform_health(ctx)
    assert out["verdict"] == "degraded"
    assert any("warning" in r for r in out["reasons"])
    assert any("95% media load" in r for r in out["reasons"])
    assert any("port licences at 95% of entitlement" in r for r in out["reasons"])
    assert out["alarms"]["by_level"] == {"warning": 1}


@respx.mock
async def test_critical_alarm_or_unsynced_node_is_critical(ctx):
    _mock(
        alarms=[{"name": "boom", "level": "critical"}],
        nodes=[{"name": "n1", "sync_status": "not_synchronized", "media_load": "1"}],
    )
    out = await health.get_platform_health(ctx)
    assert out["verdict"] == "critical"
    assert "1 critical alarm(s)" in out["reasons"]
    assert "1 Conferencing Node(s) not synchronized" in out["reasons"]
    assert out["nodes"]["by_sync_status"] == {"not_synchronized": 1}


@respx.mock
async def test_tolerates_missing_numeric_fields(ctx):
    _mock(nodes=[{"name": "n1"}], licensing=[{"name": "x", "port_total": None}])
    out = await health.get_platform_health(ctx)
    assert out["verdict"] == "ok"
    assert out["nodes"]["max_media_load"] is None


@respx.mock
async def test_top_alarms_are_ordered_by_severity(ctx):
    _mock(
        alarms=[{"name": f"w{i}", "level": "warning"} for i in range(6)]
        + [{"name": "boom", "level": "critical"}],
    )
    out = await health.get_platform_health(ctx)
    assert out["alarms"]["top"][0]["name"] == "boom"
    assert len(out["alarms"]["top"]) == 5
