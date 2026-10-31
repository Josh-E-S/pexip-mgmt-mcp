"""Tests for read-only mode (PEXIP_READ_ONLY).

Read-only mode is a server-side safety gate: when enabled, every mutating tool
(create/update/delete/control) is unregistered at startup so an LLM cannot call
it — only list/get/schema reads survive. These tests exercise the two moving
parts in isolation: the config flag parsing and the `enforce_read_only` pruning.

A throwaway FastMCP instance is built here (rather than mutating the shared
`mcp` singleton) so removing tools can't leak into other tests.
"""

from __future__ import annotations

import os

import pytest
from mcp.server.fastmcp import Context, FastMCP

from pexip_mcp.config import PexipSettings
from pexip_mcp.mcp_app import enforce_platform_gate, enforce_read_only
from pexip_mcp.tools._helpers import control, create, delete, read, update


@pytest.fixture
def clean_env(monkeypatch, tmp_path):
    for key in list(os.environ):
        if key.startswith("PEXIP_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)  # no .env here
    yield


def _server_with_one_tool_per_bucket() -> FastMCP:
    """Build a fresh FastMCP with exactly one tool per annotation bucket."""
    server = FastMCP("test-read-only")

    @server.tool(annotations=read("read one"))
    async def read_tool(ctx: Context) -> dict:
        return {}

    @server.tool(annotations=create("create one"))
    async def create_tool(ctx: Context) -> dict:
        return {}

    @server.tool(annotations=update("update one"))
    async def update_tool(ctx: Context) -> dict:
        return {}

    @server.tool(annotations=delete("delete one"))
    async def delete_tool(ctx: Context) -> dict:
        return {}

    @server.tool(annotations=control("control one"))
    async def control_tool(ctx: Context) -> dict:
        return {}

    return server


# --- config flag ---


def test_read_only_defaults_true(clean_env):
    # Secure by default: the mutating admin surface is opt-in.
    s = PexipSettings(host="h", username="u", password="p")
    assert s.read_only is True


def test_read_only_parses_true_from_env(clean_env, monkeypatch):
    monkeypatch.setenv("PEXIP_HOST", "h")
    monkeypatch.setenv("PEXIP_USERNAME", "u")
    monkeypatch.setenv("PEXIP_PASSWORD", "p")
    monkeypatch.setenv("PEXIP_READ_ONLY", "true")
    assert PexipSettings().read_only is True


def test_read_only_parses_false_from_env(clean_env, monkeypatch):
    monkeypatch.setenv("PEXIP_HOST", "h")
    monkeypatch.setenv("PEXIP_USERNAME", "u")
    monkeypatch.setenv("PEXIP_PASSWORD", "p")
    monkeypatch.setenv("PEXIP_READ_ONLY", "false")
    assert PexipSettings().read_only is False


# --- enforce_read_only pruning ---


def test_enforce_read_only_removes_only_mutating_tools():
    server = _server_with_one_tool_per_bucket()
    assert len(server._tool_manager.list_tools()) == 5

    removed = enforce_read_only(server)

    assert removed == ["control_tool", "create_tool", "delete_tool", "update_tool"]
    remaining = {t.name for t in server._tool_manager.list_tools()}
    assert remaining == {"read_tool"}


def test_enforce_read_only_is_idempotent():
    server = _server_with_one_tool_per_bucket()
    first = enforce_read_only(server)
    second = enforce_read_only(server)
    assert len(first) == 4
    assert second == []
    assert {t.name for t in server._tool_manager.list_tools()} == {"read_tool"}


def test_enforce_read_only_keeps_read_tools_callable():
    """Surviving read tools must still be present and callable, not just listed."""
    server = _server_with_one_tool_per_bucket()
    enforce_read_only(server)
    assert server._tool_manager.get_tool("read_tool") is not None


# --- apply_startup_policy (shared by stdio + --http paths, F1) ---


def test_apply_startup_policy_prunes_when_read_only():
    """The --http path calls this eagerly; read-only default must prune writes."""
    from pexip_mcp.config import PexipSettings
    from pexip_mcp.mcp_app import apply_startup_policy

    server = _server_with_one_tool_per_bucket()
    settings = PexipSettings(host="h", username="u", password="p")  # read_only defaults True
    apply_startup_policy(server, settings)
    assert {t.name for t in server._tool_manager.list_tools()} == {"read_tool"}


def test_apply_startup_policy_keeps_writes_when_disabled():
    from pexip_mcp.config import PexipSettings
    from pexip_mcp.mcp_app import apply_startup_policy

    server = _server_with_one_tool_per_bucket()
    settings = PexipSettings(host="h", username="u", password="p", read_only=False)
    apply_startup_policy(server, settings)
    # All five buckets remain callable when writes are explicitly enabled.
    assert len(server._tool_manager.list_tools()) == 5


# --- platform-lifecycle gate (PEXIP_ALLOW_PLATFORM_TOOLS) ---


def _server_with_platform_and_normal_tools() -> FastMCP:
    """Build a server with one platform-lifecycle tool and one ordinary control tool."""
    server = FastMCP("test-platform")

    @server.tool(annotations=control("backup restore"))
    async def backup_restore(ctx: Context) -> dict:  # name matches PLATFORM_TOOLS
        return {}

    @server.tool(annotations=control("mute participant"))
    async def mute_participant(ctx: Context) -> dict:  # ordinary control, not platform
        return {}

    @server.tool(annotations=read("list vmrs"))
    async def list_vmrs(ctx: Context) -> dict:
        return {}

    return server


def test_enforce_platform_gate_removes_only_platform_tools():
    from pexip_mcp.mcp_app import enforce_platform_gate

    server = _server_with_platform_and_normal_tools()
    removed = enforce_platform_gate(server)
    assert removed == ["backup_restore"]
    remaining = {t.name for t in server._tool_manager.list_tools()}
    assert remaining == {"mute_participant", "list_vmrs"}


def test_platform_tools_gated_by_default_when_writes_enabled():
    from pexip_mcp.config import PexipSettings
    from pexip_mcp.mcp_app import apply_startup_policy

    server = _server_with_platform_and_normal_tools()
    settings = PexipSettings(host="h", username="u", password="p", read_only=False)
    apply_startup_policy(server, settings)
    names = {t.name for t in server._tool_manager.list_tools()}
    assert "backup_restore" not in names  # platform gated off by default
    assert {"mute_participant", "list_vmrs"} <= names  # ordinary tools remain


def test_platform_tools_exposed_when_allowed():
    from pexip_mcp.config import PexipSettings
    from pexip_mcp.mcp_app import apply_startup_policy

    server = _server_with_platform_and_normal_tools()
    settings = PexipSettings(
        host="h", username="u", password="p", read_only=False, allow_platform_tools=True
    )
    apply_startup_policy(server, settings)
    names = {t.name for t in server._tool_manager.list_tools()}
    assert "backup_restore" in names


def test_platform_tools_default_gated_in_config(clean_env):
    from pexip_mcp.config import PexipSettings

    assert PexipSettings(host="h", username="u", password="p").allow_platform_tools is False


# ── Platform gate against prefixed names and legacy aliases ──────────────────


def _prefixed_server(monkeypatch=None, legacy: bool = False):
    """A PexipMCP instance (the class the real server uses), so tools register
    under pexip_* names exactly as in production, optionally with aliases."""
    from pexip_mcp.mcp_app import PexipMCP

    if monkeypatch is not None:
        monkeypatch.setenv("PEXIP_LEGACY_TOOL_NAMES", "true" if legacy else "false")
    server = PexipMCP("t")

    @server.tool(annotations=control("Restore platform backup", idempotent=False))
    async def backup_restore(ctx: Context, backup_id: int) -> dict:  # pragma: no cover
        return {}

    @server.tool(annotations=control("Trigger platform upgrade", idempotent=False))
    async def platform_upgrade(ctx: Context) -> dict:  # pragma: no cover
        return {}

    @server.tool(annotations=control("Lock a conference"))
    async def lock_conference(ctx: Context, conference: str) -> dict:  # pragma: no cover
        return {}

    @server.tool(annotations=read("List VMRs"))
    async def list_vmrs(ctx: Context) -> dict:  # pragma: no cover
        return {}

    return server


def test_platform_gate_matches_prefixed_names():
    server = _prefixed_server()
    names = {t.name for t in server._tool_manager.list_tools()}
    assert "pexip_backup_restore" in names  # registered under the published name
    removed = enforce_platform_gate(server)
    assert removed == ["pexip_backup_restore", "pexip_platform_upgrade"]
    remaining = {t.name for t in server._tool_manager.list_tools()}
    assert remaining == {"pexip_lock_conference", "pexip_list_vmrs"}


def test_platform_gate_removes_legacy_aliases_too(monkeypatch):
    server = _prefixed_server(monkeypatch, legacy=True)
    names = {t.name for t in server._tool_manager.list_tools()}
    assert {"backup_restore", "pexip_backup_restore"} <= names
    removed = enforce_platform_gate(server)
    assert set(removed) == {
        "backup_restore",
        "pexip_backup_restore",
        "platform_upgrade",
        "pexip_platform_upgrade",
    }


def test_platform_gate_on_the_real_catalog_names():
    """Belt and braces: every PLATFORM_TOOLS entry names a tool that actually exists
    in the real registry under its published name."""
    from pexip_mcp.mcp_app import PLATFORM_TOOLS, TOOL_PREFIX, mcp

    import pexip_mcp.server  # noqa: F401

    registered = {t.name for t in mcp._tool_manager.list_tools()}
    missing = {f"{TOOL_PREFIX}{n}" for n in PLATFORM_TOOLS} - registered
    assert not missing, missing
