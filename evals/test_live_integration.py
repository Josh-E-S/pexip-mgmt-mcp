"""Live node integration evals — run against a real Pexip Infinity deployment.

Requires --live flag and valid Pexip credentials in .env.
Tests create resources, verify them, then clean up.

Status/Command API tests auto-dial a participant into a temporary VMR
using the existing dial_participant tool. Set PEXIP_EVAL_DIAL_TARGET to
the SIP URI or alias to dial out to (e.g. "sip:test@lab.local").
"""
from __future__ import annotations

import asyncio
import os

import pytest
import pytest_asyncio

from pexip_mcp.client import PexipError
from pexip_mcp.tools import command, conference, end_user, history, resource_crud, schema, status

pytestmark = [pytest.mark.live, pytest.mark.asyncio(loop_scope="session")]

DIAL_TARGET = os.environ.get("PEXIP_EVAL_DIAL_TARGET", "")
# The VMR the live-call phase dials into. Use a real hosted VMR on your node
# (set PEXIP_EVAL_VMR) so the call is a hosted conference — lock/mute-guests
# and other conference commands are invalid on gateway-routed calls.
EVAL_VMR = os.environ.get("PEXIP_EVAL_VMR", "allhands@example.com")


# ---------------------------------------------------------------------------
# Phase 1: Read-only smoke tests
# ---------------------------------------------------------------------------

class TestReadOnlySmoke:
    """Verify connectivity, auth, and basic list/get calls."""

    async def test_list_vmrs(self, live_ctx):
        result = await conference.list_vmrs(live_ctx)
        assert "objects" in result
        assert "meta" in result

    async def test_list_locations(self, live_ctx):
        from pexip_mcp.tools import infrastructure
        result = await infrastructure.list_locations(live_ctx)
        assert "objects" in result

    async def test_get_global_settings(self, live_ctx):
        from pexip_mcp.tools import global_settings
        result = await global_settings.get_global_settings(live_ctx)
        assert isinstance(result, dict)

    async def test_list_alarms(self, live_ctx):
        result = await status.list_alarms(live_ctx)
        assert "objects" in result

    async def test_get_licensing_status(self, live_ctx):
        result = await status.get_licensing_status(live_ctx)
        assert isinstance(result, dict)

    async def test_schema_discovery(self, live_ctx):
        result = await schema.get_resource_schema(live_ctx, resource="conference")
        assert isinstance(result, dict)
        assert "fields" in result or "properties" in result or len(result) > 0

    async def test_list_active_conferences(self, live_ctx):
        result = await status.list_active_conferences(live_ctx)
        assert "objects" in result


# ---------------------------------------------------------------------------
# Phase 1b: Generic CRUD tools — read-only smoke tests
# ---------------------------------------------------------------------------

class TestGenericCRUDSmoke:
    """Verify the generic CRUD tools work against the live node."""

    async def test_list_resources_sip_proxy(self, live_ctx):
        result = await resource_crud.list_resources(live_ctx, resource="sip_proxy")
        assert "objects" in result

    async def test_list_resources_dns_server(self, live_ctx):
        result = await resource_crud.list_resources(live_ctx, resource="dns_server")
        assert "objects" in result

    async def test_list_resources_role(self, live_ctx):
        result = await resource_crud.list_resources(live_ctx, resource="role")
        assert "objects" in result

    async def test_list_resources_tls_certificate(self, live_ctx):
        result = await resource_crud.list_resources(live_ctx, resource="tls_certificate")
        assert "objects" in result

    async def test_list_resources_unknown_raises(self, live_ctx):
        with pytest.raises(PexipError) as exc:
            await resource_crud.list_resources(live_ctx, resource="not_a_real_thing")
        assert exc.value.status_code == 400

    async def test_get_resource_schema_via_registry(self, live_ctx):
        """Confirm schema discovery works for a registry resource."""
        result = await schema.get_resource_schema(live_ctx, resource="sip_proxy")
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Phase 2: VMR CRUD lifecycle
# ---------------------------------------------------------------------------

