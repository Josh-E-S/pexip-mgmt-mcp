"""Shared pytest fixtures and URL constants for the whole test suite.

How these tests work — important for newcomers
----------------------------------------------
We never hit a real Pexip Management Node in tests. Instead, every test wraps
itself with `@respx.mock` (see https://lundberg.github.io/respx/), which patches
httpx so that any request to a URL we've registered (`respx.get(...)`,
`respx.post(...)`, etc.) gets a canned `httpx.Response` back — and any request
to a URL we did NOT register raises, so missing mocks are obvious.

The `client` fixture builds a real `PexipClient` pointed at `manager.example.com`.
That host doesn't exist; respx ensures no DNS or socket call ever happens.

The `ctx` fixture fakes the MCP Context object that FastMCP passes to every tool
at runtime. Tools reach the PexipClient via `ctx.request_context.lifespan_context.pexip`
(see `pexip_mcp/tools/_helpers.py::get_client`). We mimic that exact attribute
chain with nested `SimpleNamespace` so tools can run unmodified in tests.

URL constants (BASE_URL, STATUS_URL, ...) match the four Pexip sub-APIs from
`client.py` — tests import the ones they need and append `/<resource>/` to mock
specific endpoints.

`vmr_uri` / `fk` build the FK URI strings Pexip uses for cross-resource
references (see `_helpers.py::fk_uri`); tests use them to assert that POST/PATCH
bodies contain the right reference string.

pytest-asyncio runs async tests automatically (see `asyncio_mode = "auto"` in
pyproject.toml), so async def tests don't need a decorator.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
import pytest_asyncio

from pexip_mcp.client import PexipClient

PEXIP_HOST = "manager.example.com"
ROOT_URL = f"https://{PEXIP_HOST}/api/admin"
BASE_URL = f"{ROOT_URL}/configuration/v1"
STATUS_URL = f"{ROOT_URL}/status/v1"
HISTORY_URL = f"{ROOT_URL}/history/v1"
COMMAND_URL = f"{ROOT_URL}/command/v1"


# Use the `client` fixture to get a real PexipClient pointed at the fake host
# — respx will intercept every request it makes.
@pytest_asyncio.fixture
async def client():
    """Yield a PexipClient configured for the test host, and close it after the test."""
    c = PexipClient(host=PEXIP_HOST, username="admin", password="password")
    try:
        yield c
    finally:
        await c.aclose()


# Use the `ctx` fixture when a test exercises a tool function rather than the
# raw PexipClient — tools take a Context, not a client.
@pytest.fixture
def ctx(client):
    """Minimal MCP Context stand-in exposing ctx.request_context.lifespan_context.pexip.

    Mirrors the real attribute chain FastMCP gives to tool functions, so the
    same `get_client(ctx)` call works in tests as in production.
    """
    return SimpleNamespace(
        request_context=SimpleNamespace(lifespan_context=SimpleNamespace(pexip=client))
    )


# Use vmr_uri to build the FK URI string Pexip wants when one resource points at a VMR.
def vmr_uri(vmr_id: int) -> str:
    """Build the configuration-API FK URI for a VMR (`/api/admin/configuration/v1/conference/<id>/`)."""
    return f"/api/admin/configuration/v1/conference/{vmr_id}/"


# Use fk to build the FK URI for any configuration-API resource (system_location, ivr_theme, ...).
def fk(resource: str, obj_id: int) -> str:
    """Build the configuration-API FK URI for any resource by name and id."""
    return f"/api/admin/configuration/v1/{resource}/{obj_id}/"
