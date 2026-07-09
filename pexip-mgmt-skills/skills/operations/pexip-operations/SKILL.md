---
name: pexip-operations
description: Operate a Pexip Infinity deployment through the pexip-mgmt MCP server — run call-volume and quality reports from CDRs, control live meetings (kick / mute / lock / transfer / change layout / dial out), administer VMRs / aliases / end users / dial-plan rules, and check platform health (alarms, node load, licensing). Triggers on `list_active_participants`, `disconnect_participant`, `mute_participant`, `lock_conference`, `summarize_calls`, `list_history_participants`, `get_participant_quality`, `list_alarms`, `get_licensing_status`, `create_vmr`, `add_vmr_alias`, `list_gateway_rules`, and on user verbs like "kick", "boot", "mute everyone", "lock the meeting", "dial out", "who's in", "calls today", "bad-quality calls", "any alarms", "add an alias", "new VMR". Do NOT use for modifying the MCP server's Python code itself (use `pexip-config-api` / `pexip-status-api` / `pexip-history-api` / `pexip-command-api`).
license: MIT
---

# Pexip Infinity operations runbook

You are operating a Pexip Infinity deployment via the **pexip-mgmt** MCP server. The server exposes 122 typed tools (46 Configuration, 39 Status, 14 History, 23 Command) wrapping Pexip's four admin APIs:

| Domain | Tools | When to reach for it |
|---|---|---|
| **Live meetings** | `list_active_*`, `disconnect_*`, `mute_*`, `lock_conference`, `transfer_participant`, `set_conference_layout`, `dial_participant` | The meeting is happening **right now**. |
| **Reporting / CDRs** | `summarize_calls`, `list_history_*`, `get_history_participant` | The meeting is **over** — usage, quality forensics, billing. |
| **Platform health** | `list_alarms`, `list_node_status`, `get_licensing_status`, `get_participant_quality` | "Is the platform OK?", "Why is Bob's call choppy?" |
| **Configuration** | `*_vmr`, `*_alias`, `*_end_user`, `*_gateway_rule`, `*_automatic_participant`, `*_ldap_source`, `get_resource_schema` | Long-lived objects — VMRs, dial plan, directory. |

## When to use

- "Who's in the standup right now?" → live meeting state
- "Kick the late joiners and lock" → live meeting control
- "Total calls today, broken out by direction" → reporting
- "Show me yesterday's bad-quality calls" → quality forensics
- "Add `meet.alice@example.com` as an alias on AllHands" → configuration
- "Any active alarms?" / "Are we close to the license cap?" → platform health

## Routing decisions in one place

```
Question mentions…              →  Load sibling doc
"right now" / live / kick       →  live-meeting-ops.md
yesterday / last week / report  →  reporting.md
alarms / nodes / licensing      →  platform-health.md
VMR / alias / end user / theme  →  vmr-administration.md
dial plan / gateway / routing   →  dial-plan.md
"will this disconnect…"         →  safety.md  (read BEFORE acting)
"which tool does…"              →  tool-index.md
```

Sibling files are not loaded into context until you read them. Pull only the one that matches the user's question.

## Three rules that apply everywhere

1. **Live commands need UUIDs from the Status API first.** `disconnect_participant`, `mute_participant`, `lock_conference`, etc. all take a UUID. Names won't work. The flow is always:
   `list_active_participants(conference_name=…)` → pick the right `id` from `objects` → `disconnect_participant(participant_id=<uuid>)`.
   Surface who you're about to act on in plain text before invoking the destructive tool. See `safety.md`.

2. **Counts and totals use `summarize_calls`, not list-then-count.** It paginates server-side, walks up to 10,000 participants, and returns counts + duration totals grouped by `call_direction` / `call_quality` / `protocol` / `service_tag` / `system_location` / `conference_name` / `disconnect_reason` / `vendor`. Cheaper on tokens and tool calls than `list_history_participants` for any "how many / how long" question.

3. **Don't guess Pexip field names.** When a config field isn't in the reference docs, call `get_resource_schema("<resource>")` to fetch the live schema (fields, types, required-ness, enum values). Schemas drift between Pexip versions. The resources you'll need most: `conference`, `conference_alias`, `end_user`, `system_location`, `worker_vm`, `gateway_routing_rule`, `automatic_participant`, `ldap_sync_source`, `ivr_theme`, `global`.

## Time format

All Pexip timestamps are **UTC, ISO 8601** (e.g. `2026-05-19T00:00:00`). Convert from the user's local time on input, convert back on output. Pexip retains only the last **10,000 conference instances** — for queries over wider ranges the `summarize_calls` response will set `truncated: true` and you should mention that to the user.

## Two-letter cheatsheet for the 16 most-used tools

```
list_active_conferences         live conferences (filter by name/service_type)
list_active_participants        live participants  (filter by conference_name)
disconnect_participant          kick one (needs UUID)
mute_participant                audio-mute one     (needs UUID)
lock_conference                 hold latecomers    (needs UUID)
mute_guests                     mute role=guest    (needs UUID)
set_conference_layout           change layout      (needs UUID + layout enum)
dial_participant                outbound to add someone
transfer_participant            move participant to another conference
summarize_calls                 aggregate CDRs by group_by
list_history_conferences        past meetings in a time window
list_history_participants       per-leg CDRs
get_history_participant         deep quality (bucketed_call_quality)
list_alarms                     active platform alarms
get_licensing_status            port usage vs entitlement
get_resource_schema             introspect any config resource's fields
```

Everything else: see `tool-index.md`.

## Safety defaults

Before any destructive call (`disconnect_*`, `delete_*`, `update_global_settings`, `transfer_participant`, `disconnect_conference`) — repeat back the target and ask for confirmation **unless the user's request was unambiguous and named the target by exact id or name**. "Kick Alice" → safe to proceed after resolving Alice to one UUID; "Tidy up the meeting" → confirm first. Detailed rules in `safety.md`.

## Bundled helpers

- `healthcheck.sh` — smoke-test the MCP server is reachable and authed. Runs `python -m pexip_mcp --healthcheck`.
- `pexip_report.py` — pretty-print a `summarize_calls` JSON response as Markdown. Pipe the tool's response in and paste the output into a doc, ticket, or email.
- `layouts.json` — valid `host_layout` / `guest_layout` enum values for `set_conference_layout`.
- `disconnect-reasons.json` — common `disconnect_reason` strings for filtering CDRs.

## Reference source

- **Authoritative Pexip docs:**
  - API overview: https://docs.pexip.com/api_manage/management_intro.htm
  - Configuration API: https://docs.pexip.com/api_manage/api_configuration.htm
  - Status API: https://docs.pexip.com/api_manage/api_status.htm
  - History API: https://docs.pexip.com/api_manage/api_history.htm
  - Command API: https://docs.pexip.com/api_manage/api_command.htm
- **MCP server source:** `src/pexip_mcp/tools/` (one file per Pexip resource family)
- **Related skills:**
  - Developer reference (modify the MCP server itself): `pexip-config-api`, `pexip-status-api`, `pexip-history-api`, `pexip-command-api`
  - Event-driven companion (webhook events): `pexip-event-sinks`
  - Router: `pexip-mgmt-intake`