class TestVMRLifecycle:
    """Create -> read -> update -> delete a VMR on the live node."""

    VMR_NAME = "eval-test-vmr"

    async def test_vmr_crud(self, live_ctx):
        # Clean up any leftover from a prior failed run
        try:
            await conference.delete_vmr(live_ctx, self.VMR_NAME)
        except PexipError:
            pass

        # create_vmr is secure-by-default: it requires a PIN or an explicit
        # allow_no_pin. This is a CRUD-lifecycle test, not a PIN test, so opt out
        # of the PIN requirement rather than couple to the node's Global PIN Length.
        created = await conference.create_vmr(
            live_ctx, name=self.VMR_NAME, allow_no_pin=True, description="eval test"
        )
        assert created["name"] == self.VMR_NAME
        vmr_id = created["id"]

        try:
            fetched = await conference.get_vmr(live_ctx, self.VMR_NAME)
            assert fetched["id"] == vmr_id

            updated = await conference.update_vmr(
                live_ctx, vmr_id, description="eval test - updated"
            )
            assert updated["description"] == "eval test - updated"
        finally:
            await conference.delete_vmr(live_ctx, vmr_id)

        with pytest.raises(PexipError) as exc:
            await conference.get_vmr(live_ctx, vmr_id)
        assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# Phase 3: End user CRUD
# ---------------------------------------------------------------------------

class TestEndUserLifecycle:
    """Create -> read -> update -> delete an end user."""

    EMAIL = "eval-test@pexip-eval.example"

    async def test_end_user_crud(self, live_ctx):
        # Clean up any leftover from a prior failed run
        try:
            await end_user.delete_end_user(live_ctx, self.EMAIL)
        except PexipError:
            pass

        created = await end_user.create_end_user(
            live_ctx, primary_email_address=self.EMAIL, first_name="Eval", last_name="Test"
        )
        user_id = created["id"]

        try:
            fetched = await end_user.get_end_user(live_ctx, self.EMAIL)
            assert fetched["primary_email_address"] == self.EMAIL

            updated = await end_user.update_end_user(live_ctx, self.EMAIL, first_name="Updated")
            assert updated["first_name"] == "Updated"
        finally:
            await end_user.delete_end_user(live_ctx, user_id)


# ---------------------------------------------------------------------------
# Phase 4: History API (always available, no live call needed)
# ---------------------------------------------------------------------------

class TestHistoryAPI:
    """Test history endpoints — these work even without an active call."""

    async def test_list_history_conferences(self, live_ctx):
        result = await history.list_history_conferences(live_ctx, limit=5)
        assert "objects" in result

    async def test_summarize_calls(self, live_ctx):
        result = await history.summarize_calls(
            live_ctx,
            start_time="2020-01-01T00:00:00",
            end_time="2030-01-01T00:00:00",
            group_by="call_direction",
        )
        assert isinstance(result, dict)

    async def test_list_alarm_history(self, live_ctx):
        result = await history.list_alarm_history(live_ctx)
        assert "objects" in result


# ---------------------------------------------------------------------------
# Phase 5: Error handling on live node
# ---------------------------------------------------------------------------

class TestLiveErrors:
    """Verify error handling against a real server."""

    async def test_get_nonexistent_vmr(self, live_ctx):
        with pytest.raises(PexipError) as exc:
            await conference.get_vmr(live_ctx, "eval-nonexistent-room-xyz-99999")
        assert exc.value.status_code == 404

    async def test_update_vmr_no_fields(self, live_ctx):
        with pytest.raises(PexipError) as exc:
            await conference.update_vmr(live_ctx, 99999)
        assert exc.value.status_code == 400

    async def test_invalid_group_by(self, live_ctx):
        with pytest.raises(PexipError) as exc:
            await history.summarize_calls(
                live_ctx,
                start_time="2026-01-01T00:00:00",
                end_time="2026-01-02T00:00:00",
                group_by="invalid_field",
            )
        assert exc.value.status_code == 400


