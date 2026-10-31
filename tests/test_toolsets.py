"""Toolset selection: resolution of PEXIP_TOOLSETS, enforcement on a prefixed
registry, interaction with PEXIP_TOOLS / PEXIP_DENY_TOOLS, and the catalog
invariants (every tool in exactly one toolset, every toolset entry is a tool)."""

from __future__ import annotations

import pytest
from mcp.server.fastmcp import Context

from pexip_mcp.config import PexipSettings
from pexip_mcp.mcp_app import PexipMCP, TOOL_PREFIX, enforce_toolsets, is_legacy_alias, mcp
from pexip_mcp.tools._catalog import (
    DEFAULT_TOOLSETS,
    TOOLSET_OF,
    TOOLSETS,
    resolve_toolsets,
)
from pexip_mcp.tools._helpers import control, read

import pexip_mcp.server  # noqa: F401 — registers all tools


def _settings(**kw) -> PexipSettings:
    return PexipSettings(host="h", username="u", password="p", **kw)


# ── resolve_toolsets ─────────────────────────────────────────────────────────


def test_default_and_all_and_core_always_on():
    assert resolve_toolsets(None) == set(DEFAULT_TOOLSETS) | {"core"}
    assert resolve_toolsets("default") == resolve_toolsets("")
    assert resolve_toolsets("all") == set(TOOLSETS)
    assert resolve_toolsets("rooms") == {"core", "rooms"}
    assert "core" in resolve_toolsets("live")


def test_default_can_be_extended_and_names_are_case_insensitive():
    assert resolve_toolsets("default,dialplan") == set(DEFAULT_TOOLSETS) | {"core", "dialplan"}
    assert resolve_toolsets(" Rooms , LIVE ") == {"core", "rooms", "live"}


def test_unknown_toolset_fails_loudly():
    with pytest.raises(ValueError, match="Unknown toolset 'rooms2'"):
        resolve_toolsets("rooms2")


# ── catalog invariants ───────────────────────────────────────────────────────


def test_every_registered_tool_belongs_to_exactly_one_toolset():
    registered = {
        t.name.removeprefix(TOOL_PREFIX)
        for t in mcp._tool_manager.list_tools()
        if not is_legacy_alias(t)
    }
    missing = registered - set(TOOLSET_OF)
    assert not missing, f"Add to tools/_catalog.py TOOLSETS: {sorted(missing)}"
    seen: dict[str, str] = {}
    for ts in TOOLSETS.values():
        for tool in ts.tools:
            assert tool not in seen, f"{tool} is in both {seen[tool]} and {ts.name}"
            seen[tool] = ts.name


def test_every_toolset_entry_is_a_registered_tool():
    registered = {t.name.removeprefix(TOOL_PREFIX) for t in mcp._tool_manager.list_tools()}
    stale = set(TOOLSET_OF) - registered
    assert not stale, f"Remove from tools/_catalog.py (no such tool): {sorted(stale)}"


def test_registered_tools_carry_their_toolset_in_meta():
    for t in mcp._tool_manager.list_tools():
        if is_legacy_alias(t):
            continue
        assert (t.meta or {}).get("toolset") == TOOLSET_OF[t.name.removeprefix(TOOL_PREFIX)]


def test_platform_toolset_is_off_by_default_and_dialplan_too():
    assert not TOOLSETS["platform"].default
    assert not TOOLSETS["dialplan"].default
    for name in ("core", "rooms", "live", "health", "history", "config", "directory"):
        assert TOOLSETS[name].default


# ── enforce_toolsets on a prefixed registry ──────────────────────────────────


def _server() -> PexipMCP:
    server = PexipMCP("t")

    @server.tool(annotations=read("List VMRs"))
    async def list_vmrs(ctx: Context) -> dict:  # pragma: no cover
        return {}

    @server.tool(annotations=control("Lock a conference"))
    async def lock_conference(ctx: Context, conference: str) -> dict:  # pragma: no cover
        return {}

    @server.tool(annotations=read("List gateway rules"))
    async def list_gateway_rules(ctx: Context) -> dict:  # pragma: no cover
        return {}

    @server.tool(annotations=control("Create platform backup"))
    async def backup_create(ctx: Context) -> dict:  # pragma: no cover
        return {}

    @server.tool(annotations=read("Describe resources"))
    async def describe_resources(ctx: Context) -> dict:  # pragma: no cover
        return {}

    return server


def _names(server) -> set[str]:
    return {t.name for t in server._tool_manager.list_tools()}


def test_default_selection_drops_dialplan_and_platform():
    server = _server()
    enabled, removed = enforce_toolsets(server, _settings())
    assert "dialplan" not in enabled and "platform" not in enabled
    assert removed == ["pexip_backup_create", "pexip_list_gateway_rules"]
    assert _names(server) == {
        "pexip_list_vmrs",
        "pexip_lock_conference",
        "pexip_describe_resources",
    }


def test_explicit_tools_add_back_and_deny_wins():
    server = _server()
    enforce_toolsets(
        server,
        _settings(
            tools="list_gateway_rules, pexip_backup_create", deny_tools="pexip_lock_conference"
        ),
    )
    assert _names(server) == {
        "pexip_list_vmrs",
        "pexip_list_gateway_rules",
        "pexip_backup_create",
        "pexip_describe_resources",
    }


def test_all_keeps_everything_and_is_idempotent():
    server = _server()
    enabled, removed = enforce_toolsets(server, _settings(toolsets="all"))
    assert removed == [] and enabled == set(TOOLSETS)
    enabled2, removed2 = enforce_toolsets(server, _settings(toolsets="all"))
    assert removed2 == []


def test_unknown_tool_is_kept_not_hidden(caplog):
    server = _server()

    @server.tool(annotations=read("Brand new"))
    async def brand_new_tool(ctx: Context) -> dict:  # pragma: no cover
        return {}

    with caplog.at_level("WARNING"):
        enforce_toolsets(server, _settings(toolsets="rooms"))
    assert "pexip_brand_new_tool" in _names(server)
    assert "belongs to no toolset" in caplog.text


def test_startup_policy_applies_toolsets_on_a_real_shaped_registry(monkeypatch):
    """apply_startup_policy runs toolset enforcement after read-only / platform gates."""
    from pexip_mcp.mcp_app import apply_startup_policy

    server = _server()
    apply_startup_policy(
        server, _settings(read_only=False, allow_platform_tools=True, toolsets="rooms,platform")
    )
    assert _names(server) == {"pexip_list_vmrs", "pexip_backup_create", "pexip_describe_resources"}


def test_platform_gate_set_is_defined_once_inside_the_platform_toolset():
    from pexip_mcp.mcp_app import PLATFORM_TOOLS
    from pexip_mcp.tools._catalog import PLATFORM_GATED

    assert PLATFORM_TOOLS is PLATFORM_GATED
    assert PLATFORM_GATED <= TOOLSETS["platform"].tools
