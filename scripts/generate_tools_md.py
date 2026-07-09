"""Regenerate TOOLS.md from the live tool registry.

Usage:
    uv run python scripts/generate_tools_md.py

Run this whenever tools are added, removed, or re-annotated so the
catalog document never drifts from the code.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

CATEGORY_BY_MODULE = {"status": "Status", "history": "History", "command": "Command"}


def _params_cell(schema: dict | None) -> str:
    if not schema or "properties" not in schema:
        return ""
    required = set(schema.get("required", []))
    parts = []
    for name in schema["properties"]:
        if name == "ctx":
            continue
        parts.append(name if name in required else f"{name}?")
    return ", ".join(parts)


def main() -> None:
    from pexip_mcp.mcp_app import mcp

    import pexip_mcp.server  # noqa: F401 — side-effect: registers all tools

    tools = sorted(mcp._tool_manager.list_tools(), key=lambda t: t.name)
    counts: dict[str, int] = {}
    rows = []
    for tool in tools:
        module = inspect.getmodule(tool.fn).__name__.rsplit(".", 1)[-1]
        category = CATEGORY_BY_MODULE.get(module, "Configuration")
        counts[category] = counts.get(category, 0) + 1
        ann = tool.annotations
        rows.append(
            "| `{name}` | {title} | {ro} | {destr} | {idem} | {params} |".format(
                name=tool.name,
                title=(ann.title if ann else "") or "",
                ro="✅" if ann and ann.readOnlyHint else "❌",
                destr="✅" if ann and ann.destructiveHint else "❌",
                idem="✅" if ann and ann.idempotentHint else "❌",
                params=_params_cell(tool.parameters),
            )
        )

    summary = ", ".join(
        f"{counts[c]} {c}" for c in ("Configuration", "Status", "History", "Command") if c in counts
    )
    lines = [
        "# Tool Catalog",
        "",
        f"Auto-generated reference of all {len(tools)} tools exposed by the "
        f"pexip-mgmt-mcp server ({summary}).",
        "",
        "Regenerate with: `uv run python scripts/generate_tools_md.py`",
        "",
        "| Tool | Title | Read-only | Destructive | Idempotent | Parameters |",
        "|---|---|---|---|---|---|",
        *rows,
        "",
    ]
    (REPO_ROOT / "TOOLS.md").write_text("\n".join(lines))
    print(f"Wrote TOOLS.md: {len(tools)} tools ({summary})")


if __name__ == "__main__":
    main()