# ---------------------------------------------------------------------------
# Phase 6: Live call — Status + Command API
#
# Uses dial_participant to auto-dial PEXIP_EVAL_DIAL_TARGET into a
# temporary VMR, then exercises status reads and command actions against
# the live call. Cleans up (disconnect + delete VMR) in teardown.
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="session")
async def live_call(live_ctx):
    """Set up a single live call for all status/command tests.

    Session-scoped: dials once, all 12 tests share the same call, teardown
    disconnects at the end.

    Flow:
      1. If EVAL_VMR is already live, disconnect it (clean slate).
      2. If EVAL_VMR doesn't exist as a configured VMR, create it.
      3. Dial DIAL_TARGET into EVAL_VMR.
      4. Wait for connection, find conference + participant UUIDs.
      5. Yield to tests.
      6. Teardown: disconnect the call. Only delete the VMR if we created it.
    """
    if not DIAL_TARGET:
        pytest.skip(
            "PEXIP_EVAL_DIAL_TARGET not set — set it to a SIP URI or alias "
            "reachable from your lab node (e.g. sip:cisco@lab.local)"
        )

    created_vmr = False

    # Step 1: No pre-cleanup needed — we dial into an existing VMR and
    # only disconnect our own participant in teardown.

    # Step 2: Check if the VMR exists; create it only if it doesn't
    try:
        await conference.get_vmr(live_ctx, EVAL_VMR)
    except PexipError as e:
        if e.status_code == 404:
            # allow_no_pin: this is a throwaway VMR for a call-lifecycle test, so
            # opt out of the secure-by-default PIN requirement (and any node PIN
            # policy) rather than couple the test to a specific PIN length.
            await conference.create_vmr(
                live_ctx, name=EVAL_VMR, description="eval live call test",
                allow_no_pin=True,
            )
            created_vmr = True
        else:
            raise

    try:
        # Step 3: Dial the target into the VMR
        dial_result = await command.dial_participant(
            live_ctx,
            conference_alias=EVAL_VMR,
            destination=DIAL_TARGET,
            protocol="sip",
            system_location="Primary",
        )

        # Step 4: Wait for the call to establish and find UUIDs
        # The participant_id from the dial response is the most reliable handle.
        dialed_pid = dial_result["data"]["participant_id"]
        await asyncio.sleep(10)

        # Look up the participant to find which conference it landed in.
        # The status API conference name is the VMR's display name, not the
        # alias we dialed, so we find the conference through the participant.
        try:
            part = await status.get_active_participant(live_ctx, dialed_pid)
        except PexipError:
            pytest.skip("Participant not found in status — call may not have connected")

        conf_name = part.get("conference")
        if not conf_name:
            pytest.skip("Participant has no conference — call may still be connecting")

        confs = await status.list_active_conferences(live_ctx, name=conf_name)
        conf_objects = confs.get("objects", [])
        if not conf_objects:
            pytest.skip("Conference not found in status after dial")

        conf_id = conf_objects[0]["id"]

        # Step 5: Yield to tests
        yield {
            "ctx": live_ctx,
            "conference_id": conf_id,
            "conference_name": conf_name,
            "participant_id": dialed_pid,
            "dial_result": dial_result,
        }

    finally:
        # Step 6: Disconnect the dialed participant (not the whole conference)
        try:
            await command.disconnect_participant(live_ctx, participant_id=dialed_pid)
        except Exception:
            pass
        # Only delete the VMR if we created it
        if created_vmr:
            await asyncio.sleep(2)
            try:
                await conference.delete_vmr(live_ctx, EVAL_VMR)
            except Exception:
                pass


