"""Scoring functions for eval results.

Each scorer compares actual tool selections / parameters against expected
values from the YAML eval cases and returns an EvalResult.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EvalResult:
    passed: bool
    score: float  # 0.0–1.0
    details: str = ""
    actual: list[str] = field(default_factory=list)
    expected: list[str] = field(default_factory=list)


def score_exact(actual_tools: list[str], expected_tools: list[str]) -> EvalResult:
    """All expected tools must appear, in any order, with no extras."""
    actual_set = set(actual_tools)
    expected_set = set(expected_tools)
    if actual_set == expected_set:
        return EvalResult(passed=True, score=1.0, actual=actual_tools, expected=expected_tools)
    missing = expected_set - actual_set
    extra = actual_set - expected_set
    parts = []
    if missing:
        parts.append(f"missing: {sorted(missing)}")
    if extra:
        parts.append(f"extra: {sorted(extra)}")
    matched = len(expected_set & actual_set)
    total = len(expected_set | actual_set)
    return EvalResult(
        passed=False,
        score=matched / total if total else 0.0,
        details="; ".join(parts),
        actual=actual_tools,
        expected=expected_tools,
    )


def score_subset(actual_tools: list[str], expected_tools: list[str]) -> EvalResult:
    """All expected tools must appear somewhere in actual (extras are OK)."""
    actual_set = set(actual_tools)
    expected_set = set(expected_tools)
    missing = expected_set - actual_set
    if not missing:
        return EvalResult(passed=True, score=1.0, actual=actual_tools, expected=expected_tools)
    matched = len(expected_set) - len(missing)
    return EvalResult(
        passed=False,
        score=matched / len(expected_set) if expected_set else 0.0,
        details=f"missing: {sorted(missing)}",
        actual=actual_tools,
        expected=expected_tools,
    )


def score_ordered_subset(actual_tools: list[str], expected_tools: list[str]) -> EvalResult:
    """Expected tools must appear in actual in the given order (gaps OK)."""
    idx = 0
    matched = []
    for tool in actual_tools:
        if idx < len(expected_tools) and tool == expected_tools[idx]:
            matched.append(tool)
            idx += 1
    if idx == len(expected_tools):
        return EvalResult(passed=True, score=1.0, actual=actual_tools, expected=expected_tools)
    missing = [t for t in expected_tools if t not in matched]
    return EvalResult(
        passed=False,
        score=len(matched) / len(expected_tools) if expected_tools else 0.0,
        details=f"matched {len(matched)}/{len(expected_tools)} in order; missing/out-of-order: {missing}",
        actual=actual_tools,
        expected=expected_tools,
    )


def score_any_of(actual_tools: list[str], expected_tools: list[str]) -> EvalResult:
    """At least one expected tool must appear — for prompts where several
    different tools are each a fully legitimate way to do the job."""
    hits = [t for t in expected_tools if t in actual_tools]
    if hits:
        return EvalResult(passed=True, score=1.0, actual=actual_tools, expected=expected_tools)
    return EvalResult(
        passed=False,
        score=0.0,
        details=f"none of {expected_tools} called",
        actual=actual_tools,
        expected=expected_tools,
    )


def score_params(
    actual_params: dict,
    expected_params: dict | None = None,
    params_present: list[str] | None = None,
) -> EvalResult:
    """Check parameter values and presence."""
    issues = []

    if expected_params:
        for key, expected_val in expected_params.items():
            actual_val = actual_params.get(key)
            if actual_val is None:
                issues.append(f"missing param {key!r}")
            elif str(actual_val) != str(expected_val):
                issues.append(f"{key}: expected {expected_val!r}, got {actual_val!r}")

    if params_present:
        for key in params_present:
            if key not in actual_params:
                issues.append(f"param {key!r} not present")

    if not issues:
        return EvalResult(passed=True, score=1.0)

    total_checks = len(expected_params or {}) + len(params_present or [])
    return EvalResult(
        passed=False,
        score=(total_checks - len(issues)) / total_checks if total_checks else 0.0,
        details="; ".join(issues),
    )


SCORERS = {
    "exact": score_exact,
    "subset": score_subset,
    "ordered_subset": score_ordered_subset,
    "any_of": score_any_of,
}
