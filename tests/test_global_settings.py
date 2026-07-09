from __future__ import annotations

import json

import httpx
import pytest
import respx

from pexip_mcp.client import PexipError
from pexip_mcp.tools import global_settings

from .conftest import BASE_URL


@respx.mock
async def test_get_global_settings(ctx):
    respx.get(f"{BASE_URL}/global/1/").mock(
        return_value=httpx.Response(
            200, json={"id": 1, "management_session_timeout_secs": 1800}
        )
    )

    result = await global_settings.get_global_settings(ctx)

    assert result["id"] == 1


@respx.mock
async def test_update_global_settings_empty_raises(ctx):
    with pytest.raises(PexipError) as exc:
        await global_settings.update_global_settings(ctx, updates={})

    assert exc.value.status_code == 400


@respx.mock
async def test_update_global_settings_patches_singleton(ctx):
    patch = respx.patch(f"{BASE_URL}/global/1/").mock(return_value=httpx.Response(202))
    respx.get(f"{BASE_URL}/global/1/").mock(
        return_value=httpx.Response(
            200, json={"id": 1, "management_session_timeout_secs": 3600}
        )
    )

    result = await global_settings.update_global_settings(
        ctx, updates={"management_session_timeout_secs": 3600}
    )

    payload = json.loads(patch.calls.last.request.read())
    assert payload == {"management_session_timeout_secs": 3600}
    assert result["management_session_timeout_secs"] == 3600
