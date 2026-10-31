"""Every registered tool must be exercised by at least one eval case.

Two tests:

- a RATCHET that always runs: the set of tools with no eval coverage may only
  shrink. Adding a tool without a case, or deleting the only case that covers
  a tool, fails CI. Removing entries from KNOWN_UNCOVERED as cases are added
  is the expected maintenance.
- the GOAL, xfail(strict) until KNOWN_UNCOVERED is empty.

"Covered" means the tool name appears in evals/cases/*.yaml (tool selection,
parameters, workflows, error handling) or in evals/test_live_integration.py.

Baseline on 2026-10-31: 48 of 122 tools uncovered, nearly all the Status /
History long tail that docs/TOOL-ARCHITECTURE-PLAN.md phase 4 folds into the
generic status/history tools. Folding them removes the gap; alternatively each
needs a case before it can leave this list.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from pexip_mcp.mcp_app import mcp

import pexip_mcp.server  # noqa: F401 — registers all tools

REPO = Path(__file__).parent.parent
CASE_FILES = sorted((REPO / "evals" / "cases").glob("*.yaml"))
LIVE_FILE = REPO / "evals" / "test_live_integration.py"

KNOWN_UNCOVERED: frozenset[str] = frozenset(
    {
        "backup_restore",
        "certificates_import",
        "delete_ldap_source",
        "delete_resource",
        "get_alarm_history",
        "get_backplane",
        "get_backplane_history",
        "get_backplane_history_media_streams",
        "get_backplane_media_streams",
        "get_cloud_monitored_location",
        "get_cloud_node",
        "get_cloud_overflow_location",
        "get_conference_shard",
        "get_conference_sync_status",
        "get_conferencing_node",
        "get_exchange_scheduler_status",
        "get_gateway_rule",
        "get_ivr_theme",
        "get_ldap_source",
        "get_location",
        "get_location_status",
        "get_management_node_status",
        "get_mjx_endpoint_status",
        "get_mjx_meeting_status",
        "get_node_event_history",
        "get_node_statistics",
        "get_node_status",
        "get_registration_alias",
        "get_registration_history",
        "get_teams_node_call_status",
        "get_teams_node_status",
        "list_backplane_history",
        "list_backplanes",
        "list_cloud_monitored_locations",
        "list_cloud_overflow_locations",
        "list_conference_shards",
        "list_conference_sync_status",
        "list_exchange_scheduler_status",
        "list_location_status",
        "list_node_event_history",
        "list_registration_aliases",
        "list_teams_node_call_status",
        "platform_upgrade",
        "start_cloud_node",
        "update_global_settings",
        "update_ldap_source",
        "upload_software_bundle",
    }
)


def _uncovered() -> set[str]:
    names = {t.name for t in mcp._tool_manager.list_tools()}
    corpus = "\n".join(p.read_text() for p in CASE_FILES) + "\n" + LIVE_FILE.read_text()
    return {n for n in names if not re.search(rf"\b{re.escape(n)}\b", corpus)}


def test_eval_coverage_never_regresses():
    """Ratchet: no tool outside KNOWN_UNCOVERED may lack an eval case."""
    new_gaps = _uncovered() - KNOWN_UNCOVERED
    assert not new_gaps, (
        "Tools with no eval case (add one under evals/cases/ or evals/test_live_integration.py): "
        f"{sorted(new_gaps)}"
    )


def test_known_uncovered_list_is_current():
    """Keep KNOWN_UNCOVERED honest: entries that gained coverage or no longer
    exist as tools must be removed."""
    registered = {t.name for t in mcp._tool_manager.list_tools()}
    stale = (KNOWN_UNCOVERED - _uncovered()) | (KNOWN_UNCOVERED - registered)
    assert not stale, f"Remove from KNOWN_UNCOVERED (now covered or removed): {sorted(stale)}"


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="phase 4: fold the Status/History long tail into generic tools or add cases",
)
def test_every_tool_has_an_eval_case():
    assert not _uncovered(), sorted(_uncovered())
