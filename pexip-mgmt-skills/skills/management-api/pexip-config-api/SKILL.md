---
name: pexip-config-api
description: Use when adding, modifying, or debugging MCP tools that wrap the Pexip Infinity Management Configuration API — CRUD on VMRs/conferences, conference_alias, end_user, system_location, worker_vm (conferencing nodes), gateway_routing_rule, automatic_participant, ldap_sync_source, ivr_theme, global settings, license, devices. Triggers on `/api/admin/configuration/v1/`, `conference`, `conference_alias`, `end_user`, `system_location`, `worker_vm`, `gateway_routing_rule`, `automatic_participant`, `ldap_sync_source`, `ivr_theme`, `tools/conference.py`, `tools/alias.py`, `tools/end_user.py`, `tools/gateway_rule.py`, `tools/infrastructure.py`. Do NOT use for live in-progress meetings (use `pexip-command-api` + `pexip-status-api`) or post-call CDRs (use `pexip-history-api`).
license: MIT
---

# Pexip Infinity Management — Configuration API

REST API for creating, reading, updating, and deleting platform configuration on a Pexip Infinity Management Node. This is the primary API surface for this MCP server.

## Base URL & versioning

```
https://<management-node-host>/api/admin/configuration/v1/<resource>/
```

- All requests must be HTTPS.
- Trailing slash on collection and item URIs is required.
- Append `?format=json` when in doubt; JSON is the canonical format.
- Schemas are introspectable: GET `…/<resource>/schema/?format=json` returns field types, `nullable` (true = optional, false = required), `help_text`, and allowed values for enum fields. **Always introspect the schema before hand-coding fields** — fields drift between Pexip versions.

## Authentication

- HTTP Basic over HTTPS (default). Username defaults to `admin` (the web admin account).
- OAuth or LDAP-backed auth may also be configured on the Management Node — fall back to Basic if OAuth is not configured.
- Treat credentials as secrets: read from env vars (`PEXIP_HOST`, `PEXIP_USERNAME`, `PEXIP_PASSWORD`), never hardcode. Never log credentials or `Authorization` headers.
- TLS verification: default to verifying. Expose an env var (e.g. `PEXIP_VERIFY_TLS=false`) for self-signed lab nodes, but warn loudly when disabled.

## HTTP semantics

| Verb | URI | Meaning |
| --- | --- | --- |
| GET | `…/<resource>/` | List (paginated) |
| GET | `…/<resource>/<id>/` | Retrieve one |
| POST | `…/<resource>/` | Create |
| PATCH | `…/<resource>/<id>/` | Partial update (preferred) |
| PUT | `…/<resource>/<id>/` | Full replace (rarely needed) |
| DELETE | `…/<resource>/<id>/` | Delete |

- Successful POST returns `201 Created` with a `Location` header pointing at the new object's URI.
- Successful PATCH/PUT returns `202 Accepted` (often with empty body) or `204 No Content`.
- Validation errors return `400` with a JSON body like `{"field_name": ["error message"]}` — surface these verbatim through MCP tool errors, do not flatten.
- `401` = bad credentials, `403` = authenticated but not allowed, `404` = wrong URI or wrong ID.

## Listing, filtering, pagination

- List responses are wrapped: `{"meta": {"limit": 20, "offset": 0, "total_count": N, "next": "...", "previous": null}, "objects": [...]}`.
- Default `limit` is 20. Maximum `limit` is **10,000** per request. Pass `?limit=N&offset=M` to page; follow `meta.next` (a relative URL or null) to walk pagination.
- Filtering uses Tastypie-style query params: `?name=Foo`, `?name__startswith=Foo`, `?service_type__in=conference,lecture`. The schema's `filtering` block lists which fields support which lookups.
- Ordering: `?order_by=name` or `?order_by=-created_time`.

## Rate limit

