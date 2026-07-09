"""Parameter correctness evals — does the agent pass the right field names and types?

Layer 1 (deterministic, always runs):
  Validates that expected params in YAML match the tool's actual signature.

Layer 2 (--llm flag):
  Sends the prompt to Claude and checks the tool_use input against
  expectations. The conversation runs for a few turns (mock results fed back)
  so that legitimate preparatory reads — e.g. get_resource_schema before
  create_resource — can complete before the expected call is scored. Cases
  may provide ``mock_returns`` (tool name -> payload) for those intermediate
  calls; unlisted tools get ``{}``.
"""
from __future__ import annotations

import json

import pytest

from evals.conftest import EVAL_MODEL, case_ids, load_cases
from evals.scoring import score_params

CASES = load_cases("parameters.yaml")

MAX_TURNS = 4


# ---------------------------------------------------------------------------
# Layer 1: deterministic validation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case", CASES, ids=case_ids(CASES))
def test_expected_tool_exists(case, tool_names):
    """The expected tool (and any mocked tools) must exist in the registry."""
    assert case["expected_tool"] in tool_names, (
        f"Tool {case['expected_tool']!r} from case {case['id']!r} not in registry"
    )
    for tool in case.get("mock_returns", {}):
        assert tool in tool_names, (
            f"Mocked tool {tool!r} in case {case['id']!r} not in registry"
        )


@pytest.mark.parametrize("case", CASES, ids=case_ids(CASES))
def test_expected_params_match_signature(case, tool_registry):
    """Every expected param key must be a real parameter of the tool."""
    tool_info = tool_registry[case["expected_tool"]]
    tool_params = set(tool_info["params"].keys())
    for param_key in case.get("expected_params", {}):
        assert param_key in tool_params, (
            f"Param {param_key!r} not in {case['expected_tool']} signature "
            f"(has: {sorted(tool_params)}), case {case['id']!r}"
        )
    for param_key in case.get("params_present", []):
        assert param_key in tool_params, (
            f"Param {param_key!r} not in {case['expected_tool']} signature "
            f"(has: {sorted(tool_params)}), case {case['id']!r}"
        )


# ---------------------------------------------------------------------------
# Layer 2: LLM-scored eval
# ---------------------------------------------------------------------------

@pytest.mark.llm
@pytest.mark.parametrize("case", CASES, ids=case_ids(CASES))
def test_claude_passes_correct_params(case, claude_client, claude_tools):
    """Converse until the expected tool is called, then verify its params."""
    mock_returns = case.get("mock_returns", {})
    messages = [{"role": "user", "content": case["prompt"]}]
    all_calls: list[str] = []
    target_use = None

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

        all_calls.extend(tu.name for tu in tool_uses)
        target_use = next(
            (tu for tu in tool_uses if tu.name == case["expected_tool"]), None
        )
        if target_use is not None:
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

    assert all_calls, f"Case {case['id']!r}: Claude returned no tool calls"
    assert target_use is not None, (
        f"Case {case['id']!r}: expected {case['expected_tool']!r}, "
        f"got {all_calls}"
    )

    result = score_params(
        target_use.input,
        case.get("expected_params"),
        case.get("params_present"),
    )
    assert result.passed, (
        f"Case {case['id']!r}: {result.details}\n"
        f"  Actual params: {target_use.input}"
    )
