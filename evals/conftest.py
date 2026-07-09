"""Eval suite fixtures — tool registry, mock/live clients, CLI flags.

The eval suite tests how well an LLM agent selects and parameterizes
the pexip-mgmt-mcp tools. It operates in two layers:

  Layer 1 (deterministic, default): validates that YAML eval cases
  reference real tools with correct parameter names. No LLM needed.

  Layer 2 (--llm flag): sends prompts to Claude with the full tool
  catalog and scores actual tool selection against expectations.

  --live flag: runs integration tests against a real Pexip node.
"""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import pytest_asyncio
import yaml
from dotenv import load_dotenv

from pexip_mcp.client import PexipClient

# Load .env into the process environment so the whole eval suite reads from a
# single file: Pexip creds (PEXIP_*), ANTHROPIC_API_KEY, PEXIP_EVAL_MODEL, and
# PEXIP_EVAL_DIAL_TARGET. Real environment variables still win (override=False),
# so an inline `ANTHROPIC_API_KEY=... uv run pytest` overrides the .env value.
load_dotenv(Path(__file__).parent.parent / ".env", override=False)

PEXIP_HOST = "manager.example.com"
CASES_DIR = Path(__file__).parent / "cases"

# Model used for --llm scoring. Override with PEXIP_EVAL_MODEL to test a
# different/newer model without editing the test files. Kept as a single
# source of truth so all three LLM test modules stay in sync.
EVAL_MODEL = os.environ.get("PEXIP_EVAL_MODEL", "claude-sonnet-5")


# ---------------------------------------------------------------------------
# CLI flags
# ---------------------------------------------------------------------------

def pytest_addoption(parser):
    parser.addoption("--llm", action="store_true", default=False, help="Run LLM-scored evals (needs ANTHROPIC_API_KEY)")
    parser.addoption("--live", action="store_true", default=False, help="Run integration tests against the live Pexip lab node")


def pytest_configure(config):
    config.addinivalue_line("markers", "llm: requires --llm flag and ANTHROPIC_API_KEY")
    config.addinivalue_line("markers", "live: requires --live flag and Pexip credentials")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--llm"):
        skip_llm = pytest.mark.skip(reason="needs --llm flag")
        for item in items:
            if "llm" in item.keywords:
                item.add_marker(skip_llm)
    if not config.getoption("--live"):
        skip_live = pytest.mark.skip(reason="needs --live flag")
        for item in items:
            if "live" in item.keywords:
                item.add_marker(skip_live)


# ---------------------------------------------------------------------------
# Tool registry — the full tool catalog, built by importing the server
# ---------------------------------------------------------------------------

def _build_tool_registry() -> dict[str, dict[str, Any]]:
    """Import the MCP server (triggering tool registration) and extract the catalog."""
    from pexip_mcp.mcp_app import mcp

    import pexip_mcp.server  # noqa: F401 — side-effect: registers all tools

    registry = {}
    for tool in mcp._tool_manager.list_tools():
        params = {}
        schema = tool.parameters
        if schema and "properties" in schema:
            for pname, pschema in schema["properties"].items():
                ptype = pschema.get("type", "any")
                if "anyOf" in pschema:
                    ptype = "/".join(s.get("type", "?") for s in pschema["anyOf"])
                params[pname] = {
                    "type": ptype,
                    "required": pname in schema.get("required", []),
                }
        registry[tool.name] = {
            "description": tool.description or "",
            "params": params,
            "annotations": tool.annotations,
        }
    return registry


@pytest.fixture(scope="session")
def tool_registry() -> dict[str, dict[str, Any]]:
    return _build_tool_registry()


@pytest.fixture(scope="session")
def tool_names(tool_registry) -> set[str]:
    return set(tool_registry.keys())


# ---------------------------------------------------------------------------
# Claude API tools format — converts registry to Anthropic API tool schema
# ---------------------------------------------------------------------------

def _registry_to_claude_tools(registry: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert the MCP tool registry to the Anthropic API tools format."""
    from pexip_mcp.mcp_app import mcp

    import pexip_mcp.server  # noqa: F401

    tools = []
    for tool in mcp._tool_manager.list_tools():
        tool_def = {
            "name": tool.name,
            "description": tool.description or "",
            "input_schema": tool.parameters or {"type": "object", "properties": {}},
        }
        tools.append(tool_def)
    # The catalog is ~36k tokens and identical for every request in a run.
    # Caching it turns all but the first request's tool block into cache reads
    # (10% of the input price) — without this a full --llm run costs ~10x more.
    if tools:
        tools[-1]["cache_control"] = {"type": "ephemeral"}
    return tools


@pytest.fixture(scope="session")
def claude_tools(tool_registry) -> list[dict[str, Any]]:
    return _registry_to_claude_tools(tool_registry)


# ---------------------------------------------------------------------------
# Claude API client (gated on --llm)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def claude_client():
    try:
        import anthropic
    except ImportError:
        pytest.skip("anthropic SDK not installed — run: uv add --dev anthropic")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")
    return anthropic.Anthropic(api_key=api_key)


# ---------------------------------------------------------------------------
# Mock client / ctx — mirrors tests/conftest.py
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def mock_client():
    c = PexipClient(host=PEXIP_HOST, username="admin", password="password")
    try:
        yield c
    finally:
        await c.aclose()


@pytest.fixture
def mock_ctx(mock_client):
    return SimpleNamespace(
        request_context=SimpleNamespace(lifespan_context=SimpleNamespace(pexip=mock_client))
    )


# ---------------------------------------------------------------------------
# Live client (gated on --live)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="session")
async def live_client():
    from pexip_mcp.config import PexipSettings
    try:
        settings = PexipSettings()
    except Exception:
        pytest.skip("Pexip credentials not configured in .env")
    client = PexipClient.from_settings(settings)
    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture(scope="session")
def live_ctx(live_client):
    return SimpleNamespace(
        request_context=SimpleNamespace(lifespan_context=SimpleNamespace(pexip=live_client))
    )


# ---------------------------------------------------------------------------
# YAML case loading helpers
# ---------------------------------------------------------------------------

def load_cases(filename: str) -> list[dict[str, Any]]:
    path = CASES_DIR / filename
    with open(path) as f:
        return yaml.safe_load(f)


def case_ids(cases: list[dict[str, Any]]) -> list[str]:
    # Fold tags into the pytest id so persona/tag slices work with -k, e.g.
    # `-k operator` or `-k provisioning`. Without this the id is just the bare
    # case id and -k can't see the tags.
    ids = []
    for c in cases:
        tags = "-".join(c.get("tags", []))
        ids.append(f"{c['id']}-{tags}" if tags else c["id"])
    return ids
