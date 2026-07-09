"""Error handling evals — does the server handle errors correctly?

Tests that tools raise the right exceptions or return graceful responses
when the Pexip API returns errors (404, 409, 400) or when invalid
parameters are passed.

All tests are deterministic — they use respx to mock API responses.
"""
from __future__ import annotations

import httpx
import pytest
import respx

from pexip_mcp.client import PexipError
from pexip_mcp.tools import (
    command,
    conference,
    device,
    end_user,
    history,
    resource_crud,
    schema,
)

from evals.conftest import case_ids, load_cases

PEXIP_HOST = "manager.example.com"
BASE_URL = f"https://{PEXIP_HOST}/api/admin/configuration/v1"
COMMAND_URL = f"https://{PEXIP_HOST}/api/admin/command/v1"
HISTORY_URL = f"https://{PEXIP_HOST}/api/admin/history/v1"

CASES = load_cases("error_handling.yaml")

TOOL_FUNCTIONS = {
    "get_vmr": conference.get_vmr,
    "update_vmr": conference.update_vmr,
    "delete_vmr": conference.delete_vmr,
    "disconnect_participant": command.disconnect_participant,
    "disconnect_conference": command.disconnect_conference,
    "set_participant_role": command.set_participant_role,
    "set_conference_layout": command.set_conference_layout,
    "mute_participant": command.mute_participant,
    "transfer_participant": command.transfer_participant,
    "get_resource_schema": schema.get_resource_schema,
    "summarize_calls": history.summarize_calls,
    "get_end_user": end_user.get_end_user,
    "get_device": device.get_device,
    "get_resource": resource_crud.get_resource,
    "list_resources": resource_crud.list_resources,
    "create_resource": resource_crud.create_resource,
    "update_resource": resource_crud.update_resource,
}

URL_BASES = {
    "conference": BASE_URL,
    "command": COMMAND_URL,
    "history": HISTORY_URL,
    "schema": BASE_URL,
}

METHOD_MAP = {
    "GET": respx.get,
    "POST": respx.post,
    "PATCH": respx.patch,
    "DELETE": respx.delete,
}


def _get_url_base(case):
    tags = case.get("tags", [])
    if "command" in tags:
        return COMMAND_URL
    if "history" in tags:
        return HISTORY_URL
    return BASE_URL


def _setup_mocks(case):
    """Register respx mocks from the case's mock_sequence."""
    for mock in case.get("mock_sequence", []):
        method = mock["method"]
        url = _get_url_base(case) + mock["url_suffix"]
        mocker = METHOD_MAP[method]
        mocker(url).mock(
            return_value=httpx.Response(mock["status"], json=mock["body"])
        )


def _build_kwargs(case):
    """Convert tool_params to function kwargs."""
    params = dict(case.get("tool_params", {}))
    return params


# ---------------------------------------------------------------------------
# Layer 1: tool-level error handling
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", CASES, ids=case_ids(CASES))
def test_tool_exists_in_registry(case, tool_names):
    """The tool referenced in the error case must exist."""
    assert case["tool"] in tool_names, f"Tool {case['tool']!r} not in registry"


@pytest.mark.parametrize(
    "case",
    [c for c in CASES if "expect_error" in c],
    ids=[c["id"] for c in CASES if "expect_error" in c],
)
@respx.mock
async def test_error_cases_raise(case, mock_ctx):
    """Cases with expect_error should raise the expected exception."""
    _setup_mocks(case)

    func = TOOL_FUNCTIONS[case["tool"]]
    kwargs = _build_kwargs(case)

    with pytest.raises(PexipError) as exc:
        await func(mock_ctx, **kwargs)

    expected = case["expect_error"]
    assert exc.value.status_code == expected["status"], (
        f"Case {case['id']!r}: expected status {expected['status']}, got {exc.value.status_code}"
    )


@pytest.mark.parametrize(
    "case",
    [c for c in CASES if "expect_success" in c],
    ids=[c["id"] for c in CASES if "expect_success" in c],
)
@respx.mock
async def test_idempotent_cases_succeed(case, mock_ctx):
    """Cases with expect_success should return gracefully (e.g. already disconnected)."""
    _setup_mocks(case)

    func = TOOL_FUNCTIONS[case["tool"]]
    kwargs = _build_kwargs(case)

    result = await func(mock_ctx, **kwargs)

    expected = case["expect_success"]
    assert result[expected["key"]] == expected["value"], (
        f"Case {case['id']!r}: expected {expected['key']}={expected['value']!r}, "
        f"got {result.get(expected['key'])!r}"
    )
