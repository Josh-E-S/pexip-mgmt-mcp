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

from evals.catalog import DEFAULT_EVAL_MODEL, registry_to_api_tools

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
EVAL_MODEL = DEFAULT_EVAL_MODEL


# ---------------------------------------------------------------------------
# CLI flags
# ---------------------------------------------------------------------------


def pytest_addoption(parser):
    parser.addoption(
        "--llm",
        action="store_true",
        default=False,
        help="Run LLM-scored evals (needs ANTHROPIC_API_KEY)",
    )
    parser.addoption(
        "--live",
        action="store_true",
        default=False,
        help="Run integration tests against the live Pexip lab node",
    )


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
    """Convert the MCP tool registry to the Anthropic API tools format.

    The catalog is ~36k tokens and identical for every request in a run.
    cache_last=True puts a prompt-cache breakpoint on the final tool so all but
    the first request read it from cache (10% of the input price); without it a
    full --llm run costs ~10x more. UsageRecorder below verifies the hit rate.
    """
    from pexip_mcp.mcp_app import mcp

    import pexip_mcp.server  # noqa: F401

    return registry_to_api_tools(mcp._tool_manager.list_tools(), cache_last=True)


@pytest.fixture(scope="session")
def claude_tools(tool_registry) -> list[dict[str, Any]]:
    return _registry_to_claude_tools(tool_registry)


# ---------------------------------------------------------------------------
# Claude API client (gated on --llm)
# ---------------------------------------------------------------------------


class UsageRecorder:
    """Accumulates token usage across every Messages API call in a run.

    Exists to prove the prompt cache is working: the ~36k-token tool catalog
    carries a cache_control breakpoint (see _registry_to_claude_tools), so after
    the first request every call should report cache_read_input_tokens roughly
    equal to the catalog size. If that stops happening (breakpoint removed, tool
    list mutated between calls, TTL expired on a slow run) the cost of a --llm
    run jumps ~10x. The terminal summary makes that visible on every run, and
    PEXIP_EVAL_USAGE_JSON=path writes the raw numbers for the scorecard.
    """

    # Minimum share of requests (after the first) that must read from cache
    # before the summary is flagged. Under this, something is wrong with caching.
    MIN_CACHE_HIT_RATE = 0.8

    def __init__(self) -> None:
        self.requests = 0
        self.input_tokens = 0
        self.cache_creation_input_tokens = 0
        self.cache_read_input_tokens = 0
        self.output_tokens = 0
        # Requests after the first that read from cache. The first request can
        # at best hit a cache warmed by a previous run, so it is excluded from
        # the hit-rate denominator and numerator alike.
        self.cache_hits_after_first = 0
        # Per-test accounting for the scorecard: nodeid -> counters. `current_case`
        # is set by the autouse fixture below for the duration of each test.
        self.current_case: str | None = None
        self.cases: dict[str, dict[str, int]] = {}

    def record(self, usage: Any, tool_calls: int = 0) -> None:
        if self.current_case is not None:
            c = self.cases.setdefault(
                self.current_case,
                {"requests": 0, "tool_calls": 0, "input_tokens": 0, "output_tokens": 0},
            )
            c["requests"] += 1
            c["tool_calls"] += tool_calls
            c["input_tokens"] += (
                (getattr(usage, "input_tokens", 0) or 0)
                + (getattr(usage, "cache_creation_input_tokens", 0) or 0)
                + (getattr(usage, "cache_read_input_tokens", 0) or 0)
            )
            c["output_tokens"] += getattr(usage, "output_tokens", 0) or 0
        self.requests += 1
        self.input_tokens += getattr(usage, "input_tokens", 0) or 0
        self.output_tokens += getattr(usage, "output_tokens", 0) or 0
        created = getattr(usage, "cache_creation_input_tokens", 0) or 0
        read = getattr(usage, "cache_read_input_tokens", 0) or 0
        self.cache_creation_input_tokens += created
        self.cache_read_input_tokens += read
        if read > 0 and self.requests > 1:
            self.cache_hits_after_first += 1

    @property
    def hit_rate(self) -> float | None:
        """Share of requests after the first that read from cache; None if only one request."""
        eligible = self.requests - 1
        if eligible <= 0:
            return None
        return self.cache_hits_after_first / eligible

    def as_dict(self) -> dict[str, Any]:
        return {
            "model": EVAL_MODEL,
            "requests": self.requests,
            "input_tokens_uncached": self.input_tokens,
            "cache_creation_input_tokens": self.cache_creation_input_tokens,
            "cache_read_input_tokens": self.cache_read_input_tokens,
            "output_tokens": self.output_tokens,
            "cache_hit_rate": None if self.hit_rate is None else round(self.hit_rate, 3),
        }

    def summary_lines(self) -> list[str]:
        if not self.requests:
            return []
        d = self.as_dict()
        total_in = (
            d["input_tokens_uncached"]
            + d["cache_creation_input_tokens"]
            + d["cache_read_input_tokens"]
        )
        read_share = d["cache_read_input_tokens"] / total_in if total_in else 0.0
        rate = self.hit_rate
        rate_str = "n/a (single request)" if rate is None else f"{rate:.0%}"
        lines = [
            f"LLM eval usage ({EVAL_MODEL}): {d['requests']} requests, "
            f"{total_in:,} input tokens of which {d['cache_read_input_tokens']:,} "
            f"({read_share:.0%}) were cache reads; "
            f"{d['output_tokens']:,} output tokens; "
            f"cache hit rate {rate_str}",
        ]
        if rate is not None and rate < self.MIN_CACHE_HIT_RATE:
            lines.append(
                "WARNING: prompt cache hit rate is below "
                f"{self.MIN_CACHE_HIT_RATE:.0%}. Check that the tool catalog still "
                "carries cache_control (evals/catalog.registry_to_api_tools) and is "
                "byte-identical across requests; this run cost ~10x more than it should."
            )
        return lines


