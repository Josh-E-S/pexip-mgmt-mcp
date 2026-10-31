"""Shared catalog helpers used by the eval harness, the baseline script, and the
catalog quality tests. One implementation each, so the token count the baseline
reports is measured on exactly the tool list the --llm evals send.
"""

from __future__ import annotations

import os
import re
from difflib import SequenceMatcher
from typing import Any

# Model used for --llm scoring and exact token counting. Override with
# PEXIP_EVAL_MODEL so a newer model can be tried without editing code.
DEFAULT_EVAL_MODEL = os.environ.get("PEXIP_EVAL_MODEL", "claude-sonnet-5")

# Names at or above this SequenceMatcher ratio are treated as near-duplicates
# for Glama-style disambiguation checks, unless is_conventional_pair() applies.
# 0.88 is the lowest value that catches the Teams node/call status pairs while
# still only flagging get_X/list_X pairs that the conventional-pair rule excludes.
NEAR_DUPLICATE_THRESHOLD = 0.88


def registry_to_api_tools(tools: list[Any], *, cache_last: bool = False) -> list[dict[str, Any]]:
    """Convert FastMCP Tool objects to the Anthropic Messages API `tools` shape.

    When cache_last is True a prompt-cache breakpoint is placed on the final tool
    so the whole catalog is cached as one prefix block.
    """
    out = [
        {
            "name": t.name,
            "description": t.description or "",
            "input_schema": t.parameters or {"type": "object", "properties": {}},
        }
        for t in tools
    ]
    if cache_last and out:
        out[-1]["cache_control"] = {"type": "ephemeral"}
    return out


def has_real_output_schema(tool: Any) -> bool:
    """True when the tool's outputSchema describes fields, not just a bare object.

    FastMCP emits `{"type": "object", "additionalProperties": true}` for
    `dict[str, Any]` returns. That is technically an outputSchema but tells a
    client nothing, so it does not count.
    """
    schema = getattr(tool, "output_schema", None)
    return bool(schema and schema.get("properties"))


_VERB_PREFIX = re.compile(r"^(?:pexip_)?(get|list)_")


def is_conventional_pair(a: str, b: str) -> bool:
    """Pairs that look similar by design and never confuse an agent.

    - the get_X / list_X(s) pair for the same resource
    - an action and its un- inverse (lock/unlock, mute/unmute)
    """
    stem_a, stem_b = _VERB_PREFIX.sub("", a), _VERB_PREFIX.sub("", b)
    if a != b and (stem_a.rstrip("s") == stem_b.rstrip("s")):
        return True
    return (
        a == f"un{b}" or b == f"un{a}" or a.replace("_un", "_") == b or b.replace("_un", "_") == a
    )


def near_duplicate_names(
    names: list[str], threshold: float = NEAR_DUPLICATE_THRESHOLD
) -> list[tuple[str, str, float]]:
    """Return (a, b, ratio) for every non-conventional pair at or above threshold."""
    pairs = []
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            if is_conventional_pair(a, b):
                continue
            ratio = SequenceMatcher(None, a, b).ratio()
            if ratio >= threshold:
                pairs.append((a, b, round(ratio, 3)))
    return pairs
