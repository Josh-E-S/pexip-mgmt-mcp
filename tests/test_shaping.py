"""Response shaping: envelope normalization, concise projection, byte cap, and the
central finalizer wired into every tool."""

from __future__ import annotations

import asyncio
from typing import Any

from mcp.server.fastmcp import Context

from pexip_mcp.mcp_app import PexipMCP
from pexip_mcp.tools._helpers import read
from pexip_mcp.tools._shaping import (
    CONCISE_FIELDS,
    NARROW_HINT,
    ListResult,
    finalize_result,
    project,
    shape_list,
)


def _page(n: int, *, offset: int = 0, total: int | None = None, next_url: str | None = None):
    return {
        "objects": [
            {
                "id": offset + i,
                "resource_uri": f"/x/{offset + i}/",
                "name": f"r{i}",
                "pin": "1",
                "blob": "z" * 50,
            }
            for i in range(n)
        ],
        "meta": {
            "total_count": total if total is not None else n,
            "limit": n,
            "offset": offset,
            "next": next_url,
            "previous": None,
        },
    }


# ── finalize_result ──────────────────────────────────────────────────────────


def test_non_envelope_results_pass_through_unchanged():
    for value in (
        {"deleted": True},
        {"status": "success"},
        [1, 2],
        "x",
        None,
        {"objects": "notalist"},
    ):
        assert finalize_result(value) == value


def test_has_more_from_next_link_and_from_total_count():
    with_next = finalize_result(_page(2, total=10, next_url="/x?offset=2"))
    assert with_next["meta"]["has_more"] is True
    assert with_next["meta"]["next_offset"] == 2

    by_total = finalize_result(_page(2, offset=4, total=10))
    assert by_total["meta"]["has_more"] is True
    assert by_total["meta"]["next_offset"] == 6

    last = finalize_result(_page(2, offset=8, total=10))
    assert last["meta"]["has_more"] is False
    assert "next_offset" not in last["meta"]


def test_top_level_truncated_flag_moves_into_meta():
    r = _page(3)
    r["truncated"] = True
    out = finalize_result(r)
    assert "truncated" not in out
    assert out["meta"]["truncated"] is True


def test_byte_cap_drops_trailing_objects_and_hints():
    r = _page(200, total=200)
    out = finalize_result(r, max_bytes=3_000)
    assert 0 < len(out["objects"]) < 200
    assert out["objects"][0]["id"] == 0  # keeps the head of the list
    assert out["meta"]["truncated"] is True
    assert out["meta"]["has_more"] is True
    assert out["meta"]["next_offset"] == len(out["objects"])
    assert out["meta"]["hint"] == NARROW_HINT


def test_byte_cap_keeps_at_least_one_record():
    r = {"objects": [{"id": 1, "blob": "z" * 5_000}], "meta": {"total_count": 1, "offset": 0}}
    out = finalize_result(r, max_bytes=1_000)
    assert len(out["objects"]) == 1


def test_byte_cap_env_override(monkeypatch):
    from pexip_mcp.tools import _shaping

    monkeypatch.setenv("PEXIP_MAX_RESPONSE_BYTES", "2500")
    assert _shaping.max_response_bytes() == 2500
    monkeypatch.setenv("PEXIP_MAX_RESPONSE_BYTES", "junk")
    assert _shaping.max_response_bytes() == _shaping.DEFAULT_MAX_RESPONSE_BYTES
    monkeypatch.setenv("PEXIP_MAX_RESPONSE_BYTES", "10")
    assert _shaping.max_response_bytes() == 1_000  # floor


# ── project / shape_list ─────────────────────────────────────────────────────


def test_project_keeps_requested_and_identity_fields_only():
    rec = {"id": 7, "resource_uri": "/x/7/", "name": "n", "pin": "1", "blob": "b"}
    assert project(rec, ("name",)) == {"id": 7, "resource_uri": "/x/7/", "name": "n"}
    assert project(rec, None) == rec
    assert project("scalar", ("name",)) == "scalar"


def test_shape_list_concise_default_uses_resource_fields():
    out = shape_list(_page(2), resource="conference")
    assert out["meta"]["response_format"] == "concise"
    assert set(out["objects"][0]) <= set(CONCISE_FIELDS["conference"]) | {
        "id",
        "resource_uri",
        "uuid",
    }
    assert "blob" not in out["objects"][0]
    assert "name" in out["objects"][0]


def test_shape_list_detailed_returns_full_records():
    out = shape_list(_page(2), resource="conference", response_format="detailed")
    assert out["meta"]["response_format"] == "detailed"
    assert "blob" in out["objects"][0]


def test_shape_list_fields_override_format():
    out = shape_list(_page(2), resource="conference", response_format="detailed", fields=["pin"])
    assert out["meta"]["response_format"] == "fields"
    assert out["meta"]["fields"] == ["pin"]
    assert set(out["objects"][0]) == {"id", "resource_uri", "pin"}


def test_shape_list_unknown_resource_falls_back_to_detailed():
    out = shape_list(_page(1), resource="no_such_resource")
    assert out["meta"]["response_format"] == "detailed"
    assert "blob" in out["objects"][0]


# ── central finalizer on a real registration ─────────────────────────────────


def test_every_registered_tool_result_is_finalized():
    """PexipMCP wraps each tool so list envelopes gain has_more without the tool
    doing anything, and the wrapper keeps FastMCP's schema/Context handling."""
    server = PexipMCP("t")

    @server.tool(annotations=read("List things"))
    async def list_things(ctx: Context, limit: int = 20) -> ListResult:
        """List things."""
        return _page(limit, total=100, next_url="/x?offset=20")  # type: ignore[return-value]

    tool = server._tool_manager.get_tool("pexip_list_things")
    assert list(tool.parameters["properties"]) == ["limit"]
    assert tool.context_kwarg == "ctx"
    assert set(tool.output_schema["properties"]) == {"objects", "meta"}

    async def run() -> Any:
        return await server.call_tool("pexip_list_things", {"limit": 3})

    _content, structured = asyncio.run(run())
    assert structured["meta"]["has_more"] is True
    assert structured["meta"]["next_offset"] == 3
    assert len(structured["objects"]) == 3
