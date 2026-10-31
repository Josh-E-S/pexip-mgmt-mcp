"""pexip_list_history / pexip_get_history over the history registry."""

from __future__ import annotations

import httpx
import pytest
import respx

from pexip_mcp.client import PexipError
from pexip_mcp.tools import history_generic

from .conftest import PEXIP_HOST

HISTORY = f"https://{PEXIP_HOST}/api/admin/history/v1"


def _page(objects):
    return httpx.Response(
        200,
        json={"objects": objects, "meta": {"total_count": len(objects), "limit": 20, "offset": 0}},
    )


async def test_unknown_resource_is_a_helpful_400(ctx):
    with pytest.raises(PexipError) as exc:
        await history_generic.list_history(ctx, resource="conference_shard")
    assert exc.value.status_code == 400
    assert "workervm_status_event" in str(exc.value)


@respx.mock
async def test_time_window_uses_each_resources_own_time_field(ctx):
    """Alarms bound time_raised, node events bound time (what the deleted typed
    tools sent); no ordering is imposed."""
    alarms = respx.get(f"{HISTORY}/alarm/").mock(
        return_value=_page([{"id": 1, "level": "critical"}])
    )
    await history_generic.list_history(
        ctx,
        resource="alarm",
        start_time="2026-10-01T00:00:00",
        end_time="2026-10-02T00:00:00",
        filters={"level": "critical"},
    )
    url = str(alarms.calls.last.request.url)
    assert "time_raised__gte=2026-10-01" in url and "time_raised__lt=2026-10-02" in url
    assert "order_by" not in url and "level=critical" in url

    events = respx.get(f"{HISTORY}/workervm_status_event/").mock(return_value=_page([]))
    await history_generic.list_history(
        ctx, resource="workervm_status_event", start_time="2026-10-01T00:00:00"
    )
    assert "time__gte=2026-10-01" in str(events.calls.last.request.url)


async def test_time_window_refused_for_resources_without_a_time_field(ctx):
    with pytest.raises(PexipError) as exc:
        await history_generic.list_history(
            ctx, resource="backplane", start_time="2026-10-01T00:00:00"
        )
    assert exc.value.status_code == 400 and "no time field" in str(exc.value)


async def test_name_contains_refused_for_resources_without_a_name_field(ctx):
    with pytest.raises(PexipError) as exc:
        await history_generic.list_history(ctx, resource="workervm_status_event", name_contains="x")
    assert exc.value.status_code == 400 and "no name field" in str(exc.value)


async def test_filter_that_duplicates_a_computed_param_is_refused(ctx):
    with pytest.raises(PexipError) as exc:
        await history_generic.list_history(
            ctx,
            resource="alarm",
            start_time="2026-10-01T00:00:00",
            filters={"time_raised__gte": "2026-01-01T00:00:00"},
        )
    assert exc.value.status_code == 400 and "duplicate" in str(exc.value)


@respx.mock
async def test_name_contains_uses_alias_for_registration_history(ctx):
    route = respx.get(f"{HISTORY}/registration_alias/").mock(return_value=_page([]))
    await history_generic.list_history(ctx, resource="registration_alias", name_contains="board")
    assert "alias__icontains=board" in str(route.calls.last.request.url)


@respx.mock
async def test_get_by_id_and_subpath(ctx):
    respx.get(f"{HISTORY}/alarm/7/").mock(return_value=httpx.Response(200, json={"id": 7}))
    assert (await history_generic.get_history(ctx, resource="alarm", id=7))["id"] == 7
    route = respx.get(f"{HISTORY}/backplane/9/media_stream/").mock(return_value=_page([{"rx": 1}]))
    out = await history_generic.get_history(ctx, resource="backplane/{id}/media_stream", id=9)
    assert route.called and out["objects"][0]["rx"] == 1
