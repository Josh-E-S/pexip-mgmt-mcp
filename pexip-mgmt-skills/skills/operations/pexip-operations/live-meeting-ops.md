# Live meeting operations

For "what's happening right now" and "do something to a running meeting" requests. Combines the Status API (read live state) and the Command API (act on live state).

## The fundamental flow: resolve → confirm → act

Live commands operate on **UUIDs** (`participant_id`, `conference_id`), not names. UUIDs only exist while the call is live and you get them from the Status API. Every live-control task is three steps:

1. **Resolve.** Status query that turns a human label ("Alice", "standup") into a UUID.
2. **Confirm.** Show the user who/what you're about to act on. Skip this only if the user named the target unambiguously.
3. **Act.** Command API call with the UUID.

Repeated `participant_id` / `conference_id` arguments below all refer to UUIDs from step 1.

## Recipes

### Who's in a meeting?

```
list_active_participants(conference_name="<vmr alias>")
```

Returns one object per call leg. Useful fields:
- `id` — UUID, needed for any per-participant command.
- `display_name`, `remote_address`, `protocol`, `role` (`chair`/`guest`).
- `call_quality` — string `'1_good'` / `'2_ok'` / `'3_bad'` / `'4_terrible'` (numeric-prefixed so string sort works).
- `connect_time`, `is_muted`, `is_presenting`, `media_node`.

If `conference_name` is omitted you'll page through everyone on the platform — fine on a small deployment, painful on a large one. Always scope.

### Kick one participant

```
participants = list_active_participants(conference_name="<vmr alias>")
# match display_name → exactly one object → take its id
disconnect_participant(participant_id=<uuid>)
```

Idempotent: a 404 (already disconnected) is treated as success with `note: "already disconnected"`.

If there are zero or multiple matches in step 1, **stop and surface the ambiguity** — never guess. "Alice" might match `Alice Smith` and `Alice Jones`; either ask which, or list both and stop.

### Kick everyone (end the meeting)

```
conf = list_active_conferences(name="<vmr alias>")  # → conf["objects"][0]["id"]
disconnect_conference(conference_id=<uuid>)
```

DESTRUCTIVE: every connected participant is dropped. **Always confirm with the user first** — the cost of being wrong is a whole meeting ending.

### Mute / unmute one

```
mute_participant(participant_id=<uuid>)
unmute_participant(participant_id=<uuid>)
video_mute_participant(participant_id=<uuid>)
video_unmute_participant(participant_id=<uuid>)
```

All idempotent.

### Mute all guests

```
mute_guests(conference_id=<uuid>)
unmute_guests(conference_id=<uuid>)
```

Only affects participants with `role=guest`. Hosts/chairs unaffected.

### Lock / unlock the meeting

```
lock_conference(conference_id=<uuid>)
unlock_conference(conference_id=<uuid>)
```

Locked = new joiners held at the "Waiting for host" screen until unlocked.

### Spotlight a presenter

```
spotlight_participant(participant_id=<uuid>)
unspotlight_participant(participant_id=<uuid>)
```

Pinned participant is shown as the main view regardless of who's speaking.

### Change layout

```
set_conference_layout(
    conference_id=<uuid>,
    host_layout="four_mains_zero_pips",   # or guest_layout=, or both
)
```

Valid layout enum values are in `layouts.json` (sibling). The Pexip set includes:
`one_main_zero_pips`, `one_main_seven_pips`, `two_mains_zero_pips`, `two_mains_seven_pips`, `four_mains_zero_pips`, `nine_equal`, `sixteen_equal`, `twenty_five_equal`, plus several speakers + presentation variants.

### Promote / demote (chair ↔ guest)

```
set_participant_role(participant_id=<uuid>, role="chair")
set_participant_role(participant_id=<uuid>, role="guest")
```

### Transfer a participant to another meeting

```
transfer_participant(
    participant_id=<uuid>,
    conference_alias="<target alias>",
    role="guest",        # optional
    pin="1234",          # optional, if target is PIN-protected
)
```

Not idempotent — once moved, the source `participant_id` no longer points anywhere.

### Dial someone INTO a meeting

```
dial_participant(
    conference_alias="<vmr alias>",      # what to dial INTO
    destination="sip:alice@example.com",  # who to dial OUT to
    protocol="sip",          # sip / h323 / mssip / rtmp / teams / gms / auto
    call_type="video",       # audio / video / video-only / audio-video
    role="guest",
    remote_display_name="Alice (mobile)",
)
```

Not idempotent — each call places a new outbound leg. Repeated calls dial repeatedly.

## Combined playbook: "Standup is running long — kick the late joiners and lock"

```
participants = list_active_participants(conference_name="standup")
# Filter to people who joined after the scheduled start.
# Surface the list to the user, ask for confirmation.
for p in late_arrivals:
    disconnect_participant(participant_id=p["id"])
conf = list_active_conferences(name="standup")
lock_conference(conference_id=conf["objects"][0]["id"])
```

## Live call quality — is Bob's call OK?

```
participants = list_active_participants(conference_name="<vmr alias>")
# match display_name → take id
get_participant_quality(participant_id=<uuid>)
```

Returns the participant record + all media streams (per-stream rx/tx bitrate, packet loss, jitter, codec, resolution). Read `call_quality` (the rolled-up bucket) and the per-stream `rx_packet_loss` / `tx_packet_loss` for diagnosis.

For **post-call** quality forensics (deeper, includes `bucketed_call_quality` and `historic_call_quality`), use `get_history_participant` once the call ends — see `reporting.md`.

## What to avoid

- **Don't `list_active_participants` unfiltered on a large platform** — you'll page through thousands of objects. Always scope by `conference_name`, `role`, or `protocol`.
- **Don't cache UUIDs across tool calls.** A participant disappears the instant they hang up; reusing a stale UUID returns 404.
- **Don't `disconnect_conference` to "clean up" or "reset" a meeting unless the user asked.** It ends the meeting for everyone.
- **Don't send DTMF or text overlays** — the MCP server intentionally doesn't expose those (`set_text_overlay`, `participant/dtmf`) because they inject content into live calls.
