"""Every registered tool must be exercised by at least one eval case.

Two tests:

- a RATCHET that always runs: the set of tools with no eval coverage may only
  shrink. Adding a tool without a case, or deleting the only case that covers
  a tool, fails CI. Removing entries from KNOWN_UNCOVERED as cases are added
  is the expected maintenance.
- the GOAL, xfail(strict) until KNOWN_UNCOVERED is empty.

"Covered" means the tool is named STRUCTURALLY by a case: under an
`expected_tools` / `expected_tool` / `tool` key in evals/cases/*.yaml, or called
as `<module>.<tool>(` in evals/test_live_integration.py. Prose, prompts, and
YAML comments do not count, so a "do NOT call X" note cannot mark X covered.
Live-only coverage is accepted but reported separately, because CI never runs
the --live suite.

Baseline on 2026-10-31: 48 of 122 tools uncovered, nearly all the Status /
History long tail that docs/TOOL-ARCHITECTURE-PLAN.md phase 4 folds into the
generic status/history tools. Folding them removes the gap; alternatively each
needs a case before it can leave this list.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from pexip_mcp.mcp_app import mcp

import pexip_mcp.server  # noqa: F401 — registers all tools

REPO = Path(__file__).parent.parent
CASE_FILES = sorted((REPO / "evals" / "cases").glob("*.yaml"))
LIVE_FILE = REPO / "evals" / "test_live_integration.py"

KNOWN_UNCOVERED: frozenset[str] = frozenset(
    {
        "pexip_backup_restore",
        "pexip_certificates_import",
        "pexip_delete_ldap_source",
        "pexip_delete_resource",
        "pexip_get_alarm_history",
        "pexip_get_backplane",
        "pexip_get_backplane_history",
        "pexip_get_backplane_history_media_streams",
        "pexip_get_backplane_media_streams",
        "pexip_get_cloud_monitored_location",
        "pexip_get_cloud_node",
        "pexip_get_cloud_overflow_location",
        "pexip_get_conference_shard",
        "pexip_get_conference_sync_status",
        "pexip_get_conferencing_node",
        "pexip_get_exchange_scheduler_status",
        "pexip_get_gateway_rule",
        "pexip_get_ivr_theme",
        "pexip_get_ldap_source",
        "pexip_get_location",
        "pexip_get_location_status",
        "pexip_get_management_node_status",
        "pexip_get_mjx_endpoint_status",
        "pexip_get_mjx_meeting_status",
        "pexip_get_node_event_history",
        "pexip_get_node_statistics",
        "pexip_get_node_status",
        "pexip_get_registration_alias",
        "pexip_get_registration_history",
        "pexip_get_teams_node_call_status",
        "pexip_get_teams_node_status",
        "pexip_list_backplane_history",
        "pexip_list_backplanes",
        "pexip_list_cloud_monitored_locations",
        "pexip_list_cloud_overflow_locations",
        "pexip_list_conference_shards",
        "pexip_list_conference_sync_status",
        "pexip_list_exchange_scheduler_status",
        "pexip_list_location_status",
        "pexip_list_node_event_history",
        "pexip_list_registration_aliases",
        "pexip_list_teams_node_call_status",
        "pexip_platform_upgrade",
        "pexip_start_cloud_node",
        "pexip_update_global_settings",
        "pexip_update_ldap_source",
        "pexip_upload_software_bundle",
    }
)


# Covered only by evals/test_live_integration.py, which CI does not run. Each
# of these still needs a mocked case; the list is kept exact so it is visible.
KNOWN_LIVE_ONLY: frozenset[str] = frozenset({"pexip_get_active_participant"})


def _yaml_tool_refs() -> set[str]:
    """Tool names referenced structurally in the YAML case files."""
    refs: set[str] = set()

    def walk(node) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in {"expected_tools", "expected_tool", "tool"}:
                    for name in value if isinstance(value, list) else [value]:
                        if isinstance(name, str):
                            refs.add(name)
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for path in CASE_FILES:
        walk(yaml.safe_load(path.read_text(encoding="utf-8")))
    return refs


def _live_tool_refs() -> set[str]:
    """Tool names invoked as `<module>.<tool>(` in the live integration suite."""
    text = LIVE_FILE.read_text(encoding="utf-8")
    # The live suite calls the Python functions (conference.list_vmrs); the
    # published tool name carries the service prefix.
    return {f"pexip_{m.group(1)}" for m in re.finditer(r"\b[a-z_]+\.([a-z_]+)\(", text)}


REGISTERED: frozenset[str] = frozenset(t.name for t in mcp._tool_manager.list_tools())
YAML_COVERED: frozenset[str] = frozenset(_yaml_tool_refs()) & REGISTERED
LIVE_ONLY_COVERED: frozenset[str] = (frozenset(_live_tool_refs()) & REGISTERED) - YAML_COVERED
UNCOVERED: frozenset[str] = REGISTERED - YAML_COVERED - LIVE_ONLY_COVERED


def test_eval_coverage_never_regresses():
    """Ratchet: no tool outside KNOWN_UNCOVERED may lack an eval case."""
    new_gaps = UNCOVERED - KNOWN_UNCOVERED
    assert not new_gaps, (
        "Tools with no eval case (add one under evals/cases/ or evals/test_live_integration.py): "
        f"{sorted(new_gaps)}"
    )


def test_known_uncovered_list_is_current():
    """Keep KNOWN_UNCOVERED honest: entries that gained coverage or no longer exist
    as tools must be removed. (UNCOVERED is a subset of REGISTERED, so one
    difference covers both cases.)"""
    stale = KNOWN_UNCOVERED - UNCOVERED
    assert not stale, f"Remove from KNOWN_UNCOVERED (now covered or removed): {sorted(stale)}"


def test_live_only_coverage_is_acknowledged():
    """Tools covered ONLY by the opt-in --live suite are not exercised in CI. Keep
    this list visible so each gets a mocked case eventually."""
    assert LIVE_ONLY_COVERED <= KNOWN_LIVE_ONLY, sorted(LIVE_ONLY_COVERED - KNOWN_LIVE_ONLY)
    assert KNOWN_LIVE_ONLY <= LIVE_ONLY_COVERED, sorted(KNOWN_LIVE_ONLY - LIVE_ONLY_COVERED)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="phase 4: fold the Status/History long tail into generic tools or add cases",
)
def test_every_tool_has_an_eval_case():
    assert not UNCOVERED, sorted(UNCOVERED)
