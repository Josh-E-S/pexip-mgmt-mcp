# VMR and directory administration

For long-lived platform configuration: VMRs (Virtual Meeting Rooms), the aliases that point at them, end users in the directory, LDAP sync, IVR themes, and the global platform settings. Hits the Configuration API. For live calls see `live-meeting-ops.md`; for dial-plan rules see `dial-plan.md`.

## Resource map

| MCP tool prefix | Pexip resource | What it is |
|---|---|---|
| `*_vmr` | `conference` (with `service_type=conference`) | A persistent meeting room. |
| `*_alias` | `conference_alias` | One dial string pointing at a VMR (E.164, SIP URI, arbitrary). One VMR ↔ many aliases. |
| `*_end_user` | `end_user` | A directory entry. Often LDAP-synced. Handle: `primary_email_address`. |
| `*_automatic_participant` | `automatic_participant` | A participant Pexip auto-dials when a given VMR starts (recorder, streamer, …). |
| `*_ldap_source` | `ldap_sync_source` | LDAP / AD server config for end-user sync. |
| `get/list_ivr_theme` | `ivr_theme` | Branding bundle (read-only — themes are uploaded via the admin UI). |
| `*_global_settings` | `global` (singleton, id=1) | Platform-wide settings. |
| `get_resource_schema` | any | Live schema for any resource — use before guessing fields. |

## Name-or-id everywhere

The CRUD tools accept friendly identifiers — exact name for most resources, `primary_email_address` for end users — and resolve to integer ids internally. Ambiguous matches raise a 409 so the agent can disambiguate before acting. Pass either:

- An integer id (`vmr=42`), or
- A numeric string (`vmr="42"`), or
- The exact name (`vmr="AllHands"`) / email (`user="alice@example.com"`).

## Recipe: create a VMR with aliases

```
create_vmr(
    name="AllHands",
    aliases=["allhands@example.com", "+15551234567"],
    pin="1234",                  # optional, host PIN
    guest_pin="5678",            # optional
    allow_guests=True,
    description="Company all-hands",
    tag="exec",
    host_view="four_mains_zero_pips",
    guest_view="one_main_seven_pips",
)
```

Returns the created VMR with its integer id. Names must be unique; conflicts come back as 400 with the field-level message.

## Recipe: add an alias to an existing VMR

```
add_vmr_alias(
    vmr="AllHands",                # or vmr=42
    alias="meet.allhands@example.com",
    description="Marketing's preferred URL",
)
```

VMR-side `aliases` (the inline list on the VMR object) and `conference_alias` (a sibling resource) are two ways to attach an alias. **Pick one approach per VMR and stick with it.** `add_vmr_alias` always uses the sibling-resource approach.

## Recipe: rename / update a VMR

```
update_vmr(
    vmr="AllHands",
    name="AllHands-2026",          # rename — keep aliases pointed by id, not by old name
    pin="9999",
    description="Updated for 2026",
)
```

Only the fields you pass are patched. Aliases are managed separately (use `add_vmr_alias` / `delete_alias`), **not** by passing an `aliases=` list to update — PATCH on list fields **replaces**, it does not append.

## Recipe: delete a VMR

```
delete_vmr(vmr="AllHands")
```

Irreversible. Conferences in progress on this VMR keep running (a running conference is a Status object; deletion only removes the persistent config). Always confirm with the user first.

## Recipe: end-user CRUD

```
list_end_users(email_contains="example.com", name_contains="Alice")
get_end_user(user="alice@example.com")
create_end_user(
    primary_email_address="bob@example.com",
    first_name="Bob", last_name="Jones",
    display_name="Bob Jones",
    telephone_number="+15550100",
    department="Engineering",
)
update_end_user(user="bob@example.com", title="Staff Engineer")
delete_end_user(user="bob@example.com")
```

If the directory is LDAP-synced, manual creates/edits drift from LDAP on the next sync. Prefer fixing the LDAP source.

## Recipe: automatic participants

For "auto-dial a recorder whenever this VMR starts":

```
add_automatic_participant(
    vmr="AllHands",
    alias="sip:recorder@recording.example.com",
    protocol="sip",
    call_type="audio-video",
    role="guest",
    streaming=False,
    keep_conference_alive="if_multiple_other",
    remote_display_name="Recorder",
)
```

`keep_conference_alive` values:
- `always` — the conference doesn't end while this leg is connected.
- `if_multiple_other` — keeps alive only if ≥1 other participant remains.
- `if_one_other_no_chair` — keeps alive only if exactly one other non-chair remains.
- `never` — auto-leg never holds the meeting open.

## Recipe: LDAP sync source

```
create_ldap_source(
    name="corp-ad",
    ldap_server="ldap.corp.example.com",
    ldap_base_dn="DC=corp,DC=example,DC=com",
    bind_username="CN=svc-pexip,CN=Users,DC=corp,DC=example,DC=com",
    bind_password="...",
    ldap_user_filter="(objectClass=user)",
    sync_interval_minutes=60,
)
```

`get_ldap_source(source="corp-ad")` returns the last sync status / errors — useful for answering "is LDAP working?" without leaving the conversation.

## Recipe: global platform settings

Singleton at `/configuration/v1/global/1/`. Discover fields first:

```
get_resource_schema("global")        # → field types, enums, help text
get_global_settings()                # → current values
update_global_settings(updates={
    "management_session_timeout_secs": 1800,
    "guests_only_timeout": 300,
})
```

These settings affect the whole platform. **Always confirm with the user before changing them.** Bad values can lock admins out (e.g. session timeout) or change behavior for every meeting.

## Field gotchas (apply to all configuration resources)

- **Foreign keys are URIs, not IDs.** When the API expects a `system_location` reference, send `"/api/admin/configuration/v1/system_location/3/"`, not `3`. The MCP tools handle this for you — pass the name or id, the tool resolves to a URI.
- **PATCH on list fields replaces, not appends.** To add to a list, GET the current value, append in code, PATCH the whole list back.
- **Schema enums are case-sensitive.** Send `"conference"`, not `"Conference"`.
- **Write-only fields** (`pin`, `password`, `bind_password`) are returned as `null` or omitted on GET. Don't treat absence as "unset" — call the schema or check the resource's behaviour.

## Authoritative docs

- Configuration API: https://docs.pexip.com/api_manage/api_configuration.htm
- VMRs: https://docs.pexip.com/admin/vmrs.htm
- Event sinks: https://docs.pexip.com/admin/event_sink.htm
- LDAP sync: https://docs.pexip.com/admin/ldap_sync.htm
