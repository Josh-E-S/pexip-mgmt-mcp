from __future__ import annotations

import httpx
import respx

from pexip_mcp.tools import status

from .conftest import BASE_URL, STATUS_URL, fk


def _empty_page():
    return {
        "meta": {"total_count": 0, "limit": 20, "offset": 0, "next": None, "previous": None},
        "objects": [],
    }


@respx.mock
async def test_list_active_conferences_filters(ctx):
    route = respx.get(f"{STATUS_URL}/conference/").mock(
        return_value=httpx.Response(200, json=_empty_page())
    )

    await status.list_active_conferences(ctx, service_type="conference", tag="exec")

    params = route.calls.last.request.url.params
    assert params["service_type"] == "conference"
    assert params["tag"] == "exec"


@respx.mock
async def test_list_active_participants_by_conference_name(ctx):
    route = respx.get(f"{STATUS_URL}/participant/").mock(
        return_value=httpx.Response(200, json=_empty_page())
    )

    await status.list_active_participants(ctx, conference_name="Standup", role="chair")

    params = route.calls.last.request.url.params
    assert params["conference"] == "Standup"
    assert params["role"] == "chair"


@respx.mock
async def test_list_active_participants_is_muted_serializes_capitalized(ctx):
    route = respx.get(f"{STATUS_URL}/participant/").mock(
        return_value=httpx.Response(200, json=_empty_page())
    )

    await status.list_active_participants(ctx, is_muted=True)

    assert route.calls.last.request.url.params["is_muted"] == "True"


@respx.mock
async def test_get_active_participant_uses_status_path(ctx):
    pid = "00000000-0000-0000-0000-00000000abc1"
    route = respx.get(f"{STATUS_URL}/participant/{pid}/").mock(
        return_value=httpx.Response(200, json={"id": pid, "display_name": "Alice"})
    )

    result = await status.get_active_participant(ctx, pid)

    assert route.called
    assert result["display_name"] == "Alice"


@respx.mock
async def test_get_active_participant_resolves_display_name(ctx):
    """A display name (not a UUID) is resolved via the participant list."""
    pid = "00000000-0000-0000-0000-00000000abc1"
    respx.get(f"{STATUS_URL}/participant/").mock(
        return_value=httpx.Response(
            200,
            json={
                "meta": {"total_count": 1, "limit": 200, "offset": 0,
                         "next": None, "previous": None},
                "objects": [{"id": pid, "display_name": "Alice"}],
            },
        )
    )
    detail = respx.get(f"{STATUS_URL}/participant/{pid}/").mock(
        return_value=httpx.Response(200, json={"id": pid, "display_name": "Alice"})
    )

    result = await status.get_active_participant(ctx, "Alice")

    assert detail.called
    assert result["id"] == pid


@respx.mock
async def test_list_alarms_resolves_node_name_to_fk_uri(ctx):
    respx.get(f"{BASE_URL}/worker_vm/").mock(
        return_value=httpx.Response(
            200,
            json={
                "meta": {"total_count": 1, "limit": 2, "offset": 0,
                         "next": None, "previous": None},
                "objects": [
                    {"id": 12, "name": "lon-conf-01", "resource_uri": fk("worker_vm", 12)}
                ],
            },
        )
    )
    list_route = respx.get(f"{STATUS_URL}/alarm/").mock(
        return_value=httpx.Response(200, json=_empty_page())
    )

    await status.list_alarms(ctx, level="error", node_name="lon-conf-01")

    params = list_route.calls.last.request.url.params
    assert params["level"] == "error"
    assert params["node"] == fk("worker_vm", 12)


@respx.mock
async def test_list_node_status_filters_by_location_uri(ctx):
    respx.get(f"{BASE_URL}/system_location/").mock(
        return_value=httpx.Response(
            200,
            json={
                "meta": {"total_count": 1, "limit": 2, "offset": 0,
                         "next": None, "previous": None},
                "objects": [
                    {"id": 4, "name": "London", "resource_uri": fk("system_location", 4)}
                ],
            },
        )
    )
    list_route = respx.get(f"{STATUS_URL}/worker_vm/").mock(
        return_value=httpx.Response(200, json=_empty_page())
    )

    await status.list_node_status(ctx, location="London")

    assert list_route.calls.last.request.url.params["system_location"] == fk("system_location", 4)


