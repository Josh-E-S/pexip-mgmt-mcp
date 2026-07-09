#!/usr/bin/env python3
"""Pretty-print a `summarize_calls` MCP tool response as Markdown.

The MCP tool returns:
  {
    "total_calls": int,
    "total_duration_seconds": int,
    "average_duration_seconds": float,
    "time_range": {"start": "...", "end": "..."},
    "group_by": str,
    "groups": {<key>: {"count": int, "duration_seconds": int}, ...},
    "truncated": bool,
    "server_total_count": int | None
  }

Pipe the JSON in on stdin or pass it as the first argument.

Examples:
    cat report.json | python pexip_report.py
    python pexip_report.py "$(< report.json)"

Output is Markdown — paste straight into a doc, ticket, or email.
"""
from __future__ import annotations

import json
import sys
from typing import Any


def _fmt_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h {m}m {s}s"


def _row(key: str, count: int, total: int, duration: int) -> str:
    pct = (count / total * 100.0) if total else 0.0
    return f"| `{key}` | {count:,} | {pct:.1f}% | {_fmt_duration(duration)} |"


def render(data: dict[str, Any]) -> str:
    total = data["total_calls"]
    duration = data["total_duration_seconds"]
    avg = data["average_duration_seconds"]
    tr = data["time_range"]
    group_by = data["group_by"]
    groups = data.get("groups") or {}

    out: list[str] = []
    out.append(f"# Pexip call report — grouped by `{group_by}`")
    out.append("")
    out.append(f"- **Window:** `{tr['start']}` → `{tr['end']}` (UTC)")
    out.append(f"- **Total calls:** {total:,}")
    out.append(f"- **Total duration:** {_fmt_duration(duration)}")
    out.append(f"- **Average call:** {_fmt_duration(int(avg))}")
    if data.get("truncated"):
        cap = data.get("server_total_count") or "?"
        out.append(
            f"- **WARNING:** retention cap hit — server reports {cap} matching records, "
            "report counts only the first 10,000. Narrow the time window for a complete picture."
        )
    out.append("")
    out.append(f"| {group_by} | Count | Share | Duration |")
    out.append("|---|---:|---:|---:|")
    if not groups:
        out.append("| _(no matching calls)_ | 0 | 0% | 0s |")
    else:
        # Already sorted by count desc by the MCP tool, but re-sort defensively.
        for key, vals in sorted(
            groups.items(), key=lambda kv: kv[1]["count"], reverse=True
        ):
            out.append(_row(key, vals["count"], total, vals["duration_seconds"]))
    return "\n".join(out)


def _load_input() -> dict[str, Any]:
    raw = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    raw = raw.strip()
    if not raw:
        print("error: no JSON on stdin or argv[1]", file=sys.stderr)
        sys.exit(2)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"error: invalid JSON: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    print(render(_load_input()))
