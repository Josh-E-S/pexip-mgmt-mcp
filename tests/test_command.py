from __future__ import annotations

import json

import httpx
import pytest
import respx

from pexip_mcp.client import PexipError
from pexip_mcp.tools import command

from .conftest import BASE_URL, COMMAND_URL, STATUS_URL, fk


def _ok():
    return httpx.Response(200, json={"status": "success", "data": {}})


_UUID = "dddddddd-1111-2222-3333-444444444444"


@respx.mock
async def test_conference_command_resolves_name_to_uuid(ctx):
    """A conference name (not a UUID) is resolved via the Status API, and the
    command is issued against the resolved UUID."""
    lookup = respx.get(f"{STATUS_URL}/conference/").mock(
        return_value=httpx.Response(
            200,
            json={"objects": [{"id": _UUID, "name": "All Hands"}], "meta": {"total_count": 1}},
        )
    )
    lock = respx.post(f"{COMMAND_URL}/conference/lock/").mock(return_value=_ok())

    await command.lock_conference(ctx, conference_id="All Hands")

    assert lookup.called
    assert json.loads(lock.calls.last.request.read()) == {"conference_id": _UUID}


@respx.mock
async def test_conference_command_uuid_skips_lookup(ctx):
    """A UUID is used as-is — no Status API lookup."""
    lookup = respx.get(f"{STATUS_URL}/conference/")
    lock = respx.post(f"{COMMAND_URL}/conference/lock/").mock(return_value=_ok())

    await command.lock_conference(ctx, conference_id=_UUID)

    assert not lookup.called
    assert json.loads(lock.calls.last.request.read()) == {"conference_id": _UUID}


@respx.mock
async def test_conference_name_not_running_raises_404(ctx):
    respx.get(f"{STATUS_URL}/conference/").mock(
        return_value=httpx.Response(200, json={"objects": [], "meta": {"total_count": 0}})
    )
    with pytest.raises(PexipError) as exc:
        await command.mute_guests(ctx, conference_id="Nonexistent Room")
    assert exc.value.status_code == 404


@respx.mock
async def test_conference_name_ambiguous_raises_409(ctx):
    respx.get(f"{STATUS_URL}/conference/").mock(
        return_value=httpx.Response(
            200,
            json={
                "objects": [
                    {"id": _UUID, "name": "Standup"},
                    {"id": "eeeeeeee-1111-2222-3333-444444444444", "name": "Standup"},
                ],
                "meta": {"total_count": 2},
            },
        )
    )
    with pytest.raises(PexipError) as exc:
        await command.mute_guests(ctx, conference_id="Standup")
    assert exc.value.status_code == 409


@respx.mock
async def test_participant_command_resolves_display_name(ctx):
    """A participant display name is resolved to its UUID via the Status API."""
    lookup = respx.get(f"{STATUS_URL}/participant/").mock(
        return_value=httpx.Response(
            200,
            json={"objects": [{"id": _UUID, "display_name": "Alice Smith"}], "meta": {"total_count": 1}},
        )
    )
    mute = respx.post(f"{COMMAND_URL}/participant/mute/").mock(return_value=_ok())

    await command.mute_participant(ctx, participant_id="Alice")  # substring match

    assert lookup.called
    assert json.loads(mute.calls.last.request.read()) == {"participant_id": _UUID}


@respx.mock
async def test_participant_scope_passes_conference_filter(ctx):
    """A conference name scopes the participant lookup."""
    lookup = respx.get(f"{STATUS_URL}/participant/").mock(
        return_value=httpx.Response(
            200,
            json={"objects": [{"id": _UUID, "display_name": "Bob"}], "meta": {"total_count": 1}},
        )
    )
    respx.post(f"{COMMAND_URL}/participant/disconnect/").mock(return_value=_ok())

    await command.disconnect_participant(ctx, participant_id="Bob", conference="All Hands")

    assert "conference=All+Hands" in str(lookup.calls.last.request.url)


@respx.mock
async def test_participant_name_ambiguous_raises_409(ctx):
    respx.get(f"{STATUS_URL}/participant/").mock(
        return_value=httpx.Response(
            200,
            json={
                "objects": [
                    {"id": _UUID, "display_name": "Alex"},
                    {"id": "eeeeeeee-aaaa-bbbb-cccc-222222222222", "display_name": "Alexis"},
                ],
                "meta": {"total_count": 2},
            },
        )
    )
    with pytest.raises(PexipError) as exc:
        await command.mute_participant(ctx, participant_id="Ale")
    assert exc.value.status_code == 409