**1,000 requests per 60 seconds per Management Node.** Watch for `429 Too Many Requests`. MCP tools that fan out (e.g. "list all VMRs and their aliases") should:
- Prefer a single filtered list call over per-item GETs.
- Implement client-side backoff: on `429`, sleep `Retry-After` seconds (or 1s default) and retry.
- Batch with concurrency cap (e.g. 10 in-flight) for bulk operations.

## Core resources (initial MCP tool surface)

### Conferences (VMRs / Virtual Auditoriums / Gateway Services)
`/api/admin/configuration/v1/conference/`

The single most important resource. A "conference" object represents a VMR, a Virtual Auditorium, a Test Call Service, a Media Playback Service, or a Gateway Service — the kind is set by `service_type`.

Key fields (introspect the schema for the full list — this is a partial reference):
- `name` (required, unique) — admin-facing label.
- `service_type` (required) — one of `conference` (VMR), `lecture` (Virtual Auditorium), `two_stage_dialing` / `gateway` (Gateway Service), `test_call`, `media_playback`.
- `aliases` — **nested list of `{alias: "..."}` objects**. Aliases created here are siblings of the standalone `conference_alias` resource; either approach works but pick one and stick with it per VMR.
- `pin`, `guest_pin`, `allow_guests` — security.
- `host_view`, `guest_view` — layout names (e.g. `one_main_zero_pips`, `two_mains_seven_pips`).
- `max_callrate_in`, `max_callrate_out`, `max_pixels_per_second`.
- `tag` — free-form grouping label.
- `enable_chat`, `enable_overlay_text`, `automatic_participants` (FK list).
- `description`, `ivr_theme` (FK).

### Conference aliases
`/api/admin/configuration/v1/conference_alias/`

- `alias` (required, unique) — the dial string (E.164, URI, or arbitrary).
- `conference` — URI of the parent conference (e.g. `/api/admin/configuration/v1/conference/123/`).
- `description`.

### End users
`/api/admin/configuration/v1/end_user/`

Directory entries (often LDAP-synced). Used for ownership of VMRs and address-book lookups.
Fields: `primary_email_address` (unique), `first_name`, `last_name`, `display_name`, `telephone_number`, `mobile_number`, `title`, `department`, `avatar_url`, `ms_exchange_guid`, `sync_tag`.

### System locations
`/api/admin/configuration/v1/system_location/`

Logical grouping of Conferencing Nodes (typically per datacenter / region). Drives media routing, transcoding, dial plan, BFCP/MSI settings.
Fields: `name` (required, unique), `description`, `mtu`, `local_mssip_domain`, `transcoding_location` (FK self), `media_priority`, `bdpm_pin_checks_enabled`, `client_stun_servers`, `client_turn_servers`, `dns_servers` (FK list), `ntp_servers` (FK list), `syslog_servers` (FK list), `snmp_network_management_system` (FK list).

### Conferencing nodes
`/api/admin/configuration/v1/worker_vm/`

Note the resource is named `worker_vm`, not `conferencing_node`. Represents a deployed Conferencing Node.
Fields: `name`, `hostname`, `domain`, `address` (IPv4), `netmask`, `gateway`, `ipv6_address`, `system_location` (FK), `password` (write-only), `deployment_type` (e.g. `MANUAL`, `AWS`, `AZURE`, `GCP`, `VMWARE`), `node_type` (`CONFERENCING` or `PROXYING`), `transcoding`, `enable_distributed_database`, `enable_sip`, `enable_h323`, `enable_webrtc`, `tls_certificate` (FK).

### Gateway routing rules
`/api/admin/configuration/v1/gateway_routing_rule/`

Outbound dial plan — match an alias and rewrite to a destination on a target call protocol.
Fields: `name`, `priority` (lower = evaluated first), `enable`, `match_string` (regex), `replace_string`, `called_device_type` (e.g. `mssip`, `lync`, `external`), `outgoing_protocol`, `outgoing_location` (FK), `call_type`, `crypto_mode`, `treat_as_trusted`, `max_pixels_per_second`.

### Automatic participants
`/api/admin/configuration/v1/automatic_participant/`

