from __future__ import annotations

import os

import httpx
import pytest
import respx

from pexip_mcp.__main__ import _healthcheck

from .conftest import BASE_URL, PEXIP_HOST


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("PEXIP_HOST", PEXIP_HOST)
    monkeypatch.setenv("PEXIP_USERNAME", "admin")
    monkeypatch.setenv("PEXIP_PASSWORD", "secret")
    # Disable .env autoload so the fixture's vars win in any env.
    monkeypatch.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/tests")
    yield


@respx.mock
async def test_healthcheck_ok_returns_zero(env, capsys):
    respx.get(f"{BASE_URL}/conference/schema/").mock(
        return_value=httpx.Response(200, json={"fields": {}})
    )

    rc = await _healthcheck()

    assert rc == 0
    assert "OK" in capsys.readouterr().out


@respx.mock
async def test_healthcheck_auth_failure_returns_one(env, capsys):
    respx.get(f"{BASE_URL}/conference/schema/").mock(
        return_value=httpx.Response(401, json={"detail": "unauthorized"})
    )

    rc = await _healthcheck()

    assert rc == 1
    err = capsys.readouterr().err
    assert "FAIL" in err
    assert "401" in err


async def test_healthcheck_missing_config_returns_one(monkeypatch, capsys):
    # Clear any PEXIP_* env vars so PexipSettings raises
    for key in list(os.environ):
        if key.startswith("PEXIP_"):
            monkeypatch.delenv(key, raising=False)
    # Point .env loader at an empty dir so it can't find a real .env
    monkeypatch.chdir("/tmp")

    rc = await _healthcheck()

    assert rc == 1
    assert "FAIL" in capsys.readouterr().err


def test_safe_to_bind_loopback_without_token():
    from pexip_mcp.__main__ import _check_safe_to_bind

    assert _check_safe_to_bind("127.0.0.1", token=None) is None
    assert _check_safe_to_bind("::1", token=None) is None
    assert _check_safe_to_bind("localhost", token=None) is None


def test_safe_to_bind_non_loopback_requires_token():
    from pexip_mcp.__main__ import _check_safe_to_bind

    err = _check_safe_to_bind("0.0.0.0", token=None)
    assert err is not None
    assert "REFUSING TO START" in err
    assert "PEXIP_MCP_TOKEN" in err


def test_safe_to_bind_non_loopback_with_token_ok():
    from pexip_mcp.__main__ import _check_safe_to_bind

    strong = "a" * 32
    assert _check_safe_to_bind("0.0.0.0", token=strong) is None
    assert _check_safe_to_bind("10.0.0.5", token=strong) is None


def test_safe_to_bind_rejects_short_token():
    from pexip_mcp.__main__ import _check_safe_to_bind

    # A weak token is refused even on loopback — a false sense of security.
    err = _check_safe_to_bind("127.0.0.1", token="short")
    assert err is not None
    assert "too short" in err
    # ...and on a public bind.
    assert _check_safe_to_bind("0.0.0.0", token="short") is not None


def test_safe_to_bind_oauth_allows_non_loopback_without_token():
    from pexip_mcp.__main__ import _check_safe_to_bind

    # OIDC mode is downstream auth, so a non-loopback bind is safe with no token.
    assert _check_safe_to_bind("0.0.0.0", token=None, oauth=True) is None
    # ...but plain (no token, no oauth) still refuses.
    assert _check_safe_to_bind("0.0.0.0", token=None, oauth=False) is not None


def test_generate_token_prints_strong_token(capsys):
    from pexip_mcp.__main__ import _generate_token

    _generate_token()
    out = capsys.readouterr()
    combined = out.out + out.err
    assert "PEXIP_MCP_TOKEN=" in combined
    # Extract the value and confirm it clears the minimum-length guard.
    value = out.out.split("PEXIP_MCP_TOKEN=", 1)[1].split()[0]
    assert len(value) >= 32


def test_build_http_app_oidc_serves_prm_and_requires_auth():
    from starlette.testclient import TestClient

    from pexip_mcp.__main__ import _build_http_app

    class _Settings:
        oidc_issuer = "https://issuer.example.com"
        oidc_audience = "https://mcp.example.com"
        oidc_required_scopes_list = ["pexip.read"]

    class _RejectAll:
        def verify(self, header):
            from pexip_mcp.oidc import OIDCValidationError

            raise OIDCValidationError("nope")

    app = _build_http_app(token=None, oidc_validator=_RejectAll(), settings=_Settings())
    client = TestClient(app)

    # PRM discovery is public and advertises the IdP.
    prm = client.get("/.well-known/oauth-protected-resource")
    assert prm.status_code == 200
    body = prm.json()
    assert body["authorization_servers"] == ["https://issuer.example.com"]
    assert body["resource"] == "https://mcp.example.com"

    # A real MCP call with no/invalid token is rejected with a discovery hint.
    r = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
    assert r.status_code == 401
    assert "resource_metadata" in r.headers.get("WWW-Authenticate", "")


def test_build_http_app_without_token_has_no_auth_middleware():
    from pexip_mcp.__main__ import _build_http_app

    app = _build_http_app(token=None)
    assert app is not None  # Sanity; deeper auth checks below


async def test_build_http_app_with_token_rejects_missing_auth():
    from starlette.testclient import TestClient

    from pexip_mcp.__main__ import _build_http_app

    app = _build_http_app(token="secret-token")
    client = TestClient(app)
    r = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
    assert r.status_code == 401
    assert r.json() == {"error": "unauthorized"}


async def test_build_http_app_with_token_rejects_wrong_auth():
    from starlette.testclient import TestClient

    from pexip_mcp.__main__ import _build_http_app

    app = _build_http_app(token="secret-token")
    client = TestClient(app)
    r = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
        headers={"Authorization": "Bearer wrong"},
    )
    assert r.status_code == 401
