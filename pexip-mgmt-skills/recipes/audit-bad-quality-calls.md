# Recipe: audit bad-quality calls in a time window

End-to-end workflow for "show me the bad calls last night and tell me why". Combines a History API list query with per-record drill-downs for the deep quality fields.

**Skills used:** `pexip-operations` (reporting.md).

## Inputs

- `start_time` / `end_time` — UTC ISO 8601 window.
- `top_n` (optional) — how many worst calls to drill into. Default 20. Don't go above 50 without a reason; per-record drill-downs cost rate-limit budget (Pexip is 1,000 req/60s shared across all admin APIs).
- `quality_threshold` — `3_bad` or `4_terrible`. Default `4_terrible`.

## Steps

### 1. Get the count

```
summary = summarize_calls(
    start_time = start_time,
    end_time   = end_time,
    group_by   = "call_quality",
)
```

Lead with the counts: "X terrible, Y bad, Z ok, W good calls in this window." If terrible/bad counts are zero, stop here — there's nothing to audit.

### 2. List the worst records

```
bad = list_history_participants(
    start_time     = start_time,
    end_time       = end_time,
    call_quality   = quality_threshold,
    limit          = top_n,
    offset         = 0,
)
```

Don't `fetch_all=True` — that pulls every matching record, but we only want the top N for drill-down. Sort is `-start_time` by default (most recent first), which is usually what the user wants.

### 3. Drill into each for the deep quality fields

```
details = []
for p in bad["objects"]:
    d = get_history_participant(participant_id=p["id"])
    details.append({
        "display_name":    d["display_name"],
        "conference":      d["conference"],
        "protocol":        d["protocol"],
        "duration":        d["duration"],
        "disconnect":      d["disconnect_reason"],
        "media_node":      d.get("media_node"),
        "system_location": d.get("system_location"),
        "buckets":         d["bucketed_call_quality"],   # [unknown, good, ok, bad, terrible]
        "rx_packet_loss":  max((s.get("rx_packet_loss") or 0)
                               for s in d.get("media_streams", [])),
        "tx_packet_loss":  max((s.get("tx_packet_loss") or 0)
                               for s in d.get("media_streams", [])),
    })
```

`bucketed_call_quality` is `[unknown, good, ok, bad, terrible]` counts of 20-second windows. Example `[0, 7, 3, 1, 9]` = "started OK then went off a cliff".

### 4. Look for patterns

Before rendering, scan for clustering:

- **Same `system_location`?** Likely a regional / datacenter network issue.
- **Same `media_node`?** Likely a single node having capacity or NIC problems — cross-reference with `list_node_status` for that node.
- **Same `protocol`?** Often a NAT / firewall issue specific to that signaling path (e.g. all WebRTC failing → ICE/STUN problem).
- **Same `disconnect_reason`?** Tells you whether it was call setup (`Call failed`, `Authentication failed`) or in-call (`Connection timed out`, `ICE failure`).

Surface the pattern in plain English at the top of the report.

### 5. Render the report

```markdown
# Bad-quality call audit — <window>

**Summary:** N terrible + M bad calls (of <total> total).

**Pattern:** <one-sentence observation from step 4, if any>.

## Worst calls

| Participant | Conference | Protocol | Duration | Disconnect reason | Quality buckets | Max packet loss |
|---|---|---|---:|---|---|---:|
| Alice Smith | standup | webrtc | 12m 4s | Connection timed out | `[0,2,1,3,8]` | 14.2% |
| … |

## Recommendations

- <if location clustering> Investigate <location>'s upstream connectivity.
- <if node clustering> Inspect <node> with `get_node_status` for load / sync / errors.
- <if protocol clustering> Check NAT/firewall for <protocol> media path.
```

## Variations

### Wider window than retention can hold

Pexip retention is **10,000 conference instances**. On busy platforms, a "last 30 days" audit can hit that cap. The `summary` step in (1) sets `truncated: true` when it does. If you see truncation:

- Narrow the window to per-day, run the recipe daily, store results externally.
- Or set up `pexip-event-sinks` to push events forward.
- Or accept that the audit only covers what's still retained, and say so in the report.

### Live-call audit instead of historical

For "is THIS call OK right now":

```
participants = list_active_participants(conference_name=<name>)
for p in participants["objects"]:
    if p["call_quality"] in ("3_bad", "4_terrible"):
        live = get_participant_quality(participant_id=p["id"])
        # live["media_streams"] has per-stream rx/tx packet loss right now
```

## Safety

Read-only. The recipe never modifies anything. No confirmation needed before running.

## Reference source

- Skill: `pexip-operations/reporting.md`
- MCP tools:
  - `summarize_calls`, `list_history_participants`, `get_history_participant` in `src/pexip_mcp/tools/history.py`
  - `list_active_participants`, `get_participant_quality`, `list_node_status` in `src/pexip_mcp/tools/status.py`
- Pexip docs: https://docs.pexip.com/api_manage/api_history.htm
