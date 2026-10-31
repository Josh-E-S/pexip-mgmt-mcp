"""Measure the MCP tool catalog: count, size in tokens, per-module breakdown, quality signals.

This is the phase-0 baseline instrument for docs/TOOL-ARCHITECTURE-PLAN.md. Run it
before and after any change to the tool surface and diff the JSON.

Usage:
    uv run python scripts/catalog_stats.py                 # human-readable summary
    uv run python scripts/catalog_stats.py --json out.json # also write the full report

Token counts: when ANTHROPIC_API_KEY is set, the catalog is measured with the
Messages count_tokens endpoint (exact for Claude). Otherwise a chars/3.5 estimate
is used and labelled as such in the output.

Honors PEXIP_READ_ONLY / PEXIP_ALLOW_PLATFORM_TOOLS so you can measure the catalog
a given deployment actually exposes; defaults here measure the FULL catalog.
"""
from __future__ import annotations

import argparse
import inspect
import json
import os
import statistics
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

CATEGORY_BY_MODULE = {"status": "Status", "history": "History", "command": "Command"}
CHARS_PER_TOKEN_ESTIMATE = 3.5


def _tool_defs() -> list[dict[str, Any]]:
    from pexip_mcp.mcp_app import apply_startup_policy, mcp

    import pexip_mcp.server  # noqa: F401 — registers all tools

    if os.environ.get("PEXIP_HOST"):
        from pexip_mcp.config import PexipSettings

        apply_startup_policy(mcp, PexipSettings())

    defs = []
    for tool in sorted(mcp._tool_manager.list_tools(), key=lambda t: t.name):
        module = inspect.getmodule(tool.fn).__name__.rsplit(".", 1)[-1]
        ann = tool.annotations
        defs.append(
            {
                "name": tool.name,
                "module": module,
                "category": CATEGORY_BY_MODULE.get(module, "Configuration"),
                "title": (ann.title if ann else None),
                "description": tool.description or "",
                "input_schema": tool.parameters or {"type": "object", "properties": {}},
                "read_only": bool(ann and ann.readOnlyHint),
                "destructive": bool(ann and ann.destructiveHint),
                "has_output_schema": False,  # FastMCP 1.x: dict[str, Any] returns yield none
            }
        )
    return defs


def _as_api_tools(defs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"name": d["name"], "description": d["description"], "input_schema": d["input_schema"]}
        for d in defs
    ]


def _estimate_tokens(obj: Any) -> int:
    return int(len(json.dumps(obj, separators=(",", ":"))) / CHARS_PER_TOKEN_ESTIMATE)


def _exact_tokens(tools: list[dict[str, Any]]) -> int | None:
    """Count tokens with the Anthropic API when a key is available; None otherwise."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
    except ImportError:
        return None
    client = anthropic.Anthropic()
    model = os.environ.get("PEXIP_EVAL_MODEL", "claude-sonnet-5")
    base = client.messages.count_tokens(
        model=model, messages=[{"role": "user", "content": "hi"}]
    ).input_tokens
    with_tools = client.messages.count_tokens(
        model=model, messages=[{"role": "user", "content": "hi"}], tools=tools
    ).input_tokens
    return with_tools - base


def _near_duplicates(names: list[str], threshold: float = 0.9) -> list[tuple[str, str, float]]:
    pairs = []
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            ratio = SequenceMatcher(None, a, b).ratio()
            if ratio >= threshold:
                pairs.append((a, b, round(ratio, 3)))
    return pairs


def build_report(defs: list[dict[str, Any]]) -> dict[str, Any]:
    api_tools = _as_api_tools(defs)
    exact = _exact_tokens(api_tools)
    est = _estimate_tokens(api_tools)

    by_module: dict[str, dict[str, Any]] = {}
    for d, t in zip(defs, api_tools):
        m = by_module.setdefault(d["module"], {"tools": 0, "est_tokens": 0, "category": d["category"]})
        m["tools"] += 1
        m["est_tokens"] += _estimate_tokens(t)

    by_category: dict[str, int] = {}
    for d in defs:
        by_category[d["category"]] = by_category.get(d["category"], 0) + 1

    desc_lens = [len(d["description"]) for d in defs]
    param_counts = [len(d["input_schema"].get("properties", {})) for d in defs]
    optional_counts = [
        len(d["input_schema"].get("properties", {})) - len(d["input_schema"].get("required", []))
        for d in defs
    ]

    heaviest = sorted(
        ({"name": d["name"], "est_tokens": _estimate_tokens(t)} for d, t in zip(defs, api_tools)),
        key=lambda x: -x["est_tokens"],
    )[:10]

    quality = {
        "missing_title": [d["name"] for d in defs if not d["title"]],
        "no_read_or_destructive_hint": [
            d["name"] for d in defs if not (d["read_only"] or d["destructive"])
        ],
        "description_under_120_chars": [d["name"] for d in defs if len(d["description"]) < 120],
        "description_over_1500_chars": [d["name"] for d in defs if len(d["description"]) > 1500],
        "no_service_prefix": [d["name"] for d in defs if not d["name"].startswith("pexip_")],
        "no_output_schema": sum(1 for d in defs if not d["has_output_schema"]),
        "four_plus_optional_params": [
            d["name"] for d, n in zip(defs, optional_counts) if n >= 4
        ],
        "near_duplicate_names": _near_duplicates([d["name"] for d in defs]),
    }

    return {
        "tool_count": len(defs),
        "by_category": by_category,
        "catalog_tokens": {
            "exact_anthropic": exact,
            "estimate_chars_div_3_5": est,
            "note": "exact uses messages.count_tokens when ANTHROPIC_API_KEY is set",
        },
        "by_module": dict(sorted(by_module.items(), key=lambda kv: -kv[1]["est_tokens"])),
        "heaviest_tools": heaviest,
        "description_chars": {
            "min": min(desc_lens),
            "median": int(statistics.median(desc_lens)),
            "max": max(desc_lens),
        },
        "params_per_tool": {
            "mean": round(statistics.mean(param_counts), 2),
            "max": max(param_counts),
        },
        "quality_signals": quality,
    }


def print_summary(r: dict[str, Any]) -> None:
    toks = r["catalog_tokens"]
    tok_str = (
        f"{toks['exact_anthropic']} (exact)"
        if toks["exact_anthropic"] is not None
        else f"~{toks['estimate_chars_div_3_5']} (estimate, set ANTHROPIC_API_KEY for exact)"
    )
    print(f"tools: {r['tool_count']}  {r['by_category']}")
    print(f"catalog tokens: {tok_str}")
    print("by module:")
    for m, v in r["by_module"].items():
        print(f"  {m:24s} {v['tools']:3d} tools  ~{v['est_tokens']:6d} tok")
    print("heaviest:", ", ".join(f"{h['name']}({h['est_tokens']})" for h in r["heaviest_tools"][:5]))
    d = r["description_chars"]
    print(f"description chars: min {d['min']} / median {d['median']} / max {d['max']}")
    q = r["quality_signals"]
    print("quality signals:")
    for k, v in q.items():
        n = v if isinstance(v, int) else len(v)
        print(f"  {k:32s} {n}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", type=Path, help="Write the full report to this file")
    args = ap.parse_args()

    report = build_report(_tool_defs())
    print_summary(report)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + "\n")
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
