---
name: pexip-history-api
description: Use when adding, modifying, or debugging MCP tools that read post-call data from Pexip Infinity — Call Detail Records (CDRs), historical conferences and participants, call quality summaries, packet loss / bitrate stats, disconnect reasons, bucketed_call_quality, historic_call_quality. Triggers on `/api/admin/history/v1/`, `conference` (history), `participant` (history), `summarize_calls`, `list_history_conferences`, `list_history_participants`, `get_history_participant`, `start_time__gte`, `disconnect_reason`, `call_quality`, `tools/history.py`. Do NOT use for live in-progress meetings (use `pexip-status-api`) or for state-changing actions (use `pexip-command-api`).
license: MIT
---

# Pexip Infinity Management — History API

Read-only API for **finished** conferences and the participants who were in them. This is the source for CDRs, usage reporting, billing exports, and call-quality forensics.

## Base URL

```
https://<management-node-host>/api/admin/history/v1/<resource>/
```

- Auth, rate limit, listing/filtering/schema introspection identical to the other admin APIs.
- **GET only.**
- A conference instance moves from Status to History the moment its last participant disconnects.

## Retention

- The Management Node retains **up to 10,000 conference instances** plus all their participants. Beyond that, oldest entries are deleted FIFO.
- For long-term retention, export to an external warehouse on a schedule (event sinks or periodic History API pulls).

## Core resources

### `conference/` — completed conference instances
`/api/admin/history/v1/conference/`

Fields include: `name`, `service_type`, `tag`, `start_time`, `end_time`, `duration` (seconds), `instance_id`, `participant_count`.

Common queries:
- `?start_time__gte=2026-04-01T00:00:00&start_time__lt=2026-05-01T00:00:00` — calendar-month report.
- `?service_type=conference&order_by=-start_time&limit=50` — most recent VMR meetings.
- `?name=team-standup` — every past instance of a specific VMR.

### `participant/` — completed participant call legs
`/api/admin/history/v1/participant/`

Fields include:
- Identity: `display_name`, `remote_address`, `local_alias`, `protocol`, `call_direction` (`in`/`out`), `call_uuid`, `conversation_id`.
- Membership: `conference` (the parent conference *name*), `conference_name`, `role`, `service_tag`, `system_location`.
- Timing: `connect_time`, `disconnect_time`, `duration`.
- Outcome: `disconnect_reason` (e.g. `Call disconnected`, `Participant disconnected`, `Conference terminated`, `Call rejected`, `Call failed`).
- Quality summary: `call_quality` (`'1_good'` / `'2_ok'` / `'3_bad'` / `'4_terrible'`).
- Media stream summary: `media_streams` — a list of `{media_type, rx_bitrate, tx_bitrate, rx_packet_loss, tx_packet_loss, rx_resolution, tx_resolution, rx_codec, tx_codec, ...}` per stream the participant had.

Common queries:
- `?conference=<conference-name>` — every leg of one meeting.
- `?call_quality=4_terrible&disconnect_time__gte=2026-04-30T00:00:00` — bad-quality calls in the last day.
- `?disconnect_reason=Call+failed` — failed call audit.

### Per-participant deep quality data (only on individual GET)

When you GET **one specific participant** (`/participant/<id>/`), additional fields are populated that are **omitted from list responses for performance**:

- `historic_call_quality` — full per-window quality timeline.
- `bucketed_call_quality` — array `[unknown, good, ok, bad, terrible]` of counts. Example `[0, 7, 3, 1, 2]` = 0 unknown, 7 good, 3 ok, 1 bad, 2 terrible 20-second windows.

Quality classification rule:
- `< 1%` packet loss in a 20-second window → Good (1)
- `< 3%` → OK (2)
- `< 10%` → Bad (3)
- otherwise → Terrible (4)
- `0` = Unknown (no data)

## MCP tool design patterns

- **List-then-detail.** For "show me the bad calls and explain why" tools, list with `?call_quality=3_bad,4_terrible` (or `__in`), then GET each participant by id to get `bucketed_call_quality`. Cap detail-fanout (e.g. top 20 worst) to respect the 1,000/60s rate limit.
- **Time-window queries should always be inclusive-lower / exclusive-upper** to avoid double-counting at boundaries: `start_time__gte=...&start_time__lt=...`.
- **For aggregations (counts, totals, breakdowns), prefer the `summarize_calls` MCP tool** over fetching individual records. It paginates server-side with `limit=10000` (the per-request max) and returns counts + duration totals grouped by a chosen field.
- **Time format is ISO 8601 in UTC** (e.g. `2026-04-30T00:00:00`). Pexip stores and returns UTC; convert to the user's timezone on display, not on query.
- **CDR completeness.** The participant resource is the closest thing to a CDR. For billing-grade exports, prefer pulling on a schedule and storing externally — Pexip's 10,000-instance limit means high-volume platforms lose history fast.
- **Don't confuse `conference` (history)** — a string name — **with `conference` (configuration)** — a URI/FK. They look similar in JSON but mean different things.
- **`call_quality` strings sort lexicographically thanks to the numeric prefix** (`1_…` < `2_…` < `3_…` < `4_…`).

## Quick-reference URIs

```
Past conferences:           GET  /api/admin/history/v1/conference/
Past conferences in range:  GET  /api/admin/history/v1/conference/?start_time__gte=...&start_time__lt=...
All legs of one meeting:    GET  /api/admin/history/v1/participant/?conference=<name>
Participant deep quality:   GET  /api/admin/history/v1/participant/<id>/
Bad-quality calls:          GET  /api/admin/history/v1/participant/?call_quality__in=3_bad,4_terrible
Schema for any:             GET  /api/admin/history/v1/<resource>/schema/?format=json
```

## Authoritative docs

- History API: https://docs.pexip.com/api_manage/api_history.htm
- Viewing historical conferences (admin UI): https://docs.pexip.com/admin/conference_history.htm
- Overview: https://docs.pexip.com/api_manage/management_intro.htm
