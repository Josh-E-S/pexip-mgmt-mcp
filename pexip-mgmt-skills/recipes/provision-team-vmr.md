# Recipe: provision a team VMR with aliases and a recorder

End-to-end workflow for "stand up a new VMR for the engineering team — give it three aliases and have a recorder dial in automatically when meetings start".

**Skills used:** `pexip-operations` (vmr-administration.md).

## Inputs

- `name` — admin-facing VMR name (e.g. `eng-team`). Must be unique.
- `aliases` — list of dial strings (e.g. `["eng@example.com", "+15551234567"]`).
- `host_pin` (optional) — host PIN.
- `tag` (optional) — for grouping in reports later (e.g. `team-eng`).
- `recorder_sip` (optional) — SIP URI for a recorder/streamer to auto-dial when meetings start.

## Steps

### 1. Pre-flight: check for name collision

```
existing = list_vmrs(name=<name>)
if existing["meta"]["total_count"] > 0:
    return "A VMR named <name> already exists. Pick a different name, or add aliases to the existing one with add_vmr_alias."
```

### 2. Pre-flight: check each alias for collision

Aliases are globally unique across the platform:

```
for alias in aliases:
    existing = list_aliases(alias=alias)
    if existing["meta"]["total_count"] > 0:
        return f"Alias {alias} is already in use. Pick a different one."
```

### 3. **Confirmation**

```
About to create a new VMR:
  Name:    <name>
  Aliases: <comma-separated list>
  PIN:     <set / not set>
  Tag:     <tag or "none">
  Auto-recorder: <recorder_sip or "none">

Proceed?
```

Wait for explicit "yes" before any write.

### 4. Create the VMR with inline aliases

```
vmr = create_vmr(
    name        = name,
    aliases     = aliases,
    pin         = host_pin,            # omit if None
    allow_guests = True,
    description = f"Team VMR for {name}",
    tag         = tag,
)
```

`create_vmr` accepts inline aliases — no need to call `add_vmr_alias` for the initial set. The returned object includes the new VMR's integer id.

If the create returns a 400 with field-level errors (e.g. PIN policy violation), **stop and surface the exact server error to the user**. Don't retry blindly.

### 5. Attach an automatic participant (if `recorder_sip` provided)

```
if recorder_sip:
    add_automatic_participant(
        vmr                   = name,           # or vmr["id"]
        alias                 = recorder_sip,
        protocol              = "sip",
        call_type             = "audio-video",
        role                  = "guest",
        streaming             = False,
        keep_conference_alive = "if_multiple_other",
        remote_display_name   = "Recorder",
    )
```

`keep_conference_alive="if_multiple_other"` means the auto-participant doesn't hold the meeting open by itself — once all the humans hang up, the meeting ends even if the recorder is still connected. Other options: `always`, `if_one_other_no_chair`, `never`.

### 6. Verify

```
created = get_vmr(vmr=name)
attached_aliases = list_aliases(vmr=name)
auto_participants = list_automatic_participants(vmr=name) if recorder_sip else None
```

### 7. Report back

```markdown
Created VMR **<name>** (id `<vmr_id>`):

- **Aliases:**
  - `<alias 1>`
  - `<alias 2>`
- **Host PIN:** <set / not set>
- **Tag:** <tag or none>
- **Auto-recorder:** <recorder_sip or none>

Test dial: any of the aliases above should reach the new room.
```

## Variations

### Bulk: 50 new VMRs from a CSV

Loop the recipe. Watch the platform's **1,000 req/60s rate limit** — each VMR is at minimum 1 create + N aliases + 1 auto-participant + 1 verify GET. At ~50 VMRs you'll touch 200+ requests; pace at ≤15 in-flight to stay clear of 429s.

### Add to an existing VMR instead

Skip steps 1, 4, 5. Use:

```
for alias in new_aliases:
    add_vmr_alias(vmr=<name>, alias=alias)
```

`add_vmr_alias` creates `conference_alias` records (the sibling resource). The inline `aliases=` field on `create_vmr` does the same thing under the hood; pick one approach per VMR and stick with it.

### Theme + layout customization

After step 4, patch:

```
update_vmr(
    vmr        = name,
    host_view  = "four_mains_zero_pips",   # see assets/layouts.json in pexip-operations
    guest_view = "one_main_seven_pips",
)
```

For IVR theme assignment, you'll need the theme's URI — call `list_ivr_themes` first.

## Safety

This recipe creates new resources. It is **not** destructive (no deletes/updates of existing data) but it adds load — bulk runs need the rate-limit care noted above. Step 3's confirmation gate is mandatory; skip only when the user's request explicitly enumerated the inputs.

## Reference source

- Skill: `pexip-operations/vmr-administration.md`
- MCP tools:
  - `list_vmrs`, `create_vmr`, `get_vmr`, `update_vmr` in `src/pexip_mcp/tools/conference.py`
  - `list_aliases`, `add_vmr_alias` in `src/pexip_mcp/tools/alias.py`
  - `list_automatic_participants`, `add_automatic_participant` in `src/pexip_mcp/tools/automatic_participant.py`
- Pexip docs:
  - VMRs: https://docs.pexip.com/admin/vmrs.htm
  - Configuration API: https://docs.pexip.com/api_manage/api_configuration.htm
