from __future__ import annotations

import httpx
import pytest
import respx

from pexip_mcp.client import PexipError
from pexip_mcp.tools import history

from .conftest import BASE_URL, HISTORY_URL, fk


def _empty_page(limit: int = 20):
    return {
        "meta": {"total_count": 0, "limit": limit, "offset": 0,
                 "next": None, "previous": None},
        "objects": [],
    }


@respx.mock
async def test_list_history_conferences_time_window(ctx):
    route = respx.get(f"{HISTORY_URL}/conference/").mock(
        return_value=httpx.Response(200, json=_empty_page())
    )

    await history.list_history_conferences(
        ctx,
        start_time="2026-05-07T00:00:00",
        end_time="2026-05-08T00:00:00",
        service_type="conference",
    )

    params = route.calls.last.request.url.params
    assert params["start_time__gte"] == "2026-05-07T00:00:00"
    assert params["start_time__lt"] == "2026-05-08T00:00:00"
    assert params["service_type"] == "conference"
    assert params["order_by"] == "-start_time"


@respx.mock
async def test_get_history_conference(ctx):
    respx.get(f"{HISTORY_URL}/conference/abc-123/").mock(
        return_value=httpx.Response(200, json={"id": "abc-123", "name": "AllHands"})
    )

    result = await history.get_history_conference(ctx, "abc-123")

    assert result["name"] == "AllHands"


@respx.mock
async def test_list_history_participants_filters_quality_and_direction(ctx):
    route = respx.get(f"{HISTORY_URL}/participant/").mock(
        return_value=httpx.Response(200, json=_empty_page())
    )

    await history.list_history_participants(
        ctx,
        start_time="2026-05-01T00:00:00",
        end_time="2026-05-08T00:00:00",
        call_direction="in",
        call_quality="4_terrible",
        protocol="webrtc",
    )

    params = route.calls.last.request.url.params
    assert params["call_direction"] == "in"
    assert params["call_quality"] == "4_terrible"
    assert params["protocol"] == "webrtc"


@respx.mock
async def test_list_history_participants_resolves_location(ctx):
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
    list_route = respx.get(f"{HISTORY_URL}/participant/").mock(
        return_value=httpx.Response(200, json=_empty_page())
    )

    await history.list_history_participants(ctx, location="London")

    assert list_route.calls.last.request.url.params["system_location"] == fk("system_location", 4)


@respx.mock
async def test_get_history_participant_returns_deep_quality(ctx):
    respx.get(f"{HISTORY_URL}/participant/p-1/").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "p-1",
                "call_quality": "1_good",
                "bucketed_call_quality": [0, 7, 3, 1, 2],
            },
        )
    )

    result = await history.get_history_participant(ctx, "p-1")

    assert result["bucketed_call_quality"] == [0, 7, 3, 1, 2]


@respx.mock
async def test_summarize_calls_invalid_group_by_raises_400(ctx):
    with pytest.raises(PexipError) as exc:
        await history.summarize_calls(
            ctx,
            start_time="2026-05-01T00:00:00",
            end_time="2026-05-08T00:00:00",
            group_by="bogus_field",
        )

    assert exc.value.status_code == 400


@respx.mock
async def test_summarize_calls_aggregates_by_call_direction(ctx):
    respx.get(f"{HISTORY_URL}/participant/").mock(
        return_value=httpx.Response(
            200,
            json={
                "meta": {"total_count": 5, "limit": 1000, "offset": 0,
                         "next": None, "previous": None},
                "objects": [
                    {"id": "1", "call_direction": "in", "duration": 60},
                    {"id": "2", "call_direction": "in", "duration": 120},
                    {"id": "3", "call_direction": "out", "duration": 30},
                    {"id": "4", "call_direction": "out", "duration": 90},
                    {"id": "5", "call_direction": None, "duration": 10},
                ],
            },
        )
    )

    result = await history.summarize_calls(
        ctx,
        start_time="2026-05-07T00:00:00",
        end_time="2026-05-08T00:00:00",
        group_by="call_direction",
    )

    assert result["total_calls"] == 5
    assert result["total_duration_seconds"] == 60 + 120 + 30 + 90 + 10
    assert result["average_duration_seconds"] == (60 + 120 + 30 + 90 + 10) / 5
    assert result["group_by"] == "call_direction"
    assert result["groups"]["in"] == {"count": 2, "duration_seconds": 180}
    assert result["groups"]["out"] == {"count": 2, "duration_seconds": 120}
    assert result["groups"]["unknown"] == {"count": 1, "duration_seconds": 10}
    assert result["truncated"] is False
    # Result should be sorted by count desc; unknown (1) appears last
    keys = list(result["groups"].keys())
    assert keys[-1] == "unknown"


@respx.mock
async def test_summarize_calls_passes_filters(ctx):
    route = respx.get(f"{HISTORY_URL}/participant/").mock(
        return_value=httpx.Response(
            200,
            json={
                "meta": {"total_count": 0, "limit": 1000, "offset": 0,
                         "next": None, "previous": None},
                "objects": [],
            },
        )
    )

    await history.summarize_calls(
        ctx,
        start_time="2026-05-01T00:00:00",
        end_time="2026-05-08T00:00:00",
        group_by="call_quality",
        service_tag="exec",
        call_direction="in",
    )

    params = route.calls.last.request.url.params
    assert params["start_time__gte"] == "2026-05-01T00:00:00"
    assert params["start_time__lt"] == "2026-05-08T00:00:00"
    assert params["service_tag"] == "exec"
    assert params["call_direction"] == "in"


@respx.mock
async def test_summarize_calls_truncated_when_max_records_hit(ctx):
    route = respx.get(f"{HISTORY_URL}/participant/")
    route.side_effect = [
        httpx.Response(
            200,
            json={
                "meta": {"total_count": 50000, "limit": 1000, "offset": 0,
                         "next": "n", "previous": None},
                "objects": [
                    {"id": str(i), "call_direction": "in", "duration": 60}
                    for i in range(1000)
                ],
            },
        ),
        httpx.Response(
            200,
            json={
                "meta": {"total_count": 50000, "limit": 1000, "offset": 1000,
                         "next": "n", "previous": "p"},
                "objects": [
                    {"id": str(i), "call_direction": "out", "duration": 30}
                    for i in range(1000, 2000)
                ],
            },
        ),
    ]

    result = await history.summarize_calls(
        ctx,
        start_time="2026-05-01T00:00:00",
        end_time="2026-05-08T00:00:00",
        group_by="call_direction",
        max_records=2000,
    )

    assert result["truncated"] is True
    assert result["total_calls"] == 2000
    assert result["server_total_count"] == 50000
