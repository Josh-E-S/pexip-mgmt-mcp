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
async def test_time_window_applies_only_where_the_resource_has_start_time(ctx):
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
    assert "start_time__gte=2026-10-01" in url and "start_time__lt=2026-10-02" in url
    assert "order_by=-start_time" in url and "level=critical" in url

    backplanes = respx.get(f"{HISTORY}/backplane/").mock(return_value=_page([]))
    await history_generic.list_history(ctx, resource="backplane", start_time="2026-10-01T00:00:00")
    assert "start_time" not in str(backplanes.calls.last.request.url)


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