USAGE = UsageRecorder()


@pytest.fixture(scope="session")
def claude_client():
    """Anthropic client whose messages.create records token usage into USAGE."""
    try:
        import anthropic
    except ImportError:
        pytest.skip("anthropic SDK not installed — run: uv add --dev anthropic")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")
    client = anthropic.Anthropic(api_key=api_key)

    original_create = client.messages.create

    def recording_create(*args: Any, **kwargs: Any):
        response = original_create(*args, **kwargs)
        usage = getattr(response, "usage", None)
        if usage is not None:
            tool_calls = sum(
                1 for b in getattr(response, "content", []) if getattr(b, "type", "") == "tool_use"
            )
            USAGE.record(usage, tool_calls=tool_calls)
        return response

    client.messages.create = recording_create  # type: ignore[method-assign]
    return client


# ---------------------------------------------------------------------------
# Scorecard: per-case outcomes for every LLM-graded test, aggregated by layer
# (tool_selection / parameters / workflows) and by case tag (persona). Written
# as JSON with PEXIP_EVAL_SCORECARD_JSON=path; this is the artifact the
# architecture plan's before/after comparisons are made on.
# ---------------------------------------------------------------------------

SCORECARD: dict[str, dict[str, Any]] = {}  # nodeid -> {layer, case_id, tags, outcome}


@pytest.fixture(autouse=True)
def _track_current_case(request):
    USAGE.current_case = request.node.nodeid
    yield
    USAGE.current_case = None


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or "llm" not in item.keywords:
        return
    callspec = getattr(item, "callspec", None)
    case = (callspec.params.get("case") if callspec else None) or {}
    SCORECARD[item.nodeid] = {
        "layer": item.module.__name__.rsplit(".", 1)[-1].removeprefix("test_"),
        "case_id": case.get("id", item.name),
        "tags": list(case.get("tags", [])),
        "outcome": report.outcome,  # passed / failed / skipped
    }


def _accuracy(rows: list[dict[str, Any]]) -> dict[str, Any]:
    graded = [r for r in rows if r["outcome"] in ("passed", "failed")]
    passed = sum(1 for r in graded if r["outcome"] == "passed")
    return {
        "cases": len(graded),
        "passed": passed,
        "accuracy": round(passed / len(graded), 3) if graded else None,
    }


def build_scorecard() -> dict[str, Any]:
    rows = list(SCORECARD.values())
    by_layer = {
        layer: _accuracy([r for r in rows if r["layer"] == layer])
        for layer in sorted({r["layer"] for r in rows})
    }
    tags = sorted({t for r in rows for t in r["tags"]})
    by_tag = {t: _accuracy([r for r in rows if t in r["tags"]]) for t in tags}
    per_case = USAGE.cases
    graded_ids = [n for n, r in SCORECARD.items() if r["outcome"] in ("passed", "failed")]
    calls = [per_case[n]["tool_calls"] for n in graded_ids if n in per_case]
    toks = [
        per_case[n]["input_tokens"] + per_case[n]["output_tokens"]
        for n in graded_ids
        if n in per_case
    ]
    return {
        "model": EVAL_MODEL,
        "overall": _accuracy(rows),
        "by_layer": by_layer,
        "by_tag": by_tag,
        "per_task": {
            "mean_tool_calls": round(sum(calls) / len(calls), 2) if calls else None,
            "mean_total_tokens": int(sum(toks) / len(toks)) if toks else None,
        },
        "usage": USAGE.as_dict(),
        "cases": [{**SCORECARD[n], **per_case.get(n, {})} for n in SCORECARD],
    }


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Print cache/usage totals and the scorecard after an --llm run; optionally dump JSON."""
    import json

    lines = USAGE.summary_lines()
    if lines:
        terminalreporter.section("prompt cache / token usage")
        for line in lines:
            terminalreporter.write_line(line)
    out = os.environ.get("PEXIP_EVAL_USAGE_JSON")
    if out and lines:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(USAGE.as_dict(), indent=2) + "\n")
        terminalreporter.write_line(f"usage written to {out}")

    if not SCORECARD:
        return
    card = build_scorecard()
    terminalreporter.section("eval scorecard")
    o = card["overall"]
    terminalreporter.write_line(
        f"overall: {o['passed']}/{o['cases']} ({o['accuracy']})  "
        f"mean tool calls/task {card['per_task']['mean_tool_calls']}  "
        f"mean tokens/task {card['per_task']['mean_total_tokens']}"
    )
    for layer, a in card["by_layer"].items():
        terminalreporter.write_line(f"  {layer:16s} {a['passed']}/{a['cases']} ({a['accuracy']})")
    worst = sorted(
        ((t, a) for t, a in card["by_tag"].items() if a["accuracy"] is not None),
        key=lambda kv: kv[1]["accuracy"],
    )[:5]
    if worst:
        terminalreporter.write_line(
            "  weakest tags: " + ", ".join(f"{t} {a['accuracy']}" for t, a in worst)
        )
    out = os.environ.get("PEXIP_EVAL_SCORECARD_JSON")
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(card, indent=2) + "\n")
        terminalreporter.write_line(f"scorecard written to {out}")


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
