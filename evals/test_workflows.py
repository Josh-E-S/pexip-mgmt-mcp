"""Multi-step workflow evals — can the agent chain tools correctly?

Layer 1 (deterministic, always runs):
  Validates that every step references a real tool and that params_contain
  keys match the tool's signature.

Layer 2 (--llm flag):
  Runs a simulated multi-turn conversation: sends the prompt, gets a tool_use
  response, feeds the mock return back, and checks the full chain.
"""
from __future__ import annotations

import json

import pytest

from evals.conftest import EVAL_MODEL, case_ids, load_cases

CASES = load_cases("workflows.yaml")


# ---------------------------------------------------------------------------
# Layer 1: deterministic validation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case", CASES, ids=case_ids(CASES))
def test_workflow_tools_exist(case, tool_names):
    """Every tool referenced in a workflow step must exist in the registry."""
    for step in case["steps"]:
        assert step["tool"] in tool_names, (
            f"Tool {step['tool']!r} in workflow {case['id']!r} not in registry"
        )


@pytest.mark.parametrize("case", CASES, ids=case_ids(CASES))
def test_workflow_params_are_valid(case, tool_registry):
    """params_contain keys must match actual tool parameter names."""
    for step in case["steps"]:
        tool_info = tool_registry.get(step["tool"])
        if not tool_info:
            continue
        tool_params = set(tool_info["params"].keys())
        for param_key in step.get("params_contain", {}):
            assert param_key in tool_params, (
                f"Param {param_key!r} not in {step['tool']} signature "
                f"(has: {sorted(tool_params)}), workflow {case['id']!r}"
            )


@pytest.mark.parametrize("case", CASES, ids=case_ids(CASES))
def test_workflow_has_at_least_two_steps(case, tool_registry):
    """A workflow must have at least 2 steps to be a meaningful chain test."""
    assert len(case["steps"]) >= 2, (
        f"Workflow {case['id']!r} has only {len(case['steps'])} step(s)"
    )


# ---------------------------------------------------------------------------
# Layer 2: LLM-scored multi-turn simulation
# ---------------------------------------------------------------------------

def _match_step(steps: list[dict], step_idx: int, tool_name: str) -> int | None:
    """Find the step this call satisfies, skipping over unmatched optional steps.

    Since the server resolves names to UUIDs itself, lookup steps (e.g.
    list_active_conferences before a command) are legitimate but no longer
    required — cases mark them ``optional: true`` and the matcher accepts
    either path. Returns the matched step index, or None if the call matches
    nothing reachable (a required step blocks further look-ahead).
    """
    for j in range(step_idx, len(steps)):
        if steps[j]["tool"] == tool_name:
            return j
        if not steps[j].get("optional"):
            return None
    return None


def _check_params(case_id: str, step_idx: int, step: dict, tool_input: dict) -> None:
    """Assert each params_contain entry; a list value means any-of.

    Name resolution means a param may legitimately be either the mocked UUID
    or the human name from the prompt — cases list both acceptable values.
    """
    for key, val in (step.get("params_contain") or {}).items():
        actual_val = tool_input.get(key)
        if actual_val is None:
            continue
        accepted = [str(v) for v in (val if isinstance(val, list) else [val])]
        assert str(actual_val) in accepted, (
            f"Workflow {case_id!r} step {step_idx}: {key}={actual_val!r}, "
            f"expected one of {accepted}"
        )


@pytest.mark.llm
@pytest.mark.parametrize("case", CASES, ids=case_ids(CASES))
def test_claude_chains_tools_correctly(case, claude_client, claude_tools):
    """Simulate a multi-turn conversation and verify the tool chain."""
    messages = [{"role": "user", "content": case["prompt"]}]
    steps = case["steps"]
    matched_steps = []
    call_trace = []
    step_idx = 0
    max_turns = len(steps) + 5  # allow some slack

    for _turn in range(max_turns):
        response = claude_client.messages.create(
            model=EVAL_MODEL,
            max_tokens=1024,
            system=(
                "You are a Pexip Infinity management assistant. "
                "The current date and time is 2026-07-02T12:00:00 UTC — use it to "
                "resolve relative ranges like 'today', 'this week', or 'this month'. "
                "Use tools to fulfill the request step by step. "
                "Always use tools — never answer from memory."
            ),
            tools=claude_tools,
            messages=messages,
        )

        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if not tool_uses:
            break

        tool_results = []
        for tool_use in tool_uses:
            call_trace.append(f"{tool_use.name}({json.dumps(tool_use.input)})")
            mock_return = {}
            j = _match_step(steps, step_idx, tool_use.name)
            if j is not None:
                step = steps[j]
                matched_steps.append(j)
                mock_return = step.get("returns", {})
                _check_params(case["id"], j, step, tool_use.input)
                step_idx = j + 1

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": json.dumps(mock_return),
            })

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

        # Stop once every remaining step is optional — the chain is complete.
        if all(s.get("optional") for s in steps[step_idx:]):
            break

    missed_required = [
        f"{k}:{steps[k]['tool']}"
        for k in range(len(steps))
        if not steps[k].get("optional") and k not in matched_steps
    ]
    assert not missed_required, (
        f"Workflow {case['id']!r}: required steps not matched: {missed_required}. "
        f"Matched indices: {matched_steps}. Actual calls:\n  " + "\n  ".join(call_trace)
    )
