---
name: pexip-command-api
description: Use when adding, modifying, or debugging MCP tools that actively control in-progress Pexip Infinity conferences and participants — dial new participants, disconnect (kick), mute, video-mute, lock conferences, mute_guests, transfer, set_role, spotlight, change layout, transform_layout. Triggers on `/api/admin/command/v1/`, `participant/disconnect`, `participant/dial`, `participant/mute`, `conference/lock`, `conference/disconnect`, `conference/mute_guests`, `conference/transform_layout`, `tools/command.py`, and on user verbs like "kick", "boot", "mute everyone", "lock the meeting", "dial out", "transfer". Do NOT use for reads of live state (use `pexip-status-api`), persistent configuration (use `pexip-config-api`), or post-call data (use `pexip-history-api`).
license: MIT
---

# Pexip Infinity Management — Command API

POST-only API for **acting on running conferences and participants**. Distinct from:
- Configuration API (CRUD on persistent platform objects)
- Status API (read-only live state)
- History API (post-call CDRs)

Commands are imperative ("disconnect this participant"), not declarative ("delete this VMR").

## Base URL

```
https://<management-node-host>/api/admin/command/v1/<scope>/<command>/
```

- `<scope>` is typically `conference`, `participant`, or `platform`.
- All commands are **POST** (even read-ish ones — that is the API convention).
- Auth, rate limit, schema introspection same as the other admin APIs (Basic over HTTPS, 1,000/60s, `…/schema/?format=json`).
- Response is `200 OK` with a small JSON body, often `{"status": "success", "data": {...}}` or just `{"status": "success"}`.

## Targeting an instance

Most commands need to identify which conference instance or participant to act on. Two patterns appear, depending on the command:

1. **`conference_id` + `participant_id`** in the POST body — Pexip-internal UUIDs that you obtain from the Status API (`/api/admin/status/v1/conference/<id>/` or `/participant/<id>/`).
2. **`conference_name`** (the dialed alias) in the POST body — for commands that act on the conference as a whole and you only know it by name.

Always introspect the schema (`…/schema/?format=json`) for the exact required field names per command — they shifted between Pexip versions.

## Participant commands

`/api/admin/command/v1/participant/<command>/`

| Command | Effect | Typical body |
| --- | --- | --- |
| `dial` | Dial a new participant into a conference. | `conference_alias` (or `destination`), `protocol` (`sip`/`h323`/`mssip`/`rtmp`/`teams`/`gms`/`auto`), `call_type` (`audio`/`video`/`video-only`/`audio-video`), `role` (`chair`/`guest`), `system_location`, `streaming` (bool), `remote_display_name`, `dtmf_sequence` |
| `disconnect` | Disconnect a single participant. | `participant_id` |
| `mute` / `unmute` | Audio mute one participant. | `participant_id` |
| `video_mute` / `video_unmute` | Video mute one participant. | `participant_id` |
| `set_role` | Change role to `chair` or `guest`. | `participant_id`, `role` |
| `spotlight_on` / `spotlight_off` | Pin a participant in the layout. | `participant_id` |
| `transfer` | Move participant to another conference. | `participant_id`, `conference_alias`, optional `role`, `pin` |
| `dtmf` | Send DTMF tones into the call. | `participant_id`, `digits` |
| `set_text_overlay` | Display caption text under participant. | `participant_id`, `text` |

## Conference commands

`/api/admin/command/v1/conference/<command>/`

| Command | Effect | Typical body |
| --- | --- | --- |
| `disconnect` | Disconnect **all** participants in a conference (ends the meeting). | `conference_id` |
| `lock` / `unlock` | Lock the conference; new joiners are held at "Waiting for host". | `conference_id` |
| `mute_guests` / `unmute_guests` | Mute/unmute everyone with `guest` role. | `conference_id` |
| `start_conference` | Force-start a conference still in "waiting" state. | `conference_id` |
| `set_layout` | Change the active layout for the conference. | `conference_id`, `layout` (e.g. `one_main_zero_pips`, `two_mains_seven_pips`, `four_mains_zero_pips`, `nine_equal`, `sixteen_equal`), optional `host_layout`/`guest_layout` |
| `transform_layout` | Apply layout + indicators in one call (live-captions indicator, AI-enabled indicator, etc.). | `conference_id`, `transforms` object |

## Platform commands

`/api/admin/command/v1/platform/<command>/`

Less commonly used but include things like:
- `cloud_node_create` / `cloud_node_delete` — manage cloud-bursting nodes.
- `update_software` — push an upgrade.
- `restart_conferencing_node` — restart a specific node.

These are administrative and **destructive**; gate behind explicit user confirmation in any MCP tool.

## Errors

- `400` — bad/missing parameters (read the JSON body).
- `404` — `participant_id` or `conference_id` no longer exists (the call already ended). Treat as a soft "already gone" rather than a hard error in tools where appropriate.
- `409` — conflict (e.g. lock a conference that's already locked).
- `429` — rate-limited.

## MCP tool design notes — read carefully

- **Commands have real-world side effects.** Disconnecting a participant boots a real human off a real call. Locking a conference can leave latecomers stranded. MCP tools that wrap commands MUST:
  - Be named unambiguously (`pexip_disconnect_participant`, not `pexip_remove_user`).
  - Require explicit identifiers — never accept a fuzzy "the meeting Bob is in".
  - Return a clear success/failure report including who/what was acted on.
- **Name resolution is server-side in pexip-mgmt-mcp.** A natural-language input ("kick Alice from the standup") is one tool call: `disconnect_participant(participant_id="Alice", conference="standup")`. The server resolves the display name against currently connected participants via the Status API — zero matches raise a 404, ambiguous matches raise a 409 so the agent must disambiguate before acting. If you are wrapping the raw API yourself (without this server), do that resolution explicitly: list participants, match `display_name`, error on zero/multiple, then POST `participant/disconnect/` with the UUID.
- **Idempotency.** Most commands are not idempotent at the protocol level (you can call `disconnect` twice; the second returns 404). Treat 404-after-success as "already done".
- **Confirmation for destructive verbs.** For `conference/disconnect` (ends a whole meeting), `platform/restart_conferencing_node`, etc., consider requiring a confirmation flag in the tool input.
- **Don't expose `dtmf` / `set_text_overlay` to untrusted callers** — they can be used to inject content into live calls.

## Quick-reference URIs

```
Dial out:           POST  /api/admin/command/v1/participant/dial/
Disconnect one:     POST  /api/admin/command/v1/participant/disconnect/
Mute one:           POST  /api/admin/command/v1/participant/mute/
End a meeting:      POST  /api/admin/command/v1/conference/disconnect/
Lock a meeting:     POST  /api/admin/command/v1/conference/lock/
Mute all guests:    POST  /api/admin/command/v1/conference/mute_guests/
Change layout:      POST  /api/admin/command/v1/conference/transform_layout/
Schema for any:     GET   /api/admin/command/v1/<scope>/<command>/schema/?format=json
```

## Authoritative docs

- Command API: https://docs.pexip.com/api_manage/api_command.htm
- Disconnecting participants: https://docs.pexip.com/admin/disconnecting_participant.htm
- Overview: https://docs.pexip.com/api_manage/management_intro.htm
