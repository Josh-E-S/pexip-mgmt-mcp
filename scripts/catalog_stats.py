"""Measure the MCP tool catalog: count, size in tokens, per-module breakdown, quality signals.

This is the phase-0 baseline instrument for docs/TOOL-ARCHITECTURE-PLAN.md. Run it
before and after any change to the tool surface and diff the JSON.

Usage:
    uv run python scripts/catalog_stats.py                 # full catalog, summary
    uv run python scripts/catalog_stats.py --json out.json # also write the full report
    uv run python scripts/catalog_stats.py --as-deployed   # apply PEXIP_READ_ONLY etc.

By default the FULL catalog (every registered tool) is measured regardless of
environment. With --as-deployed the startup policy is applied from PEXIP_*
settings, so you measure what a given deployment actually exposes; this needs a
complete PexipSettings (host + credentials) in the environment.

Token counts: when ANTHROPIC_API_KEY is set, the catalog is measured with the
Messages count_tokens endpoint (exact for Claude). If that call fails for any
reason, or no key is set, a chars/3.5 estimate is used and labelled as such.
"""

from __future__ import annotations

import argparse
import inspect
import json
import os
import statistics
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from evals.catalog import (  # noqa: E402
    DEFAULT_EVAL_MODEL,
    has_real_output_schema,
    near_duplicate_names,
    registry_to_api_tools,
)

CATEGORY_BY_MODULE = {"status": "Status", "history": "History", "command": "Command"}
CHARS_PER_TOKEN_ESTIMATE = 3.5


def _tool_defs(*, as_deployed: bool = False) -> tuple[list[dict[str, Any]], list[Any]]:
    """Return (our per-tool records, the raw FastMCP Tool objects), sorted by name."""
    from pexip_mcp.mcp_app import apply_startup_policy, mcp

    import pexip_mcp.server  # noqa: F401 — registers all tools

    if as_deployed:
        from pexip_mcp.config import PexipSettings

        try:
            settings = PexipSettings()
        except Exception as e:  # noqa: BLE001 - config error is the user's to fix
            sys.exit(f"--as-deployed needs a complete PEXIP_* configuration: {e}")
        apply_startup_policy(mcp, settings)

    tools = sorted(mcp._tool_manager.list_tools(), key=lambda t: t.name)
    defs = []
    for tool in tools:
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
                "has_output_schema": has_real_output_schema(tool),
            }
        )
    return defs, tools


def _estimate_tokens(obj: Any) -> int:
    return int(len(json.dumps(obj, separators=(",", ":"))) / CHARS_PER_TOKEN_ESTIMATE)


def _exact_tokens(tools: list[dict[str, Any]]) -> tuple[int | None, str | None]:
    """Count tokens with the Anthropic API when a key is available.

    Returns (count, None) on success, (None, reason) when the exact count is not
    available so the caller can fall back to the estimate and say why.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None, "ANTHROPIC_API_KEY not set"
    try:
        import anthropic
    except ImportError:
        return None, "anthropic SDK not installed"
    try:
        client = anthropic.Anthropic()
        probe = [{"role": "user", "content": "hi"}]
        base = client.messages.count_tokens(model=DEFAULT_EVAL_MODEL, messages=probe).input_tokens
        with_tools = client.messages.count_tokens(
            model=DEFAULT_EVAL_MODEL, messages=probe, tools=tools
        ).input_tokens
        return with_tools - base, None
    except Exception as e:  # noqa: BLE001 - any API failure falls back to the estimate
        return None, f"count_tokens failed: {type(e).__name__}: {e}"


def build_report(
    defs: list[dict[str, Any]], tools: list[Any], *, as_deployed: bool
) -> dict[str, Any]:
    # Same conversion the --llm evals use (minus the cache breakpoint), so the
    # token count is measured on exactly what the harness sends.
    api_tools = registry_to_api_tools(tools)
    exact, exact_note = _exact_tokens(api_tools)
    est = _estimate_tokens(api_tools)

    by_module: dict[str, dict[str, Any]] = {}
    for d, t in zip(defs, api_tools):
        m = by_module.setdefault(
            d["module"], {"tools": 0, "est_tokens": 0, "category": d["category"]}
        )
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
        "four_plus_optional_params": [d["name"] for d, n in zip(defs, optional_counts) if n >= 4],
        "near_duplicate_names": near_duplicate_names([d["name"] for d in defs]),
    }

    return {
        "catalog_scope": "as_deployed (PEXIP_* policy applied)" if as_deployed else "full",
        "tool_count": len(defs),
        "by_category": by_category,
        "catalog_tokens": {
            "exact_anthropic": exact,
            "estimate_chars_div_3_5": est,
            "exact_unavailable_reason": exact_note,
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
        else f"~{toks['estimate_chars_div_3_5']} (estimate; exact unavailable: {toks['exact_unavailable_reason']})"
    )
    print(f"catalog: {r['catalog_scope']}")
    print(f"tools: {r['tool_count']}  {r['by_category']}")
    print(f"catalog tokens: {tok_str}")
    print("by module:")
    for m, v in r["by_module"].items():
        print(f"  {m:24s} {v['tools']:3d} tools  ~{v['est_tokens']:6d} tok")
    print(
        "heaviest:", ", ".join(f"{h['name']}({h['est_tokens']})" for h in r["heaviest_tools"][:5])
    )
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
    ap.add_argument(
        "--as-deployed",
        action="store_true",
        help="Apply the PEXIP_READ_ONLY / PEXIP_ALLOW_PLATFORM_TOOLS startup policy from the "
        "environment and measure the catalog a deployment actually exposes.",
    )
    args = ap.parse_args()

    defs, tools = _tool_defs(as_deployed=args.as_deployed)
    report = build_report(defs, tools, as_deployed=args.as_deployed)
    print_summary(report)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + "\n")
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
