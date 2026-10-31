# Live meeting operations

For "what's happening right now" and "do something to a running meeting" requests. Combines the Status API (read live state) and the Command API (act on live state).

## The fundamental flow: identify → confirm → act

Live commands accept **names**: `participant="Alice"` (display name) and
`conference="Standup"` (conference name or alias). The server resolves them to
the live UUID itself, so when the user names the target you can act directly.
UUIDs (from `pexip_list_active_participants` / `pexip_list_active_conferences`)
are still accepted and are the way to disambiguate when a name matches several
people or meetings (the tool returns 409 and says so).

1. **Identify.** If the user did not name the target ("kick whoever joined late"),
   query the Status API to find out who.
2. **Confirm.** Show the user who/what you're about to act on. Skip this only if
   the user named the target unambiguously.
3. **Act.** Command API call with the name (or UUID).

`participant` / `conference` arguments below accept a name or a UUID.

## Recipes

### Who's in a meeting?

```
pexip_list_active_participants(conference_name="<vmr alias>")
```

Returns one object per call leg. Useful fields:
- `id` — UUID; pass it to a per-participant command when a display name is ambiguous.
- `display_name`, `remote_address`, `protocol`, `role` (`chair`/`guest`).
- `call_quality` — string `'1_good'` / `'2_ok'` / `'3_bad'` / `'4_terrible'` (numeric-prefixed so string sort works).
- `connect_time`, `is_muted`, `is_presenting`, `media_node`.

If `conference_name` is omitted you'll page through everyone on the platform — fine on a small deployment, painful on a large one. Always scope.

### Kick one participant

```
participants = pexip_list_active_participants(conference_name="<vmr alias>")
# match display_name → exactly one object → take its id
pexip_disconnect_participant(participant=<name or uuid>)
```

Idempotent: a 404 (already disconnected) is treated as success with `note: "already disconnected"`.

If there are zero or multiple matches in step 1, **stop and surface the ambiguity** — never guess. "Alice" might match `Alice Smith` and `Alice Jones`; either ask which, or list both and stop.

### Kick everyone (end the meeting)

```
conf = pexip_list_active_conferences(name="<vmr alias>")  # → conf["objects"][0]["id"]
pexip_disconnect_conference(conference=<name or uuid>)
```

DESTRUCTIVE: every connected participant is dropped. **Always confirm with the user first** — the cost of being wrong is a whole meeting ending.

### Mute / unmute one

```
pexip_mute_participant(participant=<name or uuid>)
pexip_unmute_participant(participant=<name or uuid>)
video_mute_participant(participant=<name or uuid>)
video_unmute_participant(participant=<name or uuid>)
```

All idempotent.

### Mute all guests

```
pexip_mute_guests(conference=<name or uuid>)
pexip_unmute_guests(conference=<name or uuid>)
```

Only affects participants with `role=guest`. Hosts/chairs unaffected.

### Lock / unlock the meeting

```
pexip_lock_conference(conference=<name or uuid>)
pexip_unlock_conference(conference=<name or uuid>)
```

Locked = new joiners held at the "Waiting for host" screen until unlocked.

### Spotlight a presenter

```
spotlight_participant(participant=<name or uuid>)
unspotlight_participant(participant=<name or uuid>)
```

Pinned participant is shown as the main view regardless of who's speaking.

### Change layout

```
pexip_set_conference_layout(
    conference=<name or uuid>,
    host_layout="four_mains_zero_pips",   # or guest_layout=, or both
)
```

Valid layout enum values are in `layouts.json` (sibling). The Pexip set includes:
`one_main_zero_pips`, `one_main_seven_pips`, `two_mains_zero_pips`, `two_mains_seven_pips`, `four_mains_zero_pips`, `nine_equal`, `sixteen_equal`, `twenty_five_equal`, plus several speakers + presentation variants.

### Promote / demote (chair ↔ guest)

```
pexip_set_participant_role(participant=<name or uuid>, role="chair")
pexip_set_participant_role(participant=<name or uuid>, role="guest")
```

### Transfer a participant to another meeting

```
pexip_transfer_participant(
    participant=<name or uuid>,
    conference_alias="<target alias>",
    role="guest",        # optional
    pin="1234",          # optional, if target is PIN-protected
)
```

Not idempotent — once moved, the source `participant_id` no longer points anywhere.

### Dial someone INTO a meeting

```
pexip_dial_participant(
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
participants = pexip_list_active_participants(conference_name="standup")
# Filter to people who joined after the scheduled start.
# Surface the list to the user, ask for confirmation.
for p in late_arrivals:
    pexip_disconnect_participant(participant=p["id"])
conf = pexip_list_active_conferences(name="standup")
pexip_lock_conference(conference=conf["objects"][0]["id"])
```

## Live call quality — is Bob's call OK?

```
participants = pexip_list_active_participants(conference_name="<vmr alias>")
# match display_name → take id
pexip_get_participant_quality(participant=<name or uuid>)
```

Returns the participant record + all media streams (per-stream rx/tx bitrate, packet loss, jitter, codec, resolution). Read `call_quality` (the rolled-up bucket) and the per-stream `rx_packet_loss` / `tx_packet_loss` for diagnosis.

For **post-call** quality forensics (deeper, includes `bucketed_call_quality` and `historic_call_quality`), use `pexip_get_history_participant` once the call ends — see `reporting.md`.

## What to avoid

- **Don't `pexip_list_active_participants` unfiltered on a large platform** — you'll page through thousands of objects. Always scope by `conference_name`, `role`, or `protocol`.
- **Don't cache UUIDs across tool calls.** A participant disappears the instant they hang up; reusing a stale UUID returns 404.
- **Don't `pexip_disconnect_conference` to "clean up" or "reset" a meeting unless the user asked.** It ends the meeting for everyone.
- **Don't send DTMF or text overlays** — the MCP server intentionally doesn't expose those (`set_text_overlay`, `participant/dtmf`) because they inject content into live calls.
