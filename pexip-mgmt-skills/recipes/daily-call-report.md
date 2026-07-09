# Recipe: daily call report

End-to-end workflow for generating a single day's usage report from Pexip CDRs and formatting it as Markdown ready to paste, email, or post.

**Skills used:** `pexip-operations` (reporting.md), bundled `pexip_report.py` helper.

## Inputs

- `date` — the calendar day in the user's local timezone (e.g. `2026-05-19`).
- `tz` — the user's timezone (default: UTC).
- `group_by` — one of `call_direction` / `call_quality` / `protocol` / `service_tag` / `system_location` / `conference_name` / `disconnect_reason` / `vendor`. Default `call_direction`.

## Steps

### 1. Convert the date to UTC ISO 8601 boundaries

```
start_utc = <local midnight on `date` in `tz`, converted to UTC>
end_utc   = <local midnight on (`date` + 1 day) in `tz`, converted to UTC>
```

Use whatever timezone library is at hand. The result should look like:

```
start_utc = "2026-05-19T07:00:00"   # for PDT (UTC-7)
end_utc   = "2026-05-20T07:00:00"
```

### 2. Pull the aggregation

```
result = summarize_calls(
    start_time = start_utc,
    end_time   = end_utc,
    group_by   = group_by,
)
```

`result` is the JSON object documented in `pexip-operations/reporting.md`. If `result["truncated"] == true`, mention to the user that the retention cap was hit and the report may be incomplete.

### 3. Format as Markdown

The skill bundles a formatter:

```bash
echo '<result json>' | python ./skills/operations/pexip-operations/pexip_report.py
```

Or do it inline if you'd rather not shell out. The expected shape:

```markdown
# Pexip call report — grouped by `call_direction`

- **Window:** `2026-05-19T07:00:00` → `2026-05-20T07:00:00` (UTC)
- **Total calls:** 412
- **Total duration:** 48h 17m 0s
- **Average call:** 7m 1s

| call_direction | Count | Share | Duration |
|---|---:|---:|---:|
| `in` | 290 | 70.4% | 34h 40m 0s |
| `out` | 122 | 29.6% | 13h 37m 0s |
```

### 4. Present to the user

- Show them the rendered Markdown.
- If a `truncated` flag came back, lead with that warning.
- Offer to re-run with a different `group_by` (the call is cheap; aggregates are server-side).

## Variations

### Recurring (e.g. emailed daily)

The MCP server is not a scheduler. To run this daily:

- Use a cron / systemd timer / GitHub Actions schedule on the user's side.
- Pipe the formatted Markdown into a mail tool (Gmail MCP, Postmark, Mailgun, etc.).
- For a multi-grouping report (direction AND quality AND per-VMR), call `summarize_calls` three times and concatenate the rendered output.

### Weekly / monthly

Same recipe, wider window. Watch for the **10,000-instance retention cap** — `truncated: true` happens fast on busy platforms over multi-day ranges. If you hit it, suggest one of:

- Run per-day and aggregate client-side
- Set up `pexip-event-sinks` for forward-looking real-time CDR collection
- Pull on a tighter schedule and store externally

## Safety

Read-only. The recipe never calls a destructive tool. No user confirmation needed before running.

## Reference source

- Skill: `pexip-operations/reporting.md`
- MCP tool: `summarize_calls` in `src/pexip_mcp/tools/history.py`
- Pexip docs: https://docs.pexip.com/api_manage/api_history.htm
