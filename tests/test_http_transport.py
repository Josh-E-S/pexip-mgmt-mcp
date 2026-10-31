"""Tests for the --http transport gates and transport-security wiring.

Covers the 2026-10-31 security-review findings on `__main__.py`:
  - H2/H3: pure-ASGI gates; OIDC sessions bound to the principal that opened them
  - M1: a non-ASCII Authorization header is a 401, not a 500
  - M2: the RFC 9728 resource_metadata URL comes from PEXIP_MCP_PUBLIC_URL
  - M3: Host allow-list for DNS-rebinding protection from PEXIP_MCP_ALLOWED_HOSTS
  - I5: the inner app's lifespan really runs (an initialize succeeds through the gate)
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from pexip_mcp.__main__ import (
    _LOOPBACK_HOSTS,
    _OIDCGate,
    _StaticTokenGate,
    _build_http_app,
    _prm_url,
    _transport_security,
)
from pexip_mcp.config import PexipSettings
from pexip_mcp.oidc import OIDCValidationError

# TestClient's default base_url is http://testserver, which the SDK's loopback
# DNS-rebinding protection rejects (421). Use a loopback host:port instead.
BASE = "http://127.0.0.1:8000"
MCP_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}
INIT = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "0"},
    },
}


@pytest.fixture
def server_env(monkeypatch):
    """Settings the inner FastMCP lifespan needs; writes left ON so no tool is pruned
    from the shared registry while other tests run."""
    monkeypatch.setenv("PEXIP_HOST", "manager.example.com")
    monkeypatch.setenv("PEXIP_USERNAME", "admin")
    monkeypatch.setenv("PEXIP_PASSWORD", "secret")
    monkeypatch.setenv("PEXIP_READ_ONLY", "false")
    monkeypatch.setenv("PEXIP_ALLOW_PLATFORM_TOOLS", "true")
    # The SDK's StreamableHTTPSessionManager may only be run once per instance,
    # and the shared FastMCP singleton caches it; drop the cache so each test that
    # enters the lifespan gets a fresh manager.
    from pexip_mcp.mcp_app import mcp

    mcp._session_manager = None
    yield
    mcp._session_manager = None


class _MapValidator:
    """OIDC validator stub: `Bearer <name>` -> principal `<name>@example.com`."""

    def __init__(self, *names: str) -> None:
        self._names = set(names)

    def verify(self, header: str) -> dict:
        prefix = "Bearer "
        if not header.startswith(prefix) or header[len(prefix) :] not in self._names:
            raise OIDCValidationError("nope")
        return {"sub": header[len(prefix) :], "email": f"{header[len(prefix) :]}@example.com"}


class _Settings:
    oidc_issuer = "https://issuer.example.com"
    oidc_audience = "api://pexip-mcp"
    oidc_required_scopes_list: list[str] = []
    mcp_public_url = "https://pexip-mcp.example.com"
    mcp_allowed_hosts_list: list[str] = []
    mcp_allowed_origins_list: list[str] = []


# ── Gate types ───────────────────────────────────────────────────────────────


def test_gates_are_pure_asgi_not_base_http_middleware():
    from starlette.middleware.base import BaseHTTPMiddleware

    assert not issubclass(_StaticTokenGate, BaseHTTPMiddleware)
    assert not issubclass(_OIDCGate, BaseHTTPMiddleware)
    assert isinstance(_build_http_app(token="x" * 32), _StaticTokenGate)
    assert isinstance(
        _build_http_app(token=None, oidc_validator=_MapValidator(), settings=_Settings()),
        _OIDCGate,
    )


# ── Static token gate ────────────────────────────────────────────────────────


def test_static_token_non_ascii_header_is_401_not_500():
    """Drive the gate as raw ASGI: httpx refuses to send a non-ASCII header, but a
    hostile or broken client can. Previously hmac.compare_digest raised TypeError
    on the mixed str/bytes comparison and the server answered 500."""
    import asyncio

    gate = _StaticTokenGate(app=None, token="secret-token")
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/mcp",
        "headers": [(b"authorization", "Bearer caf\xe9".encode("latin-1"))],
    }
    sent: list[dict] = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    asyncio.run(gate(scope, receive, send))
    assert sent[0]["type"] == "http.response.start" and sent[0]["status"] == 401


def test_static_token_accepts_correct_token_and_lifespan_runs(server_env):
    """The one test that proves the mounted app's lifespan is entered: without it
    the session manager is never started and an initialize fails inside the SDK."""
    app = _build_http_app(token="secret-token")
    with TestClient(app, base_url=BASE) as client:
        r = client.post(
            "/mcp", json=INIT, headers={**MCP_HEADERS, "Authorization": "Bearer secret-token"}
        )
    assert r.status_code == 200, r.text
    assert r.headers.get("mcp-session-id")


# ── OIDC gate: discovery and session binding ────────────────────────────────


def test_oidc_401_challenge_points_at_public_prm_url():
    app = _build_http_app(token=None, oidc_validator=_MapValidator(), settings=_Settings())
    client = TestClient(app, base_url=BASE)
    r = client.post("/mcp", json=INIT, headers=MCP_HEADERS)
    assert r.status_code == 401
    assert (
        'resource_metadata="https://pexip-mcp.example.com/.well-known/oauth-protected-resource"'
        in r.headers["WWW-Authenticate"]
    )
    # The PRM document itself needs no token.
    assert client.get("/.well-known/oauth-protected-resource").status_code == 200


def test_oidc_session_is_bound_to_the_principal_that_opened_it(server_env):
    app = _build_http_app(
        token=None, oidc_validator=_MapValidator("alice", "bob"), settings=_Settings()
    )
    with TestClient(app, base_url=BASE) as client:
        opened = client.post(
            "/mcp", json=INIT, headers={**MCP_HEADERS, "Authorization": "Bearer alice"}
        )
        assert opened.status_code == 200, opened.text
        sid = opened.headers["mcp-session-id"]
        assert app._sessions[sid] == "alice@example.com"

        ping = {"jsonrpc": "2.0", "id": 2, "method": "ping"}
        # Bob presents his own valid token with Alice's session: refused.
        riding = client.post(
            "/mcp",
            json=ping,
            headers={**MCP_HEADERS, "Authorization": "Bearer bob", "mcp-session-id": sid},
        )
        assert riding.status_code == 403
        assert "different principal" in riding.json()["error_description"]

        # Alice continues on her own session.
        own = client.post(
            "/mcp",
            json=ping,
            headers={**MCP_HEADERS, "Authorization": "Bearer alice", "mcp-session-id": sid},
        )
        assert own.status_code != 403

        # Closing the session drops the binding.
        client.delete(
            "/mcp", headers={**MCP_HEADERS, "Authorization": "Bearer alice", "mcp-session-id": sid}
        )
        assert sid not in app._sessions


def test_oidc_unknown_session_id_is_not_blocked(server_env):
    """A session id the gate has never seen (e.g. after a restart) is left to the
    transport to reject; the gate only enforces bindings it recorded."""
    app = _build_http_app(token=None, oidc_validator=_MapValidator("alice"), settings=_Settings())
    with TestClient(app, base_url=BASE) as client:
        r = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
            headers={**MCP_HEADERS, "Authorization": "Bearer alice", "mcp-session-id": "ghost"},
        )
    assert r.status_code != 403


def test_oidc_session_table_is_bounded():
    gate = _OIDCGate(app=None, validator=_MapValidator(), prm_url="x")
    from pexip_mcp import __main__ as m

    for i in range(m._MAX_BOUND_SESSIONS + 50):
        gate._bind(f"s{i}", "p")
    assert len(gate._sessions) == m._MAX_BOUND_SESSIONS
    assert "s0" not in gate._sessions  # oldest evicted first


# ── PRM URL ──────────────────────────────────────────────────────────────────


def test_prm_url_prefers_public_url_then_http_audience_then_path():
    class S:
        mcp_public_url = None
        oidc_audience = "api://pexip-mcp"

    assert _prm_url(S()) == "/.well-known/oauth-protected-resource"
    S.oidc_audience = "https://mcp.example.com/"
    assert _prm_url(S()) == "https://mcp.example.com/.well-known/oauth-protected-resource"
    S.mcp_public_url = "https://public.example.com/"
    assert _prm_url(S()) == "https://public.example.com/.well-known/oauth-protected-resource"


# ── Transport security (Host allow-list) ─────────────────────────────────────


def _settings(**overrides) -> PexipSettings:
    base = dict(host="h", username="u", password="p")
    return PexipSettings(**base, **overrides)


def test_allowed_hosts_setting_expands_bare_hostnames_to_any_port():
    s = _settings(mcp_allowed_hosts="pexip-mcp.example.com, 10.0.0.5:8443")
    assert s.mcp_allowed_hosts_list == [
        "pexip-mcp.example.com",
        "pexip-mcp.example.com:*",
        "10.0.0.5:8443",
    ]


def test_transport_security_loopback_plus_configured_hosts():
    sec = _transport_security("127.0.0.1", _settings(mcp_allowed_hosts="pexip-mcp.example.com"))
    assert sec.enable_dns_rebinding_protection is True
    assert "pexip-mcp.example.com:*" in sec.allowed_hosts
    assert "localhost:*" in sec.allowed_hosts


def test_transport_security_non_loopback_without_hosts_keeps_sdk_default(capsys):
    assert "0.0.0.0" not in _LOOPBACK_HOSTS
    assert _transport_security("0.0.0.0", _settings()) is None
    assert "PEXIP_MCP_ALLOWED_HOSTS" in capsys.readouterr().err


def test_transport_security_non_loopback_with_hosts_enables_protection():
    sec = _transport_security("0.0.0.0", _settings(mcp_allowed_hosts="mcp.example.com"))
    assert sec is not None and "mcp.example.com" in sec.allowed_hosts
