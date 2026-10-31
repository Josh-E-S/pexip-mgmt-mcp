"""pexip_run_platform_command (gated) and pexip_send_provisioning_email."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from pexip_mcp.client import PexipError
from pexip_mcp.tools import command

from .conftest import PEXIP_HOST

COMMAND = f"https://{PEXIP_HOST}/api/admin/command/v1"


def _ok():
    return httpx.Response(200, json={"status": "success", "data": {}})


@respx.mock
@pytest.mark.parametrize(
    "name, action, params",
    [
        ("backup_create", "backup_create", None),
        ("backup_restore", "backup_restore", {"backup_id": 12}),
        ("start_cloud_node", "start_cloudnode", None),
        ("snapshot", "snapshot", None),
        ("upgrade", "upgrade", {"bundle": "x"}),
        ("upload_software_bundle", "software_bundle", {"file": "y"}),
        ("certificates_import", "certificates_import", {"certs": []}),
    ],
)
async def test_platform_command_maps_to_the_right_action(ctx, name, action, params):
    route = respx.post(f"{COMMAND}/platform/{action}/").mock(return_value=_ok())
    out = await command.run_platform_command(ctx, command=name, params=params)
    assert out["status"] == "success"
    assert json.loads(route.calls.last.request.content) == (params or {})


async def test_platform_command_rejects_unknown_names(ctx):
    with pytest.raises(PexipError) as exc:
        await command.run_platform_command(ctx, command="factory_reset")  # type: ignore[arg-type]
    assert exc.value.status_code == 400 and "Valid" in str(exc.value)


def test_platform_command_is_the_only_gated_tool():
    from pexip_mcp.tools._catalog import PLATFORM_GATED, TOOLSETS

    assert PLATFORM_GATED == {"run_platform_command"}
    assert "run_platform_command" in TOOLSETS["platform"].tools


@respx.mock
@pytest.mark.parametrize(
    "target, action", [("vmr", "send_conference_email"), ("device", "send_device_email")]
)
async def test_provisioning_email_targets(ctx, target, action):
    """Pins the CURRENT payload. The device variant's conference_id key is under
    verification (docs/review/MANUAL-REVIEW-QUEUE.md #14); change both when confirmed."""
    route = respx.post(f"{COMMAND}/conference/{action}/").mock(return_value=_ok())
    await command.send_provisioning_email(ctx, target=target, target_id=42)
    assert json.loads(route.calls.last.request.content) == {"conference_id": 42}
