from __future__ import annotations

import httpx
import respx

from pexip_mcp.tools import schema

from .conftest import BASE_URL


@respx.mock
async def test_get_resource_schema_uses_format_json(ctx):
    route = respx.get(f"{BASE_URL}/conference/schema/").mock(
        return_value=httpx.Response(
            200,
            json={
                "fields": {"name": {"nullable": False, "type": "string"}},
                "filtering": {"name": ["exact", "icontains"]},
            },
        )
    )

    result = await schema.get_resource_schema(ctx, "conference")

    assert route.called
    assert route.calls.last.request.url.params["format"] == "json"
    assert result["fields"]["name"]["nullable"] is False