@respx.mock
async def test_get_node_status_resolves_name(ctx):
    respx.get(f"{BASE_URL}/worker_vm/").mock(
        return_value=httpx.Response(
            200,
            json={
                "meta": {"total_count": 1, "limit": 2, "offset": 0,
                         "next": None, "previous": None},
                "objects": [
                    {"id": 12, "name": "lon-conf-01", "resource_uri": fk("worker_vm", 12)}
                ],
            },
        )
    )
    respx.get(f"{STATUS_URL}/worker_vm/12/").mock(
        return_value=httpx.Response(200, json={"id": 12, "media_load": 42})
    )

    result = await status.get_node_status(ctx, "lon-conf-01")

    assert result["media_load"] == 42


@respx.mock
async def test_get_licensing_status(ctx):
    route = respx.get(f"{STATUS_URL}/licensing/").mock(
        return_value=httpx.Response(
            200,
            json={
                "meta": {"total_count": 1, "limit": 1000, "offset": 0,
                         "next": None, "previous": None},
                "objects": [{"port_used": 12, "port_max": 100}],
            },
        )
    )

    result = await status.get_licensing_status(ctx)

    assert route.called
    assert result["objects"][0]["port_used"] == 12


@respx.mock
async def test_get_participant_quality_combines_participant_and_streams(ctx):
    pid = "00000000-0000-0000-0000-0000000000f1"
    respx.get(f"{STATUS_URL}/participant/{pid}/").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": pid,
                "display_name": "Alice",
                "call_quality": "1_good",
                "conference": "Standup",
            },
        )
    )
    respx.get(f"{STATUS_URL}/participant_media_stream/").mock(
        return_value=httpx.Response(
            200,
            json={
                "meta": {"total_count": 2, "limit": 100, "offset": 0,
                         "next": None, "previous": None},
                "objects": [
                    {"media_type": "audio", "rx_bitrate": 64000, "tx_bitrate": 64000},
                    {"media_type": "video", "rx_bitrate": 1500000, "tx_bitrate": 1200000},
                ],
            },
        )
    )

    result = await status.get_participant_quality(ctx, participant_id=pid)

    assert result["participant"]["call_quality"] == "1_good"
    assert len(result["media_streams"]) == 2
    assert {s["media_type"] for s in result["media_streams"]} == {"audio", "video"}


@respx.mock
async def test_get_participant_quality_filters_streams_by_participant_uri(ctx):
    pid = "00000000-0000-0000-0000-0000000000f1"
    respx.get(f"{STATUS_URL}/participant/{pid}/").mock(
        return_value=httpx.Response(200, json={"id": pid})
    )
    streams_route = respx.get(f"{STATUS_URL}/participant_media_stream/").mock(
        return_value=httpx.Response(
            200, json={"meta": {"total_count": 0, "limit": 100, "offset": 0,
                                "next": None, "previous": None},
                      "objects": []}
        )
    )

    await status.get_participant_quality(ctx, participant_id=pid)

    expected_uri = f"/api/admin/status/v1/participant/{pid}/"
    assert streams_route.calls.last.request.url.params["participant"] == expected_uri


@respx.mock
async def test_fetch_all_walks_pagination(ctx):
    route = respx.get(f"{STATUS_URL}/participant/")
    route.side_effect = [
        httpx.Response(
            200,
            json={
                "meta": {"total_count": 1500, "limit": 1000, "offset": 0,
                         "next": "n", "previous": None},
                "objects": [{"id": str(i)} for i in range(1000)],
            },
        ),
        httpx.Response(
            200,
            json={
                "meta": {"total_count": 1500, "limit": 1000, "offset": 1000,
                         "next": None, "previous": "p"},
                "objects": [{"id": str(i)} for i in range(1000, 1500)],
            },
        ),
    ]

    result = await status.list_active_participants(ctx, fetch_all=True)

    assert len(result["objects"]) == 1500
    assert result["truncated"] is False
    assert route.call_count == 2
