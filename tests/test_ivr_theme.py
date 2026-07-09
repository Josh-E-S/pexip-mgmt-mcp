from __future__ import annotations

import httpx
import respx

from pexip_mcp.tools import ivr_theme

from .conftest import BASE_URL, fk


@respx.mock
async def test_list_ivr_themes(ctx):
    route = respx.get(f"{BASE_URL}/ivr_theme/").mock(
        return_value=httpx.Response(
            200, json={"meta": {"total_count": 0, "limit": 20, "offset": 0,
                                "next": None, "previous": None},
                      "objects": []}
        )
    )

    await ivr_theme.list_ivr_themes(ctx, name_contains="exec")

    assert route.calls.last.request.url.params["name__icontains"] == "exec"


@respx.mock
async def test_get_ivr_theme_by_name(ctx):
    respx.get(f"{BASE_URL}/ivr_theme/").mock(
        return_value=httpx.Response(
            200,
            json={
                "meta": {"total_count": 1, "limit": 2, "offset": 0,
                         "next": None, "previous": None},
                "objects": [{"id": 2, "name": "default",
                             "resource_uri": fk("ivr_theme", 2)}],
            },
        )
    )
    respx.get(f"{BASE_URL}/ivr_theme/2/").mock(
        return_value=httpx.Response(200, json={"id": 2, "name": "default"})
    )

    result = await ivr_theme.get_ivr_theme(ctx, "default")

    assert result["name"] == "default"
