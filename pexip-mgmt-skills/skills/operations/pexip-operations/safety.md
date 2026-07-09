# Safety — confirmation and resolution rules for destructive operations

Pexip operations have real-world side effects. A disconnected participant is booted off a real call. A locked conference can leave latecomers stranded. A deleted VMR breaks every dial string that pointed at it. This page is the rulebook for which operations need explicit user confirmation and how to resolve fuzzy human input safely.

## Categorize before you act

| Risk | Examples | Confirmation rule |
|---|---|---|
| **Read-only** | `list_*`, `get_*`, `summarize_calls`, `get_resource_schema` | No confirmation needed. Run freely. |
| **Idempotent + reversible** | `mute_participant`, `lock_conference`, `spotlight_participant`, `set_participant_role`, `add_vmr_alias`, `create_*` | Confirm if the user's request was ambiguous about the target. Skip if the target was named explicitly. |
| **Idempotent + DESTRUCTIVE** | `disconnect_participant`, `disconnect_conference`, `delete_*`, `update_global_settings` | Always state what you're about to do and the target, and proceed only if the request was unambiguous OR the user has confirmed in this turn. |
| **Not idempotent** | `dial_participant`, `transfer_participant`, `create_*` (when a duplicate would matter) | Confirm before retrying after any error — repeats place real calls / create real duplicates. |

## The resolution rule

When the user names a target by something fuzzy ("Alice", "the standup", "that bad meeting yesterday"):

1. Do the Status / History lookup.
2. **Stop if zero or multiple matches.** Tell the user what you found and ask which.
3. Proceed only when there's exactly one match. **Surface the resolved identity** ("I see one participant named Alice Smith in the AllHands meeting — disconnecting now…") before acting on it.

Never silently pick "the first match" when there are several. The cost of being wrong on Pexip operations is high.

## The confirmation rule

Before any operation in the **DESTRUCTIVE** row above:

```
I'm about to <verb> <target>:
- <key identifying fields>
This will <real-world consequence>.

Proceed?
```

Exceptions where you can skip the prompt and act immediately:

- The user named the target by exact id or unique name AND used an unambiguous verb. "Kick participant 8c3f-…" or "disconnect Alice from the AllHands meeting" with one Alice in that meeting → act.
- The same destructive verb has already been confirmed in this conversation turn and the user said "yes do it for all of them" / "go ahead".

## Live-meeting safety specifics

- **`disconnect_conference` ends an entire meeting.** Treat as if you were about to hang up on the room. Always confirm.
- **`lock_conference` strands latecomers.** Reversible (unlock), but disruptive — confirm if the meeting is currently in progress and you're acting on a fuzzy match.
- **`transfer_participant` is one-way and not idempotent.** Once a participant is transferred, you can't replay the call. If the source meeting still has the participant id after a `404`, something else went wrong — don't retry blindly.
- **`dial_participant` places a new outbound call per invocation.** Don't retry on timeout without checking whether the first attempt succeeded — you can end up with two simultaneous outbound legs.

## Configuration safety specifics

- **`delete_vmr` does not affect in-progress conferences on that VMR** — running calls are Status-API objects, not Configuration-API objects. But it does break every dial string that pointed at the deleted VMR.
- **`update_global_settings` affects the whole platform.** Bad values can lock out admins (session timeout), change default behavior for every meeting, or break LDAP / IVR. Read `get_resource_schema("global")` first to see valid types and ranges. Show the user the diff before applying.
- **`delete_alias` is fast and irreversible.** Aliases re-created with the same string aren't the "same" alias — the integer id changes, which can matter for audit logs.
- **`delete_gateway_rule` can leave a class of calls unrouted.** Prefer `update_gateway_rule(rule=…, enable=False)` for a removal you might want to reverse.

## Reporting safety

History queries are read-only and safe to run. The only "cost" is rate-limit budget — Pexip's 1,000 req/60s limit is shared across all admin APIs, so don't fan out detail GETs over more than ~20-50 records without reason.

## When the MCP server isn't there

If a tool call fails because the MCP server isn't connected (no `pexip-mgmt` server in the host's MCP config), surface that clearly — "the pexip-mgmt MCP server isn't available in this session" — and don't try to substitute by suggesting shell commands or HTTP requests against the Pexip API. The user installed the MCP server for a reason; failure should send them back to fix the wiring.