@respx.mock
async def test_dial_participant_minimal_body(ctx):
    route = respx.post(f"{COMMAND_URL}/participant/dial/").mock(return_value=_ok())

    await command.dial_participant(ctx, conference_alias="standup", destination="alice@x.com")

    body = json.loads(route.calls.last.request.read())
    assert body == {"conference_alias": "standup", "destination": "alice@x.com"}


@respx.mock
async def test_dial_participant_resolves_system_location_to_uri(ctx):
    respx.get(f"{BASE_URL}/system_location/").mock(
        return_value=httpx.Response(
            200,
            json={
                "meta": {"total_count": 1, "limit": 2, "offset": 0,
                         "next": None, "previous": None},
                "objects": [
                    {"id": 4, "name": "London", "resource_uri": fk("system_location", 4)}
                ],
            },
        )
    )
    route = respx.post(f"{COMMAND_URL}/participant/dial/").mock(return_value=_ok())

    await command.dial_participant(
        ctx,
        conference_alias="standup",
        destination="alice@x.com",
        protocol="sip",
        role="guest",
        system_location="London",
        streaming=False,
    )

    body = json.loads(route.calls.last.request.read())
    assert body["system_location"] == "London"
    assert body["protocol"] == "sip"
    assert body["role"] == "guest"
    assert body["streaming"] is False


@respx.mock
async def test_disconnect_participant_passes_id(ctx):
    route = respx.post(f"{COMMAND_URL}/participant/disconnect/").mock(return_value=_ok())

    await command.disconnect_participant(ctx, participant_id="11111111-aaaa-bbbb-cccc-222222222222")

    body = json.loads(route.calls.last.request.read())
    assert body == {"participant_id": "11111111-aaaa-bbbb-cccc-222222222222"}


@respx.mock
async def test_disconnect_participant_swallows_404_as_already_disconnected(ctx):
    respx.post(f"{COMMAND_URL}/participant/disconnect/").mock(
        return_value=httpx.Response(404, json={"detail": "Not found"})
    )

    result = await command.disconnect_participant(ctx, participant_id="55555555-aaaa-bbbb-cccc-666666666666")

    assert result["status"] == "success"
    assert "already disconnected" in result["note"]
    assert result["participant_id"] == "55555555-aaaa-bbbb-cccc-666666666666"


@respx.mock
async def test_disconnect_participant_propagates_other_errors(ctx):
    respx.post(f"{COMMAND_URL}/participant/disconnect/").mock(
        return_value=httpx.Response(500, text="oops")
    )

    with pytest.raises(PexipError) as exc:
        await command.disconnect_participant(ctx, participant_id="77777777-aaaa-bbbb-cccc-888888888888")

    assert exc.value.status_code == 500


@respx.mock
async def test_mute_participant(ctx):
    route = respx.post(f"{COMMAND_URL}/participant/mute/").mock(return_value=_ok())

    await command.mute_participant(ctx, participant_id="33333333-aaaa-bbbb-cccc-444444444444")

    assert json.loads(route.calls.last.request.read()) == {"participant_id": "33333333-aaaa-bbbb-cccc-444444444444"}


@respx.mock
async def test_unmute_participant(ctx):
    route = respx.post(f"{COMMAND_URL}/participant/unmute/").mock(return_value=_ok())

    await command.unmute_participant(ctx, participant_id="33333333-aaaa-bbbb-cccc-444444444444")

    assert route.called


@respx.mock
async def test_set_participant_role_validates_enum(ctx):
    with pytest.raises(PexipError) as exc:
        await command.set_participant_role(ctx, participant_id="33333333-aaaa-bbbb-cccc-444444444444", role="admin")

    assert exc.value.status_code == 400


@respx.mock
async def test_set_participant_role_chair(ctx):
    route = respx.post(f"{COMMAND_URL}/participant/role/").mock(return_value=_ok())

    await command.set_participant_role(ctx, participant_id="33333333-aaaa-bbbb-cccc-444444444444", role="chair")

    body = json.loads(route.calls.last.request.read())
    assert body == {"participant_id": "33333333-aaaa-bbbb-cccc-444444444444", "role": "chair"}


@respx.mock
async def test_disconnect_conference(ctx):
    route = respx.post(f"{COMMAND_URL}/conference/disconnect/").mock(return_value=_ok())

    await command.disconnect_conference(ctx, conference_id="aaaaaaaa-1111-2222-3333-444444444444")

    assert json.loads(route.calls.last.request.read()) == {"conference_id": "aaaaaaaa-1111-2222-3333-444444444444"}


