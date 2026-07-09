"""Tests for audit logging of mutating Management API calls, and F6 error redaction."""
from __future__ import annotations

import logging

import httpx
import pytest
import respx

from pexip_mcp import audit
from pexip_mcp.client import PexipError

from .conftest import BASE_URL, COMMAND_URL


@pytest.fixture
def audit_logs(caplog):
    """Capture pexip_mcp.audit records at INFO and above."""
    caplog.set_level(logging.INFO, logger="pexip_mcp.audit")
    return caplog


# ── audit lines are emitted for mutations ────────────────────────────────────


@respx.mock
async def test_create_emits_ok_audit_line(client, audit_logs):
    respx.post(f"{BASE_URL}/conference/").mock(
        return_value=httpx.Response(201, headers={"Location": "/x/conference/9/"})
    )
    await client.create("conference", {"name": "R"})
    line = next(r.message for r in audit_logs.records if r.name == "pexip_mcp.audit")
    assert "action=create" in line
    assert "resource=conference" in line
    assert "outcome=ok" in line
    assert "principal=basic:admin" in line  # from the client fixture's username
    assert "duration_ms=" in line


@respx.mock
async def test_update_and_delete_include_resolved_id(client, audit_logs):
    respx.patch(f"{BASE_URL}/conference/42/").mock(return_value=httpx.Response(202))
    respx.delete(f"{BASE_URL}/conference/7/").mock(return_value=httpx.Response(204))
    await client.update("conference", 42, {"name": "N"})
    await client.delete("conference", 7)
    lines = [r.message for r in audit_logs.records if r.name == "pexip_mcp.audit"]
    assert any("action=update" in m and "id=42" in m for m in lines)
    assert any("action=delete" in m and "id=7" in m for m in lines)


@respx.mock
async def test_command_audited(client, audit_logs):
    respx.post(f"{COMMAND_URL}/participant/disconnect/").mock(
        return_value=httpx.Response(200, json={"status": "success"})
    )
    await client.command("participant", "disconnect", {"participant_id": "abc"})
    lines = [r.message for r in audit_logs.records if r.name == "pexip_mcp.audit"]
    assert any("action=command" in m and "resource=participant" in m and "id=disconnect" in m
               for m in lines)


@respx.mock
async def test_failed_mutation_logs_warning_with_ref(client, audit_logs):
    respx.delete(f"{BASE_URL}/conference/5/").mock(
        return_value=httpx.Response(404, json={"detail": "gone"})
    )
    with pytest.raises(PexipError) as exc:
        await client.delete("conference", 5)
    warnings = [r for r in audit_logs.records
                if r.name == "pexip_mcp.audit" and r.levelno == logging.WARNING]
    assert warnings, "a failed mutation must log a WARNING audit line"
    msg = warnings[-1].message
    assert "outcome=error" in msg
    assert "status=404" in msg
    # The audit ref matches the exception's correlation id (client can report it).
    assert f"ref={exc.value.correlation_id}" in msg


@respx.mock
async def test_reads_are_not_audited(client, audit_logs):
    respx.get(f"{BASE_URL}/conference/1/").mock(
        return_value=httpx.Response(200, json={"id": 1})
    )
    await client.get("conference", 1)
    assert not [r for r in audit_logs.records if r.name == "pexip_mcp.audit"]


# ── principal resolution ─────────────────────────────────────────────────────


@respx.mock
async def test_oidc_principal_overrides_credential_identity(client, audit_logs):
    respx.post(f"{BASE_URL}/conference/").mock(
        return_value=httpx.Response(201, headers={"Location": "/x/conference/1/"})
    )
    token = audit.current_principal.set("josh@example.com")
    try:
        await client.create("conference", {"name": "R"})
    finally:
        audit.current_principal.reset(token)
    line = next(r.message for r in audit_logs.records if r.name == "pexip_mcp.audit")
    assert "principal=josh@example.com" in line
    assert "basic:admin" not in line


# ── F6: upstream error redaction ─────────────────────────────────────────────


def test_upstream_error_hides_body_from_client():
    err = PexipError(500, {"trace": "internal stack detail"}, upstream=True)
    # Client-facing string: generic + correlation id, no body.
    assert "internal stack detail" not in str(err)
    assert "ref" in str(err)
    assert err.correlation_id in str(err)
    # But status/body stay available for tool logic and internal logging.
    assert err.status_code == 500
    assert err.body == {"trace": "internal stack detail"}
    assert "internal stack detail" in err.detail()


def test_tool_raised_error_keeps_its_message():
    # Non-upstream errors (our own validation/guards) stay visible to the LLM.
    err = PexipError(400, {"settings": ["At least one field is required"]})
    assert "At least one field is required" in str(err.body)
    assert str(err)  # has a message; body is not suppressed for our own errors