Participants automatically dialed when a conference starts (e.g. recorders, streamers).
Fields: `alias` (required), `conference` (FK), `description`, `protocol` (`sip`, `h323`, `mssip`, `rtmp`, `gms`, `teams`), `call_type` (`audio`, `video`, `video-only`), `dtmf_sequence`, `keep_conference_alive`, `routing` (`auto`, `manual`), `system_location` (FK), `streaming`, `remote_display_name`.

### Other commonly used configuration resources

- `ivr_theme/` — branding/theme bundles for VMRs.
- `mssip_proxy/`, `sip_proxy/`, `h323_gatekeeper/` — signaling targets.
- `mjx_endpoint/`, `mjx_integration/` — One-Touch Join.
- `ldap_sync_source/` — LDAP/AD sync configuration.
- `recurring_conference/` — scheduled conferences.
- `tls_certificate/`, `trusted_ca_certificate/`.
- `licence/` (note British spelling) — read-only in practice.
- `global/` — singleton; platform-wide settings (only `GET` and `PATCH` on `/global/1/`).

## Field gotchas

- **Foreign keys are URIs, not IDs.** Set `system_location` to `"/api/admin/configuration/v1/system_location/3/"`, not `3` or `"3"`.
- **PATCH semantics for list fields are replace, not append.** To add one alias to a VMR, GET the current `aliases` array, append, then PATCH the whole array back. Same for FK lists like `automatic_participants`.
- **Schema enums are case-sensitive.** Send `"conference"`, not `"Conference"`.
- **Some fields are write-only** (e.g. `password`, `pin`) — GETs return them as `null` or omit them. Don't treat absence as "field was unset".
- **Booleans in query filters** must be `True` / `False` (capitalized) in some Pexip versions. Test before relying on it.

## MCP tool design notes

- **One MCP tool per logical operation, not one per HTTP verb.** E.g. `pexip_create_vmr` (POST conference + nested aliases), `pexip_list_vmrs` (filtered GET), `pexip_get_vmr` (GET by id or by name lookup), `pexip_update_vmr` (PATCH), `pexip_delete_vmr` (DELETE).
- **Accept VMR identifiers by name OR id.** Internally resolve name → id with a filtered list call. Cache for the duration of a tool invocation only.
- **Validate inputs against the live schema** when possible (fetch schema once, cache for the process lifetime). Reject unknown fields client-side with a clear error rather than letting the server return an opaque 400.
- **Surface server validation errors verbatim.** Pexip returns useful per-field messages — do not flatten to "request failed".
- **Idempotency.** Pexip POST is not idempotent (creates duplicate-name conferences would 400 on uniqueness, but other resources allow duplicates). For "create or update" tools, look up by unique key first.
- **Never expose raw credentials** in tool inputs/outputs or error messages.

## Quick-reference URIs

```
List/create VMRs:        GET|POST  /api/admin/configuration/v1/conference/
Get/update/delete VMR:   GET|PATCH|DELETE  /api/admin/configuration/v1/conference/<id>/
Schema for VMR:          GET  /api/admin/configuration/v1/conference/schema/?format=json
List aliases for VMR:    GET  /api/admin/configuration/v1/conference_alias/?conference=/api/admin/configuration/v1/conference/<id>/
List end users:          GET  /api/admin/configuration/v1/end_user/
List locations:          GET  /api/admin/configuration/v1/system_location/
List conferencing nodes: GET  /api/admin/configuration/v1/worker_vm/
List gateway rules:      GET  /api/admin/configuration/v1/gateway_routing_rule/?order_by=priority
Global settings:         GET|PATCH  /api/admin/configuration/v1/global/1/
```

## Authoritative docs

- Overview: https://docs.pexip.com/api_manage/management_intro.htm
- Configuration API: https://docs.pexip.com/api_manage/api_configuration.htm
- Using the API (auth, pagination, rate limits): https://docs.pexip.com/api_manage/using.htm
- Versioned PDF references (v17, v15, etc.): https://docs.pexip.com/files/v17/Pexip_Infinity_Management_API_v17.a.pdf