@respx.mock
async def test_disconnect_conference_swallows_404(ctx):
    respx.post(f"{COMMAND_URL}/conference/disconnect/").mock(
        return_value=httpx.Response(404, json={"detail": "Not found"})
    )

    result = await command.disconnect_conference(ctx, conference_id="bbbbbbbb-1111-2222-3333-444444444444")

    assert result["status"] == "success"
    assert "already ended" in result["note"]


@respx.mock
async def test_lock_and_unlock_conference(ctx):
    lock_route = respx.post(f"{COMMAND_URL}/conference/lock/").mock(return_value=_ok())
    unlock_route = respx.post(f"{COMMAND_URL}/conference/unlock/").mock(return_value=_ok())

    await command.lock_conference(ctx, conference_id="aaaaaaaa-1111-2222-3333-444444444444")
    await command.unlock_conference(ctx, conference_id="aaaaaaaa-1111-2222-3333-444444444444")

    assert lock_route.called
    assert unlock_route.called


@respx.mock
async def test_mute_and_unmute_guests(ctx):
    mute_route = respx.post(f"{COMMAND_URL}/conference/mute_guests/").mock(return_value=_ok())
    unmute_route = respx.post(f"{COMMAND_URL}/conference/unmute_guests/").mock(return_value=_ok())

    await command.mute_guests(ctx, conference_id="aaaaaaaa-1111-2222-3333-444444444444")
    await command.unmute_guests(ctx, conference_id="aaaaaaaa-1111-2222-3333-444444444444")

    assert mute_route.called
    assert unmute_route.called


@respx.mock
async def test_set_conference_layout_requires_at_least_one_field(ctx):
    with pytest.raises(PexipError) as exc:
        await command.set_conference_layout(ctx, conference_id="aaaaaaaa-1111-2222-3333-444444444444")

    assert exc.value.status_code == 400


@respx.mock
async def test_set_conference_layout_sends_transforms_payload(ctx):
    route = respx.post(f"{COMMAND_URL}/conference/transform_layout/").mock(return_value=_ok())

    await command.set_conference_layout(
        ctx, conference_id="aaaaaaaa-1111-2222-3333-444444444444", host_layout="four_mains_zero_pips"
    )

    body = json.loads(route.calls.last.request.read())
    assert body == {
        "conference_id": "aaaaaaaa-1111-2222-3333-444444444444",
        "transforms": {"host_layout": "four_mains_zero_pips"},
    }


@respx.mock
async def test_set_conference_layout_both_layouts(ctx):
    route = respx.post(f"{COMMAND_URL}/conference/transform_layout/").mock(return_value=_ok())

    await command.set_conference_layout(
        ctx,
        conference_id="aaaaaaaa-1111-2222-3333-444444444444",
        host_layout="one_main_zero_pips",
        guest_layout="nine_equal",
    )

    body = json.loads(route.calls.last.request.read())
    assert body["transforms"] == {
        "host_layout": "one_main_zero_pips",
        "guest_layout": "nine_equal",
    }


@respx.mock
async def test_transfer_participant_minimal(ctx):
    route = respx.post(f"{COMMAND_URL}/participant/transfer/").mock(return_value=_ok())

    await command.transfer_participant(
        ctx, participant_id="33333333-aaaa-bbbb-cccc-444444444444", conference_alias="breakout-1"
    )

    body = json.loads(route.calls.last.request.read())
    assert body == {"participant_id": "33333333-aaaa-bbbb-cccc-444444444444", "conference_alias": "breakout-1"}


@respx.mock
async def test_transfer_participant_with_role_and_pin(ctx):
    route = respx.post(f"{COMMAND_URL}/participant/transfer/").mock(return_value=_ok())

    await command.transfer_participant(
        ctx,
        participant_id="33333333-aaaa-bbbb-cccc-444444444444",
        conference_alias="locked-room",
        role="guest",
        pin="1234",
    )

    body = json.loads(route.calls.last.request.read())
    assert body["role"] == "guest"
    assert body["pin"] == "1234"


@respx.mock
async def test_transfer_participant_invalid_role_raises(ctx):
    with pytest.raises(PexipError) as exc:
        await command.transfer_participant(
            ctx, participant_id="33333333-aaaa-bbbb-cccc-444444444444", conference_alias="x", role="admin"
        )
    assert exc.value.status_code == 400


