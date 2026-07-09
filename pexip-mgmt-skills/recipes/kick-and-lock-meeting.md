# Recipe: kick late joiners and lock a meeting

End-to-end workflow for the canonical "the standup is running long — boot the latecomers and lock the room" admin action. Combines Status API reads + Command API writes with mandatory confirmation gates.

**Skills used:** `pexip-operations` (live-meeting-ops.md, safety.md).

## Inputs

- `conference` — the dialed alias of the meeting (e.g. `standup`, `allhands`).
- `cutoff_time` (optional) — local time after which joiners are considered "late". If omitted, ask the user to pick from the actual participant list.

## Steps

### 1. List active participants

```
participants = list_active_participants(conference_name=<conference>)
```

If `objects` is empty: the conference is no longer running. Tell the user, stop.

### 2. Identify "late joiners"

If `cutoff_time` was provided:
- Convert to UTC ISO 8601.
- Filter `objects` by `connect_time >= cutoff_utc`.

Otherwise:
- Show the user the full participant list with `display_name` + `connect_time` (UTC → user's local TZ).
- Ask them to confirm which ones to disconnect.

### 3. **Confirmation gate**

Before any disconnect, surface:

```
About to disconnect <N> participant(s) from conference "<conference>":
  - <display_name> (joined <connect_time>)
  - <display_name> (joined <connect_time>)
  - …

These users will be dropped from the call immediately. Proceed?
```

Wait for explicit "yes" / "proceed" / "go ahead". For "no" or anything ambiguous, stop and ask what to do instead.

(Skip this gate only if the user's original request was unambiguous AND named the targets by exact `display_name` or `participant_id`.)

### 4. Disconnect each one

```
for p in late_arrivals:
    disconnect_participant(participant_id=p["id"])
```

`disconnect_participant` is idempotent — a 404 returns `note: "already disconnected"`, which is fine.

If any call fails with non-404, **stop the loop**, report which participant errored, and ask the user how to proceed.

### 5. Lock the conference

```
conf = list_active_conferences(name=<conference>)
if not conf["objects"]:
    # Race condition — last participant left while we were disconnecting.
    return "Conference is no longer running. Nothing left to lock."
lock_conference(conference_id=conf["objects"][0]["id"])
```

### 6. Report back

```
Done:
- Disconnected: <list of display_names>
- Locked: <conference> (new joiners will wait at "Waiting for host")

Remaining in the meeting: <count from another list_active_participants call>
```

## Variations

### Mute all guests instead of disconnecting

Replace step 4 with:

```
conf = list_active_conferences(name=<conference>)
mute_guests(conference_id=conf["objects"][0]["id"])
```

Mute is reversible (`unmute_guests`); disconnect is not. Prefer mute for "running too loud" cases; reserve disconnect for actual policy violations.

### End the meeting entirely

Replace steps 2-5 with:

```
conf = list_active_conferences(name=<conference>)
disconnect_conference(conference_id=conf["objects"][0]["id"])
```

DESTRUCTIVE — boots **everyone**. Always confirm before invoking. Useful for "this meeting was scheduled by mistake, kill it" not for routine cleanup.

## Safety

This is a destructive recipe. Every step that mutates state passes through the confirmation gate in step 3. The recipe will refuse to proceed without explicit user "yes" unless the original request was unambiguous.

For the full rule set on when confirmation can be skipped, see `pexip-operations/safety.md`.

## Reference source

- Skill: `pexip-operations/live-meeting-ops.md`, `pexip-operations/safety.md`
- MCP tools:
  - `list_active_participants`, `list_active_conferences` in `src/pexip_mcp/tools/status.py`
  - `disconnect_participant`, `lock_conference`, `mute_guests`, `disconnect_conference` in `src/pexip_mcp/tools/command.py`
- Pexip docs: https://docs.pexip.com/api_manage/api_command.htm
