"""Catalog quality lint: the Glama rubric and the Claude Connectors Directory
pre-submission checklist, made executable.

Each test asserts one property of EVERY registered tool. Properties the current
catalog does not yet satisfy are marked xfail(strict=True): they document the
phase-1 acceptance criteria in docs/TOOL-ARCHITECTURE-PLAN.md and will start
failing-as-XPASS (which strict turns into a real failure) the moment the work
lands, at which point the xfail marker is removed. Nothing here changes runtime
behaviour.

Rubric sources:
  - Glama: Tool Definition Quality (purpose clarity, usage guidelines, behavioral
    transparency, parameter semantics, conciseness, completeness) + Server
    Coherence (disambiguation, naming consistency, count, completeness).
  - Claude directory checklist: title + readOnlyHint/destructiveHint on every
    tool, names <= 64 chars, narrow accurate descriptions, no read/write mixing,
    API docs link on freeform-payload tools.
  - Anthropic "Writing tools for agents": service prefix, unambiguous parameter
    names, input examples for tools with many optional parameters.
"""

from __future__ import annotations

import pytest

from pexip_mcp.mcp_app import mcp

import pexip_mcp.server  # noqa: F401 — registers all tools
from evals.catalog import has_real_output_schema, near_duplicate_names

TOOLS = sorted(mcp._tool_manager.list_tools(), key=lambda t: t.name)
NAMES = [t.name for t in TOOLS]

# Tools whose payload is a freeform dict the model constructs. The directory
# requires such tools to name or link the target API in their description.
FREEFORM_PAYLOAD_PARAMS = {"settings", "filters", "updates"}
PEXIP_DOCS_MARKERS = ("docs.pexip.com", "Management API", "management API")


def _props(tool) -> dict:
    return (tool.parameters or {}).get("properties", {})


def _optional_count(tool) -> int:
    schema = tool.parameters or {}
    return len(schema.get("properties", {})) - len(schema.get("required", []))


# ── Already true today: these guard against regressions ─────────────────────


def test_every_tool_has_a_title():
    missing = [t.name for t in TOOLS if not (t.annotations and t.annotations.title)]
    assert not missing, missing


def test_every_tool_has_annotations():
    missing = [t.name for t in TOOLS if t.annotations is None]
    assert not missing, missing


def test_tool_names_are_snake_case_and_short():
    bad = [n for n in NAMES if len(n) > 64 or n != n.lower() or " " in n or "-" in n]
    assert not bad, bad


def test_every_tool_has_a_description():
    missing = [t.name for t in TOOLS if not (t.description or "").strip()]
    assert not missing, missing


def test_read_only_tools_are_not_destructive():
    bad = [
        t.name
        for t in TOOLS
        if t.annotations and t.annotations.readOnlyHint and t.annotations.destructiveHint
    ]
    assert not bad, bad


def test_no_tool_mixes_read_and_write_operations():
    """Directory rule: a catch-all tool with a method/op parameter spanning GET and
    POST/DELETE is rejected. Our generic CRUD is split per verb, so no tool should
    take a parameter that selects between reading and writing."""
    suspicious = []
    for t in TOOLS:
        for pname, pschema in _props(t).items():
            enum = set(pschema.get("enum", []) or [])
            if enum & {"get", "list", "read"} and enum & {"create", "update", "delete", "write"}:
                suspicious.append(f"{t.name}.{pname}")
    assert not suspicious, suspicious


def test_freeform_payload_tools_reference_pexip_api_docs():
    """Directory rule: tools that take a caller-constructed payload must name the API."""
    bad = []
    for t in TOOLS:
        if FREEFORM_PAYLOAD_PARAMS & set(_props(t)):
            desc = t.description or ""
            if not any(m in desc for m in PEXIP_DOCS_MARKERS):
                bad.append(t.name)
    # Today the generic CRUD tools say "Pexip configuration resource" but do not
    # link the Management API docs; tracked for phase 1.
    if bad:
        pytest.xfail(f"phase 1: add Management API doc reference to {bad}")


# ── Phase-1 acceptance criteria (xfail until the work lands) ────────────────


@pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="phase 1: every tool gets the pexip_ prefix"
)
def test_every_tool_has_service_prefix():
    bad = [n for n in NAMES if not n.startswith("pexip_")]
    assert not bad, bad


def test_every_non_read_tool_declares_destructive():
    bad = [
        t.name
        for t in TOOLS
        if t.annotations and not t.annotations.readOnlyHint and not t.annotations.destructiveHint
    ]
    assert not bad, bad


@pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="phase 1: description floor of 120 chars"
)
def test_descriptions_meet_length_floor():
    short = [t.name for t in TOOLS if len((t.description or "").strip()) < 120]
    assert not short, short


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="phase 3: describe_resources replaces inline registry",
)
def test_descriptions_meet_length_ceiling():
    long = [t.name for t in TOOLS if len(t.description or "") > 1500]
    assert not long, long


@pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="phase 1: 'Use when' guidance in every description"
)
def test_descriptions_state_when_to_use():
    bad = [t.name for t in TOOLS if "use when" not in (t.description or "").lower()]
    assert not bad, bad


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="phase 1: input_examples via tool meta for 4+ optional params",
)
def test_tools_with_many_optional_params_have_input_examples():
    bad = [
        t.name
        for t in TOOLS
        if _optional_count(t) >= 4 and not ((t.meta or {}).get("input_examples"))
    ]
    assert not bad, bad


@pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="phase 2: typed return models produce outputSchema"
)
def test_every_tool_has_output_schema():
    """FastMCP emits a bare {additionalProperties: true} object for dict[str, Any]
    returns; only a schema with declared properties counts."""
    bad = [t.name for t in TOOLS if not has_real_output_schema(t)]
    assert not bad, bad


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="phase 1: parameter names must not carry two meanings across tools "
    "(conference_id is a UUID in command tools and an int elsewhere)",
)
def test_parameter_names_have_one_type_across_catalog():
    seen: dict[str, set[str]] = {}
    for t in TOOLS:
        for pname, pschema in _props(t).items():
            if pname == "ctx":
                continue
            types = pschema.get("type")
            if types is None and "anyOf" in pschema:
                types = "/".join(sorted(s.get("type", "?") for s in pschema["anyOf"]))
            seen.setdefault(pname, set()).add(str(types))
    conflicts = {k: v for k, v in seen.items() if len(v) > 1}
    assert not conflicts, conflicts


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="phase 4: the Teams Connector node/call status tools fold into the generic "
    "status tools, which removes the only confusable pairs",
)
def test_no_near_duplicate_tool_names():
    """Glama disambiguation: names an agent could confuse. Conventional pairs
    (get_X/list_X, lock/unlock, mute/unmute) are excluded by the shared helper,
    so anything reported here is a real naming problem."""
    dupes = near_duplicate_names(NAMES)
    assert not dupes, dupes
