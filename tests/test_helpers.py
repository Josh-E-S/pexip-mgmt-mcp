"""Tests for the shared tool helpers (`pexip_mcp.tools._helpers`).

Right now this focuses on `paginate_all`: that it walks pages until Pexip says
`meta.next == None`, that it stops at `max_records` (returning `truncated=True`),
and that it handles empty result sets cleanly.

The `_page()` helper below builds a fake Pexip list-response body in the shape
documented in `_helpers.paginate_all`'s docstring. We feed a sequence of those
into `respx`'s `route.side_effect = [...]` so the same URL returns a different
page on each call — that's how we simulate Pexip paginating.
"""
from __future__ import annotations

import httpx
import respx

from pexip_mcp.tools._helpers import paginate_all

from .conftest import HISTORY_URL


# Use _page to build one fake Pexip list-response body for `route.side_effect`.
def _page(*, total: int, objects: list, has_next: bool):
    """Return a dict shaped like a real Pexip list response (see _helpers.paginate_all)."""
    return {
        "meta": {
            "total_count": total,
            "limit": len(objects),
            "offset": 0,
            "next": "next-url" if has_next else None,
            "previous": None,
        },
        "objects": objects,
    }


@respx.mock
async def test_paginate_all_walks_pages_until_next_is_null(client):
    route = respx.get(f"{HISTORY_URL}/participant/")
    route.side_effect = [
        httpx.Response(200, json=_page(total=2500, objects=[{"id": i} for i in range(1000)],
                                       has_next=True)),
        httpx.Response(200, json=_page(total=2500, objects=[{"id": i} for i in range(1000, 2000)],
                                       has_next=True)),
        httpx.Response(200, json=_page(total=2500, objects=[{"id": i} for i in range(2000, 2500)],
                                       has_next=False)),
    ]

    result = await paginate_all(client, "participant", api="history", page_size=1000)

    assert len(result["objects"]) == 2500
    assert result["truncated"] is False
    assert result["meta"]["total_count"] == 2500
    assert result["meta"]["fetched"] == 2500
    assert route.call_count == 3
    # Verify offsets advanced correctly
    assert route.calls[0].request.url.params["offset"] == "0"
    assert route.calls[1].request.url.params["offset"] == "1000"
    assert route.calls[2].request.url.params["offset"] == "2000"


@respx.mock
async def test_paginate_all_truncates_at_max_records(client):
    route = respx.get(f"{HISTORY_URL}/participant/")
    route.side_effect = [
        httpx.Response(200, json=_page(total=10000, objects=[{"id": i} for i in range(1000)],
                                       has_next=True)),
        httpx.Response(200, json=_page(total=10000,
                                       objects=[{"id": i} for i in range(1000, 2000)],
                                       has_next=True)),
    ]

    result = await paginate_all(
        client, "participant", api="history", max_records=1500, page_size=1000
    )

    assert len(result["objects"]) == 1500
    assert result["truncated"] is True
    assert result["meta"]["fetched"] == 1500
    assert route.call_count == 2


@respx.mock
async def test_paginate_all_stops_on_empty_page(client):
    respx.get(f"{HISTORY_URL}/participant/").mock(
        return_value=httpx.Response(200, json=_page(total=0, objects=[], has_next=False))
    )

    result = await paginate_all(client, "participant", api="history")

    assert result["objects"] == []
    assert result["truncated"] is False