class TestLiveCallStatus:
    """Status API reads during a live call."""

    async def test_list_active_conferences_finds_call(self, live_call):
        result = await status.list_active_conferences(
            live_call["ctx"], name=live_call["conference_name"]
        )
        assert len(result["objects"]) >= 1

    async def test_list_active_participants(self, live_call):
        result = await status.list_active_participants(
            live_call["ctx"], conference_name=live_call["conference_name"]
        )
        assert len(result["objects"]) >= 1

    async def test_get_active_participant(self, live_call):
        result = await status.get_active_participant(
            live_call["ctx"], live_call["participant_id"]
        )
        assert result["id"] == live_call["participant_id"]

    async def test_list_node_status(self, live_call):
        result = await status.list_node_status(live_call["ctx"])
        assert "objects" in result
        assert len(result["objects"]) >= 1


class TestLiveCallNameResolution:
    """Server-side name->UUID resolution — the "how a human refers to things" path.

    A UC admin says "lock the All Hands conference" or "mute <person>"; the
    server must resolve the name/alias to the runtime UUID with no prior lookup.
    These drive the real command tools by NAME (not UUID) against the live call.
    """

    async def test_lock_unlock_conference_by_name(self, live_call):
        ctx = live_call["ctx"]
        name = live_call["conference_name"]  # human-facing running-conference name

        result = await command.lock_conference(ctx, conference_id=name)
        assert result.get("status") == "success"

        result = await command.unlock_conference(ctx, conference_id=name)
        assert result.get("status") == "success"

    async def test_mute_unmute_guests_by_name(self, live_call):
        ctx = live_call["ctx"]
        name = live_call["conference_name"]

        result = await command.mute_guests(ctx, conference_id=name)
        assert result.get("status") == "success"

        result = await command.unmute_guests(ctx, conference_id=name)
        assert result.get("status") == "success"

    async def test_mute_unmute_participant_by_display_name(self, live_call):
        ctx = live_call["ctx"]
        part = await status.get_active_participant(ctx, live_call["participant_id"])
        display_name = (part.get("display_name") or "").strip()
        if not display_name:
            pytest.skip("participant has no display_name to resolve by")

        result = await command.mute_participant(
            ctx, participant_id=display_name, conference=live_call["conference_name"]
        )
        assert result.get("status") == "success"

        result = await command.unmute_participant(
            ctx, participant_id=display_name, conference=live_call["conference_name"]
        )
        assert result.get("status") == "success"

    async def test_conference_name_not_running_raises(self, live_call):
        """A made-up conference name resolves to a clean 404, not a crash."""
        ctx = live_call["ctx"]
        with pytest.raises(PexipError) as exc:
            await command.lock_conference(
                ctx, conference_id="No Such Conference Xyzzy 12345"
            )
        assert exc.value.status_code == 404


class TestLiveCallCommands:
    """Command API actions during a live call.

    Tests are ordered to avoid conflicts (e.g. mute before disconnect).
    The disconnect test runs last since it ends the participant's call.
    """

    async def test_mute_unmute(self, live_call):
        ctx = live_call["ctx"]
        pid = live_call["participant_id"]

        result = await command.mute_participant(ctx, participant_id=pid)
        assert result.get("status") == "success"

        result = await command.unmute_participant(ctx, participant_id=pid)
        assert result.get("status") == "success"

    async def test_lock_unlock(self, live_call):
        ctx = live_call["ctx"]
        cid = live_call["conference_id"]

        result = await command.lock_conference(ctx, conference_id=cid)
        assert result.get("status") == "success"

        result = await command.unlock_conference(ctx, conference_id=cid)
        assert result.get("status") == "success"

    async def test_mute_unmute_guests(self, live_call):
        ctx = live_call["ctx"]
        cid = live_call["conference_id"]

        result = await command.mute_guests(ctx, conference_id=cid)
        assert result.get("status") == "success"

        result = await command.unmute_guests(ctx, conference_id=cid)
        assert result.get("status") == "success"

    async def test_disconnect_participant(self, live_call):
        """Disconnect the dialed participant."""
        ctx = live_call["ctx"]
        pid = live_call["participant_id"]

        result = await command.disconnect_participant(ctx, participant_id=pid)
        assert result.get("status") == "success"
