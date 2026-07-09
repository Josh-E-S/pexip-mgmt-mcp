---
name: pexip-mjx
description: Use when configuring or extending Pexip's MJX (Microsoft Join eXchange, aka One-Touch Join) integration — the feature that lets in-room video systems show a single "Join" button on their console for scheduled meetings by pulling calendar data from Exchange / Office 365 / Google Workspace and overlaying it onto the room-system UI. Triggers on `mjx_endpoint`, `mjx_integration`, `mjx_meeting_processing_rule`, `one-touch join`, "OTJ", "in-room join", "Cisco / Poly / Logitech room system", "Exchange room mailbox", "calendar-driven join", `/api/admin/configuration/v1/mjx_endpoint/`. Do NOT use for general client-side join flows (that's the client-side / Pexip client SDK domain) or for managing the VMRs MJX joins (use `pexip-operations/vmr-administration.md`).
license: MIT
---

# Pexip MJX — One-Touch Join for room systems

**MJX (Microsoft Join eXchange)** is Pexip's room-system integration. It connects to your calendar system (Exchange Online / on-prem, or Google Workspace), reads the upcoming meetings on each room mailbox, detects video-meeting URLs/aliases inside the invite body (Pexip, Teams, Zoom, Webex, Google Meet), and pushes a normalized "Join" button to the in-room codec's UI so users tap one button instead of typing a long URI.

Three Pexip resources govern it:

- `mjx_endpoint` — a room video system (Cisco CE, Poly OBTP, Logitech Tap, etc.) Pexip pushes the Join button to
- `mjx_integration` — the calendar source (Exchange / Google) Pexip reads from
- `mjx_meeting_processing_rule` — regex/transform rules that detect each meeting platform in the invite body and produce the dial string

The `pexip-mgmt-mcp` server exposes 4 dedicated MJX **status** tools — `get_mjx_endpoint_status`, `list_mjx_endpoint_status`, `get_mjx_meeting_status`, `list_mjx_meeting_status` (in `src/pexip_mcp/tools/status.py`). The MJX **configuration** resources (`mjx_endpoint`, `mjx_integration`, `mjx_meeting_processing_rule`, …) are managed through the generic `*_resource` CRUD tools (`create_resource`, `get_resource`, `update_resource`, `delete_resource`, `list_resources`).

## When to use

- "Set up One-Touch Join for our conference rooms"
- "Why isn't the Join button showing up on the Webex panels?"
- "Add a rule to detect Zoom meetings in the calendar invite"
- "Migrate room systems from vendor's OTJ to Pexip MJX"
- Adding `mjx_*` resource tools to the MCP server

## When NOT to use

- Client-side / WebRTC join flows → out of scope for this server-side package
- VMR creation / management → `pexip-operations/vmr-administration.md`
- General gateway dial-plan rules (for non-room calls) → `pexip-operations/dial-plan.md`

## Architecture in one diagram

```
                       Exchange/O365/Google Workspace
                                  │  calendar read
                                  ▼
                    ┌─────────────────────────┐
                    │   mjx_integration       │
                    │   (calendar source)     │
                    └────────────┬────────────┘
                                 │
                  detect meeting │ apply rules
                                 ▼
                    ┌─────────────────────────┐
                    │ mjx_meeting_processing  │
                    │ _rule (regex/transform) │
                    └────────────┬────────────┘
                                 │ produces join URI
                                 ▼
                    ┌─────────────────────────┐
                    │   mjx_endpoint          │
                    │   (Cisco / Poly / …)    │
                    │   gets "Join" button    │
                    └─────────────────────────┘
```

## MCP tools

Each resource has list / get / create / update / delete. Create and update take a `settings` dict for version-flexible fields — call `get_resource_schema('mjx_integration')` to discover exact field names on your platform.

```
# Calendar integrations
list_mjx_integrations(name_contains=…, limit=20, offset=0)
get_mjx_integration(integration=<id or name>)
create_mjx_integration(name=…, settings={calendar_type: …, …})
update_mjx_integration(integration=<id or name>, settings={…})
delete_mjx_integration(integration=<id or name>)

# Room endpoints
list_mjx_endpoints(name_contains=…, integration=…, limit=20, offset=0)
get_mjx_endpoint(endpoint=<id or name>)
create_mjx_endpoint(name=…, settings={room_email: …, endpoint_type: …, …})
update_mjx_endpoint(endpoint=<id or name>, settings={…})
delete_mjx_endpoint(endpoint=<id or name>)

# Processing rules
list_mjx_meeting_processing_rules(name_contains=…, limit=20, offset=0)
get_mjx_meeting_processing_rule(rule=<id or name>)
create_mjx_meeting_processing_rule(name=…, settings={match_string: …, protocol: …, …})
update_mjx_meeting_processing_rule(rule=<id or name>, settings={…})
delete_mjx_meeting_processing_rule(rule=<id or name>)
```

## Common processing rules

The detect-meeting-URL-in-invite-body step is where most of the value lives. Useful patterns:

| Meeting platform | Match string (regex) | Dial string template |
|---|---|---|
| Pexip Infinity | `meet\.example\.com/([a-z0-9._-]+)` | `\1@meet.example.com` |
| MS Teams (via CVI) | `teams\.microsoft\.com/l/meetup-join/[^\s]+` | `<tenantid>.<meeting>@<cvi-tenant>` |
| Zoom (via Zoom CVI) | `zoom\.us/j/([0-9]+)` | `\1.<zoom-cvi-suffix>` |
| Google Meet | `meet\.google\.com/([a-z-]+)` | `\1@<google-meet-cvi-suffix>` |
| Webex (via CVI) | `\b([a-z0-9]+)@webex\.com\b` | `\1@<webex-cvi-suffix>` |

CVI = Cloud Video Interop. Each platform has its own CVI dial-string convention — check the platform docs (Teams CVI, Zoom CVI, Webex CMR).

## Field gotchas

- **Room mailbox vs user mailbox.** MJX reads from **resource** (room) mailboxes, not user mailboxes. Common config mistake.
- **Service account permissions.** The Exchange/Google service account needs `Calendars.Read` on the room mailboxes — failure here is silent until you try a real meeting.
- **Endpoint capacity.** Cisco CE, Poly OBTP, Logitech Tap all have slightly different "Join" button limits per day; processing rules that fire on every invite line can exhaust them.
- **Polling vs push.** Exchange supports push subscriptions; Google Workspace polls. Latency for "calendar change reflected in room" can differ.

## Reference source

- **Authoritative Pexip docs:**
  - MJX overview: https://docs.pexip.com/admin/mjx_intro.htm
  - MJX configuration: https://docs.pexip.com/admin/configuring_mjx.htm
  - API reference: https://docs.pexip.com/api_manage/api_configuration.htm (search `mjx_endpoint`, `mjx_integration`, `mjx_meeting_processing_rule`)
- **MCP server source:** MJX status tools in `src/pexip_mcp/tools/status.py`; MJX config resources via the generic CRUD in `src/pexip_mcp/tools/resource_crud.py`
- **Related skills:** `pexip-config-api` (resource model), `pexip-operations/dial-plan.md` (the static-rule sibling), `pexip-external-policy` (more dynamic alternative)
