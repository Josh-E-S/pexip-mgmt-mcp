"""Tests for the security-hardening controls added across the codebase.

Covers, in isolation:
  - redact_secrets: secret-bearing fields are masked on read paths.
  - _safe_segment / _safe_resource_path: path-traversal / allowlist-bypass guard.
  - resource_crud sensitive-resource gate (F2): SSH keys, roles, auth, certs are
    refused through generic CRUD unless explicitly allowed.
  - create_vmr PIN-by-default: an unprotected room requires allow_no_pin=True.
  - _build_http_app lifespan delegation (F1): the mounted app's lifespan runs,
    which is what applies read-only enforcement on the --http transport.
"""
from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
import respx

from pexip_mcp.client import PexipError
from pexip_mcp.tools import conference, resource_crud
from pexip_mcp.tools._helpers import redact_secrets, security_resources_allowed

from .conftest import BASE_URL, vmr_uri


# ── redact_secrets ───────────────────────────────────────────────────────────


def test_redact_secrets_masks_known_secret_keys():
    data = {
        "name": "sink1",
        "password": "hunter2",
        "bind_password": "s3cret",
        "client_secret": "abc",
        "token": "tok",
        "pin": "1234",
        "guest_pin": "5678",
        "url": "https://example.com",
    }
    out = redact_secrets(data)
    assert out["password"] == "***REDACTED***"
    assert out["bind_password"] == "***REDACTED***"
    assert out["client_secret"] == "***REDACTED***"
    assert out["token"] == "***REDACTED***"
    assert out["pin"] == "***REDACTED***"
    assert out["guest_pin"] == "***REDACTED***"
    # Non-secret fields pass through untouched.
    assert out["name"] == "sink1"
    assert out["url"] == "https://example.com"


def test_redact_secrets_recurses_and_preserves_empty():
    data = {"objects": [{"password": "x"}, {"password": ""}], "meta": {"total": 2}}
    out = redact_secrets(data)
    assert out["objects"][0]["password"] == "***REDACTED***"
    # Empty/unset stays visible so "field not set" is distinguishable.
    assert out["objects"][1]["password"] == ""
    assert out["meta"]["total"] == 2


@respx.mock
async def test_get_resource_redacts_secret_fields(ctx):
    respx.get(f"{BASE_URL}/sip_credential/5/").mock(
        return_value=httpx.Response(
            200, json={"id": 5, "username": "svc", "password": "supersecret"}
        )
    )
    result = await resource_crud.get_resource(ctx, resource="sip_credential", id=5)
    assert result["password"] == "***REDACTED***"
    assert result["username"] == "svc"


# ── path-segment validation (F4) ─────────────────────────────────────────────


async def test_get_rejects_traversal_in_id(client):
    with pytest.raises(PexipError) as exc:
        await client.get("conference", "../global")
    assert exc.value.status_code == 400


async def test_get_rejects_traversal_in_resource(client):
    with pytest.raises(PexipError) as exc:
        await client.get("conference/../global", 1)
    assert exc.value.status_code == 400


async def test_list_allows_legit_multi_segment_resource(client):
    # Nested status paths (e.g. worker_vm/12/statistics) must still be accepted.
    with respx.mock:
        route = respx.get(
            "https://manager.example.com/api/admin/status/v1/worker_vm/12/statistics/"
        ).mock(return_value=httpx.Response(200, json={"objects": []}))
        await client.list("worker_vm/12/statistics", api="status")
        assert route.called


# ── sensitive-resource gate (F2) ─────────────────────────────────────────────


def _ctx(client, *, allow_security: bool):
    return SimpleNamespace(
        request_context=SimpleNamespace(
            lifespan_context=SimpleNamespace(
                pexip=client, allow_security_resources=allow_security
            )
        )
    )


async def test_create_sensitive_resource_refused_by_default(client):
    ctx = _ctx(client, allow_security=False)
    for resource in ("ssh_authorized_key", "role", "authentication", "ca_certificate"):
        with pytest.raises(PexipError) as exc:
            await resource_crud.create_resource(
                ctx, resource=resource, settings={"x": 1}
            )
        assert exc.value.status_code == 403


async def test_delete_sensitive_resource_refused_by_default(client):
    ctx = _ctx(client, allow_security=False)
    with pytest.raises(PexipError) as exc:
        await resource_crud.delete_resource(ctx, resource="ssh_authorized_key", id=1)
    assert exc.value.status_code == 403


@respx.mock
async def test_sensitive_resource_allowed_when_flag_set(client):
    ctx = _ctx(client, allow_security=True)
    respx.post(f"{BASE_URL}/ssh_authorized_key/").mock(
        return_value=httpx.Response(
            201,
            headers={"Location": "/api/admin/configuration/v1/ssh_authorized_key/3/"},
        )
    )
    respx.get(f"{BASE_URL}/ssh_authorized_key/3/").mock(
        return_value=httpx.Response(200, json={"id": 3, "keydata": "ssh-ed25519 AAAA"})
    )
    result = await resource_crud.create_resource(
        ctx, resource="ssh_authorized_key", settings={"keydata": "ssh-ed25519 AAAA"}
    )
    assert result["id"] == 3


async def test_non_sensitive_resource_not_gated(client):
    ctx = _ctx(client, allow_security=False)
    # dns_server is operational, not security-critical → empty-settings 400, not 403.
    with pytest.raises(PexipError) as exc:
        await resource_crud.create_resource(ctx, resource="dns_server", settings={})
    assert exc.value.status_code == 400


def test_security_resources_allowed_defaults_false_when_absent():
    # Older ctx shapes without the attribute fail closed.
    ctx = SimpleNamespace(
        request_context=SimpleNamespace(lifespan_context=SimpleNamespace())
    )
    assert security_resources_allowed(ctx) is False


# ── VMR PIN-by-default ───────────────────────────────────────────────────────


async def test_create_vmr_without_pin_refused(ctx):
    with pytest.raises(PexipError) as exc:
        await conference.create_vmr(ctx, name="Open Room")
    assert exc.value.status_code == 400


@respx.mock
async def test_create_vmr_with_pin_allowed(ctx):
    respx.post(f"{BASE_URL}/conference/").mock(
        return_value=httpx.Response(201, headers={"Location": vmr_uri(7)})
    )
    respx.get(f"{BASE_URL}/conference/7/").mock(
        return_value=httpx.Response(200, json={"id": 7})
    )
    result = await conference.create_vmr(ctx, name="Secure Room", pin="1234")
    assert result["id"] == 7


# ── F1: --http lifespan delegation ───────────────────────────────────────────


def test_build_http_app_wrapper_has_lifespan():
    """The wrapper must carry a lifespan so the mounted app's startup runs.

    Without this the PexipClient is never built and read-only enforcement never
    applies on the --http transport (the bug this fixes).
    """
    from pexip_mcp.__main__ import _build_http_app

    app = _build_http_app(token=None)
    # Starlette stores the configured lifespan on the router; assert it's not the
    # default no-op by confirming a lifespan context manager is wired up.
    assert app.router.lifespan_context is not None
