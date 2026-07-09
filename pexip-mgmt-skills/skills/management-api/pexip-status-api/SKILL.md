---
name: pexip-status-api
description: Use when adding, modifying, or debugging MCP tools that read live runtime state from Pexip Infinity — active conferences, currently-connected participants, Conferencing Node load, backplane media stats, alarms, licensing usage, cloud overflow recommendations, participant media streams, call quality. Triggers on `/api/admin/status/v1/`, `conference` (status), `participant` (status), `worker_vm`, `alarm`, `licensing`, `participant_media_stream`, `participant_call_quality`, `backplane`, `cloud_overflow_recommendation`, `tools/status.py`. Do NOT use for post-call/historical/CDR data (use `pexip-history-api`) or for state-changing actions on live meetings (use `pexip-command-api`).
license: MIT
---

# Pexip Infinity Management — Status API

Read-only API exposing the **live runtime state** of the Pexip Infinity platform. Use for monitoring, dashboards, "who's in this meeting right now" tools. For finished calls use the History API; for changing configuration use the Configuration API.

## Base URL

```
https://<management-node-host>/api/admin/status/v1/<resource>/
```

- Same authentication as the Configuration API: HTTP Basic over HTTPS (or OAuth/LDAP if configured).
- Same 1,000 req/60s rate limit applies platform-wide across all admin APIs.
- Same Tastypie-style listing: `meta` + `objects`, `?limit=&offset=`, `?field=value`, `?order_by=`.
- Schema introspection at `…/<resource>/schema/?format=json`.
- **GET only.** Status is read-only. Use the Command API to change state.

## Core resources

### `conference/` — active conference instances
`/api/admin/status/v1/conference/`

One object per **currently running** instance of a VMR/Service. Empty list = nothing is in progress.
Useful fields: `name` (the dialed alias / service name), `service_type`, `tag`, `start_time`, `is_locked`, `is_started`, `guests_muted`, `participant_count`, `instance_id`.

Filter examples:
- `?service_type=conference` — VMRs only.
- `?name=team-standup` — instances of a specific VMR.

### `participant/` — currently connected participants
`/api/admin/status/v1/participant/`

One object per active call leg.
Useful fields: `display_name`, `remote_address`, `protocol` (`api`, `sip`, `h323`, `mssip`, `webrtc`, `rtmp`, `teams`, `gms`), `call_direction` (`in`/`out`), `call_quality` (string `'1_good'`, `'2_ok'`, `'3_bad'`, `'4_terrible'`), `connect_time`, `conversation_id`, `conference` (name of the parent instance), `service_tag`, `is_presenting`, `is_muted`, `role` (`chair`/`guest`), `system_location`, `media_node` (which Conferencing Node is handling media).

Common query: `?conference=<conference-name>` to list everyone in a specific live meeting.

### `worker_vm/` — Conferencing Node status
`/api/admin/status/v1/worker_vm/`

Live load and health for each Conferencing Node.
Useful fields: `name`, `node_type`, `system_location`, `version`, `boot_time`, `last_reported`, `media_load`, `signaling_count`, `max_audio_calls`, `max_full_hd_calls`, `max_hd_calls`, `max_sd_calls`, `cpu_count`, `total_ram`, `sync_status` (`SYNCED`/`SYNCING`/`OUT_OF_SYNC`), `maintenance_mode`, `upgrade_status`, `cloud_bursting` (bool — is this an overflow node).

### `backplane/` — backplane (cluster-internal media) statistics
`/api/admin/status/v1/backplane/`

Per-stream stats for the inter-node backplane that links participants on different Conferencing Nodes.
Useful for diagnosing cross-node media issues. Fields include `media_type`, `tx_bitrate`, `rx_bitrate`, `tx_packet_loss`, `rx_packet_loss`, `tx_resolution`, `rx_resolution`, `local_node`, `remote_node`.

### `alarm/` — active alarms
`/api/admin/status/v1/alarm/`

Active warning/error alarms surfaced in the admin UI.
Fields: `name` (machine code), `details` (human description), `level` (`error`/`warning`/`info`), `node` (FK to worker_vm), `time_raised`, `instance` (subsystem).

This is the right surface for an MCP tool like "show me active platform problems".

### `licensing/` — port usage
`/api/admin/status/v1/licensing/`

Live concurrent-usage counts vs entitlement: `audio_ports_used`, `audio_ports_max`, `port_used`, `port_max`, `system_location` (FK), etc. Useful for capacity-monitoring tools.

### `cloud_overflow_recommendation/` — burst predictions
`/api/admin/status/v1/cloud_overflow_recommendation/`

Cloud bursting recommendations from the Management Node (when configured). Fields include `system_location`, `recommended_nodes`, `current_nodes`, `reason`.

### Other status resources worth knowing

- `participant_media_stream/` — per-participant per-stream media stats (use participant `id` to filter). Fields include `media_type`, `rx_codec`/`tx_codec`, `rx_resolution`/`tx_resolution`, `rx_bitrate`/`tx_bitrate`, `rx_packet_loss`/`tx_packet_loss`, `rx_jitter`/`tx_jitter`.
- `participant_call_quality/` — fine-grained quality breakdown for a participant.
- `external_participant/` — federated/external party metadata.
- `media_processing_server/` — media MCU pool status (in newer versions).
- `connectivity/` — node-to-node reachability matrix.
- `dns_lookup/` — recent DNS lookups, useful for diagnosing call routing.

## Linking status objects to configuration

Many status fields reference configuration objects by **name**, not by URI/ID — e.g. `participant.conference` is the conference instance name (which often matches a `conference_alias.alias`), and `worker_vm.system_location` is the location name. To follow back to the configuration object, do a filtered Configuration API list (`?name=...`).

## MCP tool design notes

- **Status objects are ephemeral.** A participant disappears the moment they hang up; a conference disappears when the last participant leaves. Never cache across tool invocations.
- **Default to filtered queries.** A busy platform can have thousands of active participants — never `GET /participant/` unfiltered for a tool response.
- **For "live dashboard" style tools, prefer event sinks** (configured directly in Pexip by an admin — see the `pexip-event-sinks` skill) for push notifications, instead of polling Status. The Status API is fine for one-shot questions.
- **`call_quality` strings have a numeric prefix** (`'1_good'` … `'4_terrible'`). Sort by it as a string and you'll get the right order.
- **Distinguish empty vs error.** `200 OK` with `objects: []` means "nothing active" — surface that as a normal empty result, not an error.

## Quick-reference URIs

```
Active conferences:    GET  /api/admin/status/v1/conference/
Participants in VMR:   GET  /api/admin/status/v1/participant/?conference=<name>
Conferencing Nodes:    GET  /api/admin/status/v1/worker_vm/
Active alarms:         GET  /api/admin/status/v1/alarm/
Live licensing usage:  GET  /api/admin/status/v1/licensing/
Backplane media:       GET  /api/admin/status/v1/backplane/
Schema for any:        GET  /api/admin/status/v1/<resource>/schema/?format=json
```

## Authoritative docs

- Status API: https://docs.pexip.com/api_manage/api_status.htm
- Overview: https://docs.pexip.com/api_manage/management_intro.htm
- Event sinks (push-based alternative): https://docs.pexip.com/admin/event_sink.htm
