"""Tool selection evals — does the agent pick the right tool(s) for a prompt?

Layer 1 (deterministic, always runs):
  Validates that every YAML case references real tools from the registry.

Layer 2 (--llm flag):
  Sends each prompt to Claude with the full tool catalog and scores
  whether Claude picks the expected tool(s). The conversation runs for a few
  turns (mock results fed back) so that legitimate read-before-write
  protocols — e.g. get_resource_schema before create_resource — can complete
  before scoring. Cases may provide ``mock_returns`` (tool name -> payload)
  for intermediate calls; unlisted tools get ``{}``.
"""
from __future__ import annotations

import json

import pytest

from evals.conftest import EVAL_MODEL, case_ids, load_cases
from evals.scoring import SCORERS

CASES = load_cases("tool_selection.yaml")

MAX_TURNS = 4


# ---------------------------------------------------------------------------
# Layer 1: deterministic validation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case", CASES, ids=case_ids(CASES))
def test_expected_tools_exist_in_registry(case, tool_names):
    """Every expected/mocked tool in the YAML must exist in the MCP registry."""
    for tool in case["expected_tools"]:
        assert tool in tool_names, f"Tool {tool!r} from case {case['id']!r} not in registry"
    for tool in case.get("mock_returns", {}):
        assert tool in tool_names, f"Mocked tool {tool!r} in case {case['id']!r} not in registry"


@pytest.mark.parametrize("case", CASES, ids=case_ids(CASES))
def test_match_type_is_valid(case, tool_registry):
    """match must be one of the supported scoring modes."""
    assert case["match"] in SCORERS, f"Unknown match type {case['match']!r} in case {case['id']!r}"


# ---------------------------------------------------------------------------
# Layer 2: LLM-scored eval
# ---------------------------------------------------------------------------

@pytest.mark.llm
@pytest.mark.parametrize("case", CASES, ids=case_ids(CASES))
def test_claude_selects_correct_tools(case, claude_client, claude_tools):
    """Run a short multi-turn conversation and score the tool selection."""
    scorer = SCORERS[case["match"]]
    mock_returns = case.get("mock_returns", {})
    messages = [{"role": "user", "content": case["prompt"]}]
    actual_tools: list[str] = []
    result = scorer(actual_tools, case["expected_tools"])

    for _turn in range(MAX_TURNS):
        response = claude_client.messages.create(
            model=EVAL_MODEL,
            max_tokens=1024,
            system=(
                "You are a Pexip Infinity management assistant. "
                "The current date and time is 2026-07-02T12:00:00 UTC — use it to "
                "resolve relative ranges like 'today', 'this week', or 'this month'. "
                "Use the available tools to fulfill requests. "
                "Always use tools — never answer from memory."
            ),
            tools=claude_tools,
            messages=messages,
        )

        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if not tool_uses:
            break

        actual_tools.extend(tu.name for tu in tool_uses)
        result = scorer(actual_tools, case["expected_tools"])
        # Stop as soon as the expectation is met so extra turns can't turn an
        # exact-match pass back into a failure.
        if result.passed:
            break

        messages.append({"role": "assistant", "content": response.content})
        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": json.dumps(mock_returns.get(tu.name, {})),
                }
                for tu in tool_uses
            ],
        })

    assert result.passed, (
        f"Case {case['id']!r}: {result.details}\n"
        f"  Expected: {case['expected_tools']}\n"
        f"  Actual:   {actual_tools}"
    )
