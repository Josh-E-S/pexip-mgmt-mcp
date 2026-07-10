---
name: pexip-mgmt-intake
description: Use at the START of any open-ended Pexip Infinity management or admin-API task to scope the work before answering. Triggers when the user says "I want to manage Pexip", "set up Pexip admin tooling", "use the Pexip management API", "automate Pexip", "report on Pexip calls", or any project-shaped Pexip-server-side request without specifics. Ask the questions in this skill BEFORE diving in. Do NOT use for narrow specific questions like "how does summarize_calls work" or "kick Alice from the standup" — only for project-shaped requests where the user hasn't yet decided what they're building.
license: MIT
---

# Pexip management intake

A management-side Pexip task can be many shapes: a one-off operator action ("kick this person"), a recurring report ("daily call volume"), a configuration push ("add 50 VMRs"), an integration extension ("build a webhook receiver"), or a developer task on the MCP server itself ("add a tool for X"). The right skill set, dependencies, and operational stance differ a lot.

**Don't guess.** Ask a small number of targeted questions, then route.

Keep it brief. Most management tasks resolve in 2-3 questions.

## When to use

- Any "I want to use Pexip's management API to…" type request
- Any "automate" / "report" / "monitor" Pexip request without scope
- The user mentioned Pexip and the MCP server but not what they're trying to do

## When NOT to use

- Narrow API questions: "what's the schema for `conference`?" → answer with `pexip-config-api`
- Live operator verbs: "kick Alice", "lock the AllHands" → answer with `pexip-operations`
- Specific tool questions: "how do I call `summarize_calls`?" → answer with `pexip-operations`
- MCP server code edits: "add a tool that wraps X" → answer with the matching `pexip-*-api` developer-reference skill

## The minimum questions

Ask one at a time, with options where possible. Stop as soon as you have enough to route.

### Q1. What are you trying to do? (always ask)

```
A) One-off operator action against a live or recent meeting
   (kick, lock, transfer, change layout, check who's in)
B) Recurring reporting or monitoring
   (daily / weekly call volume, quality forensics, alarm dashboard)
C) Bulk configuration change
   (create N VMRs, update dial-plan rules, manage end users)
D) Extend the MCP server itself
   (add a new tool, wrap a Pexip endpoint not currently covered)
E) Build a webhook receiver for Pexip events
   (event sinks pushing to a custom HTTP listener)
F) Integrate Pexip with a room system (MJX / One-Touch Join)
G) Other — please describe
```

Routing:

- **A** → `pexip-operations` (operator runbook, all live-meeting playbooks)
- **B** → `pexip-operations` → `reporting.md` (or `platform-health.md` for alarm-style monitoring)
- **C** → `pexip-operations` → `vmr-administration.md` and / or `dial-plan.md`
- **D** → the matching developer-reference skill:
  - Configuration CRUD → `pexip-config-api`
  - Live state reads → `pexip-status-api`
  - CDR / history reads → `pexip-history-api`
  - Live commands (kick/lock/transfer) → `pexip-command-api`
- **E** → `pexip-event-sinks`
- **F** → `pexip-mjx`
- **G** → ask follow-up

### Q2. Is the pexip-mgmt MCP server already connected? (always ask)

```
A) Yes — `pexip-mgmt` shows up in the host's MCP server list
B) No / not sure
```

If **B**:
- Point them at the install instructions in this package's `README.md`.
- Suggest they run the bundled `healthcheck.sh` (in the `pexip-operations` skill) or `uv run python -m pexip_mcp --healthcheck` against their Management Node.
- They can keep reading the skill content as docs even without the server — but tool calls won't have implementations.

### Q3. (Conditional) For routes A/B/C: confirm scope

Recurring reports? Ask:
```
- Time window the user cares about (today, this week, last 30 days, on a schedule?)
- Grouping (by direction? by quality? by VMR? by location?)
- Output format (Markdown? JSON? email?)
```

Bulk configuration? Ask:
```
- Are you adding, updating, or removing?
- Will you run this once, or repeatedly?
- Do you have the source data (CSV, spreadsheet, LDAP)?
```

Live operator action? Ask:
```
- Which conference / participant (be specific about name or alias)
- Is the action reversible (mute) or destructive (disconnect)?
```

For destructive actions specifically, also reference `pexip-operations/safety.md` before acting.

## Don't ask these (defaults are fine)

These have sensible defaults; don't make the user justify them:

- Output format → Markdown unless they ask otherwise
- Time format → UTC ISO 8601 on input, user's local TZ on display
- Pagination size → default 20, bump to `fetch_all=True` for reports
- Confirmation on destructive ops → on by default unless the user named the target unambiguously

## After the questions: the recommendation format

Respond with this shape:

```
Based on your answers, here's how I'd proceed:

  Skill(s) to load:
  - <skill name>          — for <one-line reason>
  - <skill name>          — for <one-line reason>

  First concrete step:
  <action, named tool call, or "I need X first">

  Open questions before I act:
  - <max 2-3 if anything's still unclear>
```

Then **wait for confirmation** before running any destructive tool. For read-only actions (list_*, get_*, summarize_calls) it's fine to proceed immediately.

## Example session

> User: "I want to start pulling daily call reports out of Pexip."

```
A few quick questions:

1. Which of these matches what you want?

   A) A one-shot report for a specific day, run on demand
   B) A scheduled daily report (emailed / posted somewhere)
   C) A live dashboard

   (For B/C we'll need somewhere to run a scheduler — out of scope
    for the MCP server, but the skill content tells you how.)
```

> User: "B — emailed to me each morning."

```
2. What should it group calls by? Common options:

   - call_direction (in vs out)
   - call_quality   (good / ok / bad / terrible)
   - protocol       (sip / h323 / mssip / webrtc / rtmp / teams)
   - service_tag    (your tags on VMRs)
   - conference_name (per-VMR breakdown)
   - system_location (per-datacenter breakdown)
   - disconnect_reason

   You can also combine — start with one.
```

> User: "Direction and quality."

```
Plan:

  Skill(s) to load:
  - pexip-operations → reporting.md      (CDR / summarize_calls patterns)

  First step:
  Test the report by calling summarize_calls(start_time, end_time,
  group_by='call_direction') for yesterday. I'll then run the same
  with group_by='call_quality' and show both.

  Open questions:
  - Email transport: Gmail MCP / Postmark / Mailgun / something else?
    (Out of scope for the pexip-mgmt server — you'll need a separate
     mail tool or a small cron job.)
```

## Reference source

- Authoritative Pexip docs: https://docs.pexip.com/api_manage/management_intro.htm
- Related skills: `pexip-operations`, `pexip-config-api`, `pexip-status-api`, `pexip-history-api`, `pexip-command-api`, `pexip-event-sinks`, `pexip-mjx`
