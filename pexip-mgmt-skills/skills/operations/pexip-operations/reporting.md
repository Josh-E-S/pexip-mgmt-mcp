# Reporting and CDR queries

For "what happened" questions: usage reports, billing inputs, call-quality forensics on finished calls. Hits the History API. For live calls see `live-meeting-ops.md`.

## Three tools, one rule

| Tool | Use when |
|---|---|
| **`summarize_calls`** | The user wants **counts or totals** — "how many", "how long", "by direction / quality / protocol". |
| **`list_history_participants`** | The user wants **individual records** — "show me the bad-quality calls", "every leg of yesterday's standup". |
| **`get_history_participant`** | Drill down on **one specific record** — only here do you get `bucketed_call_quality` and `historic_call_quality`. |

**Rule of thumb: if the answer is a number or a chart, start with `summarize_calls`.** It walks pagination server-side up to the platform's 10,000-instance retention limit. Fetching individual records and counting in tool-call-land is strictly worse on tokens, latency, and rate limit.

## Time format

UTC, ISO 8601, no timezone suffix: `2026-05-19T00:00:00`. The user gives you their local time; convert. Output should convert back to their local timezone for display.

Time bounds are **inclusive lower, exclusive upper** to avoid double-counting at boundaries:

```
summarize_calls(start_time="2026-05-19T00:00:00", end_time="2026-05-20T00:00:00", …)
```

That's "all of May 19th UTC". For a week, set `end_time` to the start of the day **after** the last day you want.

## Recipe: usage report

```
summarize_calls(
    start_time="2026-05-19T00:00:00",
    end_time="2026-05-20T00:00:00",
    group_by="call_direction",   # in vs out
)
```

Response shape:

```jsonc
{
  "total_calls": 412,
  "total_duration_seconds": 173820,
  "average_duration_seconds": 421.9,
  "time_range": { "start": "...", "end": "..." },
  "group_by": "call_direction",
  "groups": {
    "in":  { "count": 290, "duration_seconds": 124800 },
    "out": { "count": 122, "duration_seconds": 49020 }
  },
  "truncated": false,
  "server_total_count": 412
}
```

`groups` is sorted by count descending. If `truncated: true`, you hit the 10,000-record cap before exhausting the window — mention this in the user-facing summary and suggest a narrower time range.

### Valid `group_by` values

```
call_direction       in / out
call_quality         1_good / 2_ok / 3_bad / 4_terrible (string-sortable)
protocol             sip / h323 / mssip / webrtc / rtmp / teams / api / gms
service_tag          free-form tag carried from the parent conference
system_location      datacenter / region name
conference_name      per-VMR breakdown
disconnect_reason    "Call disconnected", "Call failed", "Call rejected", …
vendor               client vendor string
```

### Additional filters

Any of these can be combined with `group_by`:

```
conference_name="standup"           # only one VMR
service_tag="billing-customer-x"    # only one tag
call_direction="out"                # only outbound (when group_by is something else)
location="eu-west"                  # one system_location
```

## Recipe: quality forensics

"Why were there so many bad calls last night?"

```
# 1. List the bad records.
bad = list_history_participants(
    start_time="2026-05-18T20:00:00",
    end_time="2026-05-19T08:00:00",
    call_quality="4_terrible",
    limit=20, offset=0,
)

# 2. For each, drill down for the per-window timeline.
for p in bad["objects"]:
    detail = get_history_participant(participant_id=p["id"])
    # detail["bucketed_call_quality"] = [unknown, good, ok, bad, terrible] counts
    # detail["historic_call_quality"] = per-20s-window timeline
```

Quality classification (Pexip's rule):
- `< 1%` packet loss in a 20-second window → Good (`1_good`)
- `< 3%` → OK (`2_ok`)
- `< 10%` → Bad (`3_bad`)
- otherwise → Terrible (`4_terrible`)
- `0` = Unknown (no data, e.g. very short calls)

Cap the per-record fan-out at ~20 to stay within the platform's 1,000-req/60s rate limit.

## Recipe: failed-call audit

```
list_history_participants(
    start_time="2026-05-19T00:00:00",
    end_time="2026-05-20T00:00:00",
    disconnect_reason="Call failed",
    fetch_all=True,
)
```

Common `disconnect_reason` strings are in `disconnect-reasons.json` (sibling). The exact set differs slightly between Pexip versions — call `get_resource_schema("participant")` against the **history** namespace if you need to be sure.

## Recipe: per-VMR breakdown

"Which VMRs got the most use last week?"

```
summarize_calls(
    start_time="2026-05-12T00:00:00",
    end_time="2026-05-19T00:00:00",
    group_by="conference_name",
)
```

`groups` will have one entry per VMR name (`{conference_name: {count, duration_seconds}}`), sorted by count.

## Caveats

- **The 10,000-instance retention limit is global, not per-day.** A busy platform loses history faster — if `truncated: true` shows up on a multi-day query, either narrow the window or export externally on a schedule.
- **`call_quality` strings have a numeric prefix on purpose**: they sort lexicographically the right way (`1_good` < `2_ok` < `3_bad` < `4_terrible`). Don't strip the prefix.
- **`conference` in history responses is a NAME string, not a URI.** Don't confuse it with `conference` in configuration responses (which is a FK URI).
- **For exports / billing,** prefer pulling history on a schedule into your own warehouse rather than relying on Pexip's retention. Pexip event sinks (push-based, configured directly in Pexip — see the `pexip-event-sinks` skill) are a complement.

## Authoritative docs

- History API: https://docs.pexip.com/api_manage/api_history.htm
- Historical conferences in the admin UI: https://docs.pexip.com/admin/conference_history.htm
