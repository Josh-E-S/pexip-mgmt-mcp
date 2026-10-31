# Tool module review — 31 Oct 2026

Scope: a line-by-line read of the tool modules not covered by the earlier
architecture/client/helpers/CRUD/conference review, checked against (a) the
Pexip Management API as far as it can be verified from docs.pexip.com search
snippets (the site is not fetchable from the review sandbox), (b) Anthropic's
tool-design guidance, and (c) internal consistency with `_helpers.py` and
`client.py`. Read-only review: nothing under `src/`, `tests/` or `evals/` was
changed.

Files covered: `device.py`, `end_user.py`, `gateway_rule.py`, `ldap.py`,
`alias.py`, `automatic_participant.py`, `global_settings.py`, `ivr_theme.py`,
`infrastructure.py`, `status.py` (line 60 to end), `history.py` (line 120 to
end), `command.py` (whole file). Paths below are relative to
`src/pexip_mcp/tools/` unless stated.

Test run: `uv run pytest tests/ -q -p no:cacheprovider --no-cov` →
**216 passed, 11 xfailed** (the xfails are the phase-1 catalog-quality gates in
`tests/test_catalog_quality.py`, as designed). Tests that pin behaviour this
review believes is wrong are listed per file and gathered in §Tests.

Legend. **CONFIRMED** = provable from the repo itself. **VERIFY** = the Pexip
field/endpoint/enum probably differs, but the proof needs a live node
(`/api/admin/<api>/v1/<resource>/schema/?format=json`) or the official docs.
**QUALITY** = description / parameter notes relevant to the planned rename
(kept brief; `tests/test_catalog_quality.py` already measures most of it).

Two repo-wide patterns recur in several files and are described once here:

* **P1 — FK filters sent as resource URIs.** `alias.py:44`,
  `automatic_participant.py:125`, `infrastructure.py:362`, `status.py:144`,
  `status.py:168`, `history.py:132`, `history.py:222` all build a list filter
  as `params["<fk>"] = fk_uri(...)` (e.g.
  `?conference=/api/admin/configuration/v1/conference/7/`). `fk_uri` was
  written for *bodies* (`_helpers.py:145-155`: "the URI string Pexip wants
  whenever one resource references another" on POST/PATCH). Pexip's API is
  Django-tastypie; the only related-object filter the docs show is the
  double-underscore form (`conference/?aliases__alias__contains=@` on the
  "Retrieving, paginating, filtering and ordering resource details" page), and
  tastypie's `build_filters` does not translate a URI string into a pk for an
  ORM lookup. Verify on a live node whether `?conference=<uri>` returns the
  scoped list, a 400 ("Invalid resource lookup data provided"), or silently the
  unfiltered list. If it fails, the fix is `conference=<int id>` or
  `conference__id=<int id>` and the status/history variants (see P2) need a
  name string instead. Seven tests currently assert the URI form
  (`tests/test_alias.py:354`, `tests/test_automatic_participant.py:415`,
  `tests/test_infrastructure.py:543`, `tests/test_status.py:484`,
  `tests/test_status.py:507`, `tests/test_history.py:726`).
* **P2 — configuration-API URIs used against status/history records.**
  Status and history objects do not carry configuration FK URIs; in the
  documented status `participant` example `system_location` is a plain
  location name, and history `participant` carries `conference_name` as a
  string. `status.py:144` (`alarm?node=<config worker_vm URI>`),
  `status.py:168` (`worker_vm?system_location=<config URI>`),
  `history.py:132/222` (`participant?system_location=<config URI>`) therefore
  look wrong independently of P1. The config-API lookup that precedes them
  (`resolve_id_by_field(... "system_location" ...)`) is still useful, but the
  value to send is almost certainly the *name*.
* **P3 — raw record returned after create/update.** `conference.py:100-101`
  documents a deliberate convention: read paths redact, create/update return
  the raw record "so the caller can confirm the value it just set".
  `resource_crud.py:288,315` does the opposite (redacts after create/update).
  `device.py`, `ldap.py`, `global_settings.py` follow the conference
  convention. The redact helper exists precisely because "we never rely on"
  Pexip masking credential fields (`_helpers.py:86-88`), so returning
  `bind_password` / device `password` raw on create/update is the one place
  that reliance is reintroduced. Pick one convention; this review recommends
  redact-everywhere (the caller already knows the value it just sent).

---

## device.py

### CONFIRMED
1. **create/update return unredacted records** (`device.py:122`, `:160`) while
   `list_devices`/`get_device` redact (`:69`, `:77`). Pattern P3; the device
   record carries `password`.
2. **`list_registrations` is a Status-API tool living in a Configuration
   module** (`device.py:172-201`). It is the only non-`status.py` tool that
   hits `api="status"`. Not a bug, but it will be missed by any
   module-per-API reasoning (and the plan's status registry) — flagging so the
   phase-4 fold does not lose it. It also duplicates the spirit of
   `status.list_registration_aliases` (`status.py:256-273`); `registration`
   vs `registration_alias` are different Pexip resources, so both are valid,
   but the two descriptions do not tell the model when to pick which.
3. **Silent-no-op risk on unknown fields.** Every optional flag is forwarded
   verbatim (`device.py:106-118`, `:140-153`). Tastypie ignores unknown keys on
   POST/PATCH, so a wrong field name does not error — the device is created
   and the flag is simply not set. This matters for item V1 below.

### VERIFY
* **V1 `enable_infinity_connect`** (`device.py:90`, `:103`, `:114`, `:136`,
  `:149`). Pexip's registration docs describe two distinct Infinity Connect
  registration modes per device alias — non-SSO (username/password) and SSO —
  and recommend enabling only one per alias. The device schema therefore most
  likely exposes `enable_infinity_connect_non_sso` and
  `enable_infinity_connect_sso` (plus `enable_standard_sso`), not a single
  `enable_infinity_connect`. Check `device/schema/?format=json`. If so, the
  flag is a silent no-op today (item 3) and `test_create_device_omits_unset_fields`
  (`tests/test_device.py:50-59`) only pins `enable_sip`, so nothing catches it.
* **V2 `tag`** on `device` (`device.py:68`, `:115`, `:150`): confirm the
  schema has `tag` (it does have `sync_tag`); if not, filter and payload are
  silent no-ops.
* **V3 status `registration` filters** (`device.py:194`, `:196`):
  `alias__icontains` and `protocol` must appear in the status resource's
  filtering block. Also confirm the `protocol` enum in the docstring
  (`"sip" / "h323" / "mssip" / "webrtc"`, `:188`).

### QUALITY
* `get_device`, `delete_device` descriptions are one line (<120 chars) with no
  "use when".
* `device` (int | str, alias-or-id) is a good unambiguous handle; keep it
  through the rename. `password` here is the *registration* password — the
  rename should say so since `pin`/`password` also appear elsewhere.
* No `fetch_all` on `list_devices` though every other list of a potentially
  large table (`end_user`, `conference_alias`) also lacks it — consistent, so
  not a defect, but a large LDAP-provisioned estate will hit the 20/offset
  loop.

---

## end_user.py

### CONFIRMED
* No defects found. Field names (`primary_email_address`, `first_name`,
  `last_name`, `display_name`, `telephone_number`, `mobile_number`, `title`,
  `department`, `avatar_url`, `sync_tag`) are consistent with the `end_user`
  resource as used elsewhere in the repo. No secret-bearing fields, so no
  redaction is needed. Local 400 on empty patch (`end_user.py:137`) correctly
  uses `upstream=False`.
* **`update_end_user` cannot change `primary_email_address`**
  (`end_user.py:110-121` omits it). Because the email is the lookup handle
  (`:21-29`) this is defensible, but the description does not say "to change
  the email, delete and recreate" — the model will try and get a 400.

### VERIFY
* **V4 `sync_tag` filter** (`end_user.py:56-57`): confirm `sync_tag` is in the
  `end_user` filtering block; otherwise tastypie returns 400 for an
  unfilterable field.

### QUALITY
* `user` as the name-or-id handle is fine, but `user` is also the natural word
  for an *admin* user (`role`, `permission` resources in `resource_crud`).
  Consider `end_user` for the rename.
* `get_end_user`, `delete_end_user`, `update_end_user` descriptions are under
  120 chars.

---

## gateway_rule.py

### CONFIRMED
1. **`order_by=priority` is sent on every list call** (`gateway_rule.py:63`).
   Tastypie returns HTTP 400 (`InvalidSortError`) when the field is not in the
   resource's `ordering` list, so if `priority` is not orderable the tool fails
   on every call, not just when sorting is wanted. This is a correctness
   dependency the test (`tests/test_gateway_rule.py:212-224`) cannot see
   because it mocks the response. Needs V5.
2. **The tool cannot express which direction/protocol a rule matches.**
   Pexip rules carry `match_incoming_calls`, `match_outgoing_calls`,
   `match_incoming_sip/h323/mssip/webrtc/teams`, `match_source_location`,
   `match_incoming_only_if_registered`; none is exposed by
   `create_gateway_rule`/`update_gateway_rule` (`:80-131`, `:135-182`). The
   docs for the `dial` command (used by `command.dial_participant`) say a
   routed dial-out "must match an *outgoing* Call Routing Rule", so an operator
   cannot build the rule that `dial_participant(routing=...)` would need via
   this server. Not a wrong-field bug; a coverage gap worth recording before
   the typed tool is frozen.
3. `enabled_only` → `enable="True"` (`:66-67`) is a valid tastypie boolean
   literal; fine.

### VERIFY
* **V5 `priority` in `ordering`** for `gateway_routing_rule` (see item 1).
* **V6 `called_device_type` docstring enum** (`:103`:
  `"mssip", "lync", "external", "registration", "gms"`). Pexip's choices are
  believed to be of the form `external`, `mssip_server`,
  `mssip_conference_id`, `gms_conference`, `teams_conference`, `registration`.
  The docstring is the only guidance the model gets; a wrong enum here costs a
  400 round-trip (upstream, so the model only sees "Pexip API error 400 (ref
  …)" and cannot self-correct).
* **V7 `crypto_mode` docstring enum** (`:107`:
  `"best_effort" / "required" / "none"`). Pexip's conference/rule
  `crypto_mode` values are believed to be `besteffort`, `on`, `off` (empty =
  use global). Same failure mode as V6.
* **V8 `outgoing_protocol` enum** (`:104`): confirm `"teams"` and `"rtmp"`
  spellings; `"gms"` is also a protocol on rules and is missing from the
  docstring.

### QUALITY
* `rule` (name-or-id) is unambiguous; keep.
* `outgoing_location` is resolved to a config FK URI *in a body*
  (`:118`, `:123`) — that is the correct use of `fk_uri` (contrast P1).
* `create_gateway_rule` has 8 optional params and no input example (phase-1
  gate already xfails on this).

---

## ldap.py

### CONFIRMED
1. **create/update return unredacted records** (`ldap.py:306`, `:348`) while
   list/get redact (`:242`, `:254`). Pattern P3; this record carries the LDAP
   bind password. Highest-value instance of P3 in the repo because an LDAP
   bind account is a directory credential, not a meeting PIN.
2. **Silent-no-op risk** on every optional field (`:293-304`, `:327-341`) —
   same mechanism as device item 3 — and here the fields most likely to be
   wrong are the credentials (V9). The observable symptom would be "source
   created, sync fails to bind", with no error returned to the model.

### VERIFY
* **V9 field names** (`ldap.py:263-270`, `:294-301`). Pexip's admin UI for an
  LDAP sync source has: LDAP server, Base DN, **Bind username**, **Bind
  password**, Use Global Catalog, Permit no TLS, User search DN, User filter,
  plus `ldap_sync_field` mappings. The API keys are believed to be prefixed:
  `ldap_bind_username`, `ldap_bind_password`, `ldap_use_global_catalog`,
  `ldap_permit_no_tls`, `ldap_user_search_dn`, `ldap_user_filter`. The tool
  sends `bind_username` / `bind_password` (unprefixed) and three fields with
  no known UI counterpart: `ldap_user_search_filter`,
  `ldap_permitted_users_regex`, `sync_interval_minutes` (Pexip LDAP sync is a
  platform-wide schedule, not per-source, so `sync_interval_minutes` is the
  most doubtful). Check `ldap_sync_source/schema/?format=json`.
  `tests/test_ldap.py:177` asserts `payload["bind_password"] == "secret"`, i.e.
  it pins the suspect name.
* **V10 "last sync status / errors"** claimed by `get_ldap_source`
  (`ldap.py:249-250`, module docstring `:7-9`). Confirm the configuration
  resource actually carries sync-result fields; if sync status lives only in
  the admin UI / status API, the description over-promises and the model will
  tell the user "LDAP is fine" from a record that says nothing about it.

### QUALITY
* `source` as the handle is fine but generic; `ldap_source` reads better in a
  prefixed catalog.
* `list_ldap_sources`, `update_ldap_source`, `delete_ldap_source` descriptions
  are <120 chars; none says when to use `conference_sync_template` (the
  *VMR*-from-LDAP sync, exposed via `resource_crud`) versus this (the
  *end_user*-from-LDAP sync). That is the real disambiguation the model needs.
* Missing params that the UI has: `ldap_use_global_catalog`,
  `ldap_permit_no_tls` — the latter matters because the docs say TLS requires
  the CA to be trusted; without the flag a lab LDAP without TLS cannot be
  configured here.

---

## alias.py

### CONFIRMED
1. **`delete_alias(alias_id: int)` only accepts the integer id**
   (`alias.py:78-81`) and tells the model to call `list_aliases` first, while
   every sibling delete tool resolves name-or-id. `conference_alias.alias` is
   unique, so `resolve_id_by_field(client, "conference_alias", value,
   field="alias")` would work. One extra tool call per deletion today.
2. **No update tool** — to change a dial string you delete and re-add. Not a
   bug; record before the typed surface is frozen.
3. `add_vmr_alias` body uses `fk_uri` correctly (`:70`); `list_aliases`
   uses it as a *filter* (`:44`) — pattern P1.

### VERIFY
* **V11 `?conference=<uri>` filter** (`alias.py:44`) — P1.
  `tests/test_alias.py:354` asserts the URI form.

### QUALITY
* `alias` means "exact filter value" in `list_aliases` and "the dial string to
  create" in `add_vmr_alias`; same type and meaning, acceptable.
* `alias_id` vs `participant_id` vs `conference_id` style ids: see
  automatic_participant item 2 and the parameter-name table at the end.

---

## automatic_participant.py

### CONFIRMED
1. **No update tool**; `delete` + `add` is the only way to change an entry.
2. **`participant_id` carries a second meaning** (`automatic_participant.py:197`):
   here it is the integer id of a *configuration* `automatic_participant`
   row; in `command.py` (`:174`, `:205`, `:221`, `:236`, `:257`, `:412`) and
   `status.py` (`:106`, `:190`) `participant_id` is a Status-API UUID *or a
   display name*. The plan (`docs/TOOL-ARCHITECTURE-PLAN.md` §3.6) only names
   `conference_id`; `participant_id` has the same problem and the
   `test_parameter_names_have_one_type_across_catalog` xfail will trip on it
   (int vs string).
3. `system_location` and `conference` in the POST body use `fk_uri` correctly
   (`:171`, `:177`).

### VERIFY
* **V12 `keep_conference_alive` enum in the docstring** (`:161-162`:
  `"always" / "if_multiple_other" / "if_one_other_no_chair" / "never"`).
  Pexip's values, confirmed from developer.pexip.com and the admin guide, are
  `keep_conference_alive`, `keep_conference_alive_if_multiple`,
  `keep_conference_alive_never`. A model following the docstring sends an
  invalid choice and gets an opaque upstream 400. `evals/cases/parameters.yaml:166`
  expects `keep_conference_alive: "always"`, so the eval enshrines the wrong
  value too.
* **V13 `routing` enum** (`:163`: `"auto" or "manual"`). The `dial` command
  docs show the automatic value is `routing_rule`; `manual` is right. Confirm
  the config resource uses the same pair.
* **V14 `protocol` enum** (`:155`) includes `"auto"`; Pexip ADP protocols are
  `sip`, `h323`, `mssip`, `rtmp`, `gms`, `teams` — `auto` is not a known
  choice. Also confirm `presentation_url` exists (not exposed; harmless).
* **V15 `?conference=<uri>` filter** (`:125`) — P1.
  `tests/test_automatic_participant.py:415` asserts the URI form.

### QUALITY
* The rename should pick a distinct id name here (`auto_participant_id` or
  accept the alias string) — see item 2.
* `add_automatic_participant` has 10 optional params and no input example.

---

## global_settings.py

### CONFIRMED
1. **`update_global_settings` returns the record unredacted**
   (`global_settings.py:52`) while `get_global_settings` redacts (`:25`).
   Pattern P3.
2. **`updates` is a free-form dict with no key validation** (`:30`, `:51`):
   tastypie silently ignores unknown keys, so a typo'd field name "succeeds"
   and the returned record simply does not show the change. The tool should
   compare requested keys against the returned record (or against
   `get_resource_schema('global')`) and report untouched keys; today the
   model cannot tell a no-op from a success.
3. Local 400 on empty `updates` (`:49`) correctly keeps `upstream=False`.

### VERIFY
* **V16 example field names** (`:43-46`: `management_session_timeout_secs`,
  `guests_only_timeout`). Confirm both exist on `global`; the docstring
  example is the model's primary guidance for a free-form payload.
* **V17 description claims** (`:22-23`: "default themes, default join PIN
  behavior, bandwidth caps, banner text, MSSIP domain"). Confirm each is a
  `global` field rather than living on another resource (e.g. themes default
  via `ivr_theme`, banner via `login_banner` if that is a separate resource).

### QUALITY
* Already references `get_resource_schema('global')` — good. The freeform
  payload rule in `test_catalog_quality.py:94-105` requires a docs marker;
  the description does not contain "Management API" or "docs.pexip.com".

---

## ivr_theme.py

### CONFIRMED
* No defects. Read-only, name-or-id resolution, no secrets.

### VERIFY
* **V18** Module docstring (`ivr_theme.py:6-8`) says themes "are uploaded via
  the admin UI (binary assets aren't a great fit for an API)". Pexip's
  `ivr_theme` resource does accept a package upload via the API (multipart);
  the statement is a design choice, not a fact — reword so the model does not
  tell users the API cannot do it.

### QUALITY
* Both descriptions are <120 chars. `theme` (name-or-id) is fine; the rename
  should make the "use when choosing a value for `create_vmr(theme=...)`"
  link explicit (the module docstring says it, the tool descriptions do not).

---

## infrastructure.py

### CONFIRMED
1. **`worker_vm` reads are not redacted** (`infrastructure.py:367`, `:375`).
   The configuration `worker_vm` resource carries the node's admin `password`
   (set at deployment). Pexip probably masks it, but the repo's stated rule
   (`_helpers.py:86-88`) is not to rely on that; every other read path over a
   secret-bearing resource redacts. Low cost to add.
2. `system_location` filter uses a config URI (`:362`) — P1.

### VERIFY
* **V19 `?system_location=<uri>`** on config `worker_vm` (`:362`) — P1.
  `tests/test_infrastructure.py:543` asserts the URI form.
* **V20 `node_type` enum casing** (`:354`, `:366`: `"CONFERENCING"` /
  `"PROXYING"`). Believed correct (uppercase) but confirm against the schema
  choices; a wrong case returns an empty list, not an error.
* **V21 `worker_vm.password`** — confirm the field exists and whether the API
  echoes it (decides how important item 1 is).

### QUALITY
* `location` / `node` handles are good. `get_location`, `get_conferencing_node`
  descriptions are one line.

---

## status.py (lines 60 to end)

### CONFIRMED
1. **Two different access patterns for per-object media streams.**
   `get_participant_quality` lists `participant_media_stream` with a
   `participant=<status URI>` *filter* (`status.py:215-220`), whereas
   `get_backplane_media_streams` uses the *nested path*
   `backplane/<id>/media_stream` (`:368-370`). Pexip's Status API docs
   describe per-object component paths ("you must also use the relevant object
   ID in the path of component requests") for participant media, node load and
   backplane media alike. The backplane form matches the docs; the participant
   form does not. See V22. `tests/test_status.py:588-604` pins the filter
   form.
2. **`node_id` has two types in one module**: `int` in
   `get_management_node_status` (`:385`) and `str` in `get_cloud_node` (`:419`)
   and `get_teams_node_status` (`:530`). This is exactly the conflict
   `test_parameter_names_have_one_type_across_catalog` measures.
3. **Name resolution scans at most 200 participants**
   (`command.py:84`, used by `status.py:118`, `:212`). On a platform with more
   than 200 connected legs a valid display name can produce a 404 "No active
   participant matching …" that tells the model to check
   `list_active_participants` — which will then find the person. Either
   paginate or say "first 200" in the error.
4. **`list_management_node_status` has no `fetch_all`** (`:376-381`) while
   every other list in the module does; harmless (there is one Management
   Node) but inconsistent for a generic fold.
5. `get_conference_shard`, `get_registration_alias`, `get_backplane`,
   `get_cloud_*`, `get_exchange_scheduler_status`, `get_mjx_*`,
   `get_teams_*` (`:248-546`) take a bare id with no name resolution and
   one-line descriptions; they are the 39→8 fold candidates in the plan and
   nothing here argues against folding them.

### VERIFY
* **V22 participant media stream path** (`status.py:215-220`): confirm whether
  `/status/v1/participant_media_stream/?participant=<uri>` is a supported
  filter or whether the documented form is
  `/status/v1/participant/<uuid>/participant_media_stream/`. If the latter,
  `get_participant_quality` returns the participant record plus an empty (or
  400) stream list today.
* **V23 `alarm?node=<config worker_vm URI>`** (`:143-144`) — P1+P2. In status
  alarm records `node` is believed to be the node's name/address string.
  `tests/test_status.py:484` asserts the URI form.
* **V24 `worker_vm?system_location=<config URI>`** (`:167-168`) — P1+P2;
  status `worker_vm.system_location` is believed to be the location *name*.
  `tests/test_status.py:507` asserts the URI form.
* **V25 status ids vs configuration ids** (`:178-179`, `:309-310`,
  `:321-323`, `:338-340`). Each resolves the id via the *configuration*
  resource then GETs `status/v1/worker_vm/<id>/` or
  `status/v1/system_location/<id>/` (or `/statistics`). Confirm the status
  resources are keyed by the same integer id as configuration (they are
  believed to be, but if status rows carry their own `id` plus a
  `configuration_id`, every by-name lookup here can hit the wrong node).
* **V26 filterable fields on status resources**: `is_muted`, `role`,
  `protocol`, `conference` on `participant` (`:93-100`); `name`,
  `service_type`, `tag` on `conference` (`:63-68`, lines <60 but same
  filtering block); `conference_name` on `conference_shard` (`:243`);
  `alias__icontains` on `registration_alias` (`:272`); `name__icontains` on
  status `system_location` (`:301`), `worker_vm` (`:170`), `mjx_endpoint`
  (`:494`). Status resources often expose fewer filters than config ones; any
  unfilterable field gives a 400 on the whole call.
* **V27 `service_type` enum** (`:56`) includes `two_stage_dialing` and
  `test_call`; confirm spellings.

### QUALITY
* `participant_id` means "UUID *or display name*" here (`:111-114`) but only
  "UUID" in the parameter name — the rename should use a handle-style name
  (`participant`) matching `vmr`/`device`/`rule`.
* `conference` (`:106`, `:190`) is a *scoping* name string, while
  `conference_id` elsewhere is a UUID-or-name handle; two names for the same
  concept.

---

## history.py (lines 120 to end)

### CONFIRMED
1. **The same concept is addressed by two field names in one file.**
   Filters send `params["conference"] = conference_name` (`history.py:121`,
   `:215`) but `summarize_calls` groups on `obj.get("conference_name")`
   (`:155`, `:232`). Pexip's history API example participant record carries
   `'conference_name': 'VMR_1'` (confirmed from the docs snippet), so the
   group-by key is right and the filter key is the one to doubt (V28). If
   `conference` on a history participant is the URI of the history
   `conference` row, the filter either 400s or matches nothing.
2. **`total_calls` counts participant legs, not calls** (`:243`). A two-party
   gateway call is two history participants; the key name and the docstring
   ("how many calls by X") will mislead the user's report. Rename the key
   (`total_participant_legs`) or document it.
3. **`conference_id` takes a third meaning** in `get_history_conference`
   (`:77`): a history UUID (string or int accepted), versus a live UUID-or-name
   in `command.py:293+` and a config int in `command.py:432/449/463`.
4. `summarize_calls` validates `group_by` locally with `upstream=False`
   (`:206-210`) — correct and actionable.
5. `_list` caps `fetch_all` at 10,000 (`:35`) matching the documented
   retention; `summarize_calls` exposes `max_records` separately (`:171`) and
   reports `truncated` + `server_total_count` (`:249-250`) — good.

### VERIFY
* **V28 history `participant?conference=<name>`** (`:121`, `:215`): confirm
  whether the filterable field is `conference_name` (per the documented record)
  or `conference`.
* **V29 history `participant?system_location=<config URI>`** (`:131-132`,
  `:221-222`) — P1+P2; the record is believed to hold the location name.
  `tests/test_history.py:726` asserts the URI form.
* **V30 history `alarm` filters** `time_raised__gte/__lt`, `level`
  (`:277-281`): confirm they are in the filtering block.
* **V31 `workervm_status_event` time field** (`:372-374` uses `time__gte`):
  confirm the field is `time` (not `timestamp`/`event_time`) and is
  filterable.
* **V32 `duration` units** (`:236`): the docstring says seconds; confirm the
  history participant `duration` is an integer number of seconds (the UI shows
  h:m:s).
* **V33 `_GROUP_BY_FIELDS`** (`:149-158`): confirm each is a real key on the
  history participant record (`vendor`, `service_tag`, `system_location`,
  `disconnect_reason`, `call_quality`, `call_direction`, `protocol`,
  `conference_name`). An absent key silently buckets everything as
  `"unknown"` rather than erroring.

### QUALITY
* `conference_name` (string filter) here vs `conference` (string filter) in
  `status.py:75` vs `conference_id` (UUID/name) in `command.py` — three names
  for "which conference".
* `summarize_calls` is the best-described tool in the catalog (explicit "USE
  THIS for …", returns shape). Use it as the template for the description
  rule in the plan.

---

## command.py (whole file)

### CONFIRMED
1. **`send_device_email` takes `conference_id`** (`command.py:462-472`) and
   its docstring says "conference/VMR"; the endpoint sends the provisioning
   email to a *device* owner (docs: "Send provisioning email to device owner
   /api/admin/command/v1/conference/send_device_email/"). Known bug;
   `evals/cases/tool_selection.yaml:400` ("device 7") still expects this tool,
   so the eval passes while the call would target VMR 7. The body field is
   most likely `device_id` (V34).
2. **`conference_id` has three meanings across the catalog**: live UUID *or
   name* (`:293`, `:320`, `:334`, `:346`, `:360`, `:374`), configuration
   integer id (`:432`, `:449`, `:463`), history UUID (`history.py:77`).
   Known; listed for completeness with line refs.
3. **`set_conference_layout` docstring recommends layout names the Command API
   does not use** (`:381-382`: `"one_main_zero_pips"`,
   `"two_mains_seven_pips"`, `"four_mains_zero_pips"`, `"nine_equal"`,
   `"sixteen_equal"`). Pexip's `transform_layout` takes layout *codes* —
   `"1:0"`, `"1:7"`, `"1:21"`, `"2:21"`, `"1:33"`, `"4:0"`, `"9:0"`, `"16:0"`,
   `"25:0"`, `"5:7"`, `"ac_presentation_in_mix"`,
   `"ac_presentation_in_mix_group"` (developer.pexip.com `LayoutEvent`; a
   Pexip community plugin shows `transforms: {host_layout: '25:0'}`). The
   docstring values are copied from the *configuration* `host_view` enum
   (`conference.py:133`), and three of them (`two_mains_seven_pips`,
   `nine_equal`, `sixteen_equal`) exist in neither API. Provable from the repo
   as "wrong vocabulary for this API"; whether the command also accepts the
   config names needs V35. Pinned by `tests/test_command.py:300-330` and
   `evals/cases/parameters.yaml:117,248`.
4. **`certificates_import` tells the model to read a schema it cannot
   fetch** (`:505-506`:
   `/api/admin/command/v1/platform/certificates_import/schema/`).
   `get_resource_schema` hard-codes `api="configuration"` (`schema.py:29`,
   `client.py:206-211`) and `client.schema()` passes the resource through
   `_safe_segment`, which rejects `platform/certificates_import`
   (`client.py:208`). Same gap for every `settings: dict` command tool
   (`:500`, `:515`, `:535`, `:549`). Either extend `get_resource_schema` with
   an `api` parameter and multi-segment support, or inline the known fields.
5. **`transfer_participant` has no `conference` scoping parameter**
   (`:255-261`, `:277`) while every other participant tool accepts one
   (`:174`, `:205`, `:221`, `:236`, `:412`). A display name that is ambiguous
   across meetings cannot be disambiguated here except by UUID.
6. **A 404 is reported as success** in `disconnect_participant` (`:193-199`)
   and `disconnect_conference` (`:309-315`). A 404 from the Command API also
   covers "no such participant/conference UUID" (typo, stale id, wrong
   platform), so the model reports "already disconnected" for a leg that is
   still live. The idempotency goal is sound; the result should distinguish
   "resolved by name a moment ago and now gone" from "never found".
7. **Display-name resolution caps the search at 200 participants**
   (`:84`), see status.py item 3. Substring fallback (`:91-93`) means
   `"Al"` matches `"Alice"` and `"Alan"` and raises 409 — good — but a
   *unique* substring silently selects a participant the user may not have
   meant (e.g. `"Bob"` → `"Bobby Tables"`). Consider requiring exact match
   unless the caller opts into fuzzy.
8. **Annotation preset stretch.** `control(...)` is documented as "Command
   API actions that change live call state" (`_helpers.py:311-319`) but is
   also applied to `sync_conference_ldap`, both email commands,
   `backup_create`, `take_snapshot`, `certificates_import`,
   `start_cloud_node`, `platform_upgrade`, `upload_software_bundle`
   (`:430`, `:447`, `:461`, `:478-547`). `backup_create` and `take_snapshot`
   create artefacts and mutate nothing an operator would call destructive,
   yet carry `destructiveHint=True`; emails are side-effecting but not
   destructive. The hints are conservative rather than wrong, but the plan's
   `pexip_run_platform_command(command: enum)` will need a per-command hint
   table anyway.
9. **`dial_participant` resolves an integer `system_location` to its name**
   (`:150-158`) — correct for the dial command (which takes a location name,
   per the docs) and a nice contrast to P1; note the test name
   `test_dial_participant_resolves_system_location_to_uri`
   (`tests/test_command.py:144`) is misleading — the body contains the *name*
   (`:170`).
10. **PexipError flags are used correctly throughout**: every locally raised
    error (`:52`, `:60`, `:95`, `:103`, `:247`, `:276`, `:396`) keeps
    `upstream=False`, so its remediation text reaches the model; upstream
    errors are re-raised untouched. No mis-flagging found in any reviewed
    module.
11. Status→command coupling: `status.py:29` imports
    `_resolve_active_participant_id` from `command.py`. Works, but a resolver
    used by read tools lives in the write module; move to `_helpers` before
    the toolset split, or the `live`/`health` toolsets will drag `command`
    in.

### VERIFY
* **V34 `send_device_email` body field** (`:471`): expected `device_id`; fetch
  `/api/admin/command/v1/conference/send_device_email/schema/?format=json`.
* **V35 `transform_layout` vocabulary** (`:381-382`, `:390-394`): confirm the
  Management Command API `transforms` object takes the `"1:7"`-style codes
  (and whether `layout` as a single key is also accepted). Also confirm
  `host_layout`/`guest_layout` are the key names on the *management* command
  (they are on the client API).
* **V36 `dial` enums** (`:137-138`): `call_type` is believed to be
  `video` / `video-only` / `audio` — the docstring adds `"audio-video"`,
  which is not a known value; `protocol` adds `"auto"`, also not known.
  Confirm `gms`/`teams` are accepted protocols on `dial`.
* **V37 `dial` missing fields**: the docs show `routing` (`routing_rule` /
  `manual`) on `dial`, and `keep_conference_alive` and `presentation_url` are
  dial-time options in the admin UI. None is exposed (`:117-128`). Without
  `routing=routing_rule` the tool can only do manual dial-outs.
* **V38 `transfer` body** (`:278-285`): confirm `pin` and `role` are accepted
  fields on `participant/transfer`.
* **V39 `conference/sync` body field** (`:439-441`): the tool sends
  `conference_id` with a `conference_sync_template` integer. Confirm the field
  name (the plan assumes `template_id`); the docs label the command "Sync LDAP
  template" but the snippet did not show its schema.
* **V40 `platform/snapshot` and `platform/backup_create` bodies**
  (`:481`, `:530` send `{}`): a third-party rendering of the Pexip command
  reference (context7 `llms.txt`) lists a **required `name` string** for both.
  If accurate, both tools 400 on every call today, and the
  `evals/cases/tool_selection.yaml:633` case (`take_snapshot`) only checks
  tool choice. Pexip's UI also requires a backup **passphrase**; confirm
  whether the API does.
* **V41 `platform/backup_restore` body** (`:494`: `{"backup_id": int}`):
  confirm the field; the UI restore flow takes a backup *file* plus the
  passphrase, so `package`/`passphrase` are plausible instead.
* **V42 `platform/upgrade`, `start_cloudnode`, `software_bundle` bodies**
  (`:523`, `:543`, `:557`): free-form `settings` with no guidance on required
  fields (e.g. `package` for upgrade). Confirm minimum bodies and put them in
  the descriptions, since item 4 means the model cannot discover them.
* **V43 `_resolve_active_conference_id` matches `name=` only** (`:49`): the
  module docstring (`:12-13`) promises "name **or alias**". Confirm whether
  status `conference.name` equals the dialed alias; if not, an alias lookup
  needs a configuration `conference_alias` → `conference.name` hop.

### QUALITY
* `conference_alias` (`:119`, `:258`) is the only place the model is asked
  for an *alias* rather than a name/UUID; the description says "Alias of the
  conference to dial INTO" but not that a VMR *name* will not work here.
* `participant_id` means "UUID or display name" (`:182-184`); see status.py
  QUALITY.
* 13 of 23 descriptions are under 120 chars; `mute_guests`, `unmute_guests`,
  `lock_conference`, `unlock_conference` do not say what happens to
  participants already in the lobby (unlock admits them? only new joiners?).
* `settings` is used as the free-form payload name in four platform tools and
  in `resource_crud.create_resource/update_resource` with a different meaning
  (resource fields vs command parameters). Acceptable, but the plan's
  `pexip_run_platform_command(command, params)` should use `params`.

---

## Tests that pin behaviour this review believes is wrong

| Test | Pins | Review item |
|---|---|---|
| `tests/test_command.py:300-312` | `host_layout="four_mains_zero_pips"` sent to `transform_layout` | command 3 / V35 |
| `tests/test_command.py:315-330` | `"one_main_zero_pips"`, `"nine_equal"` layouts | command 3 / V35 |
| `tests/test_command.py:144` | test *name* says "to_uri"; body is the name (correct) | command 9 (rename test) |
| `tests/test_ldap.py:177` | `payload["bind_password"]` (unprefixed field) | V9 |
| `tests/test_alias.py:354` | `?conference=<config URI>` filter | P1 / V11 |
| `tests/test_automatic_participant.py:415` | `?conference=<config URI>` filter | P1 / V15 |
| `tests/test_infrastructure.py:543` | `?system_location=<config URI>` filter | P1 / V19 |
| `tests/test_status.py:484` | `alarm?node=<config URI>` | P1+P2 / V23 |
| `tests/test_status.py:507` | status `worker_vm?system_location=<config URI>` | P1+P2 / V24 |
| `tests/test_status.py:588-604` | `participant_media_stream?participant=<status URI>` | status 1 / V22 |
| `tests/test_history.py:726` | history `participant?system_location=<config URI>` | P1+P2 / V29 |
| `evals/cases/parameters.yaml:117,248` | `four_mains_zero_pips`, `nine_equal` | command 3 |
| `evals/cases/parameters.yaml:166` | `keep_conference_alive: "always"` | V12 |
| `evals/cases/tool_selection.yaml:400` | `send_device_email` for "device 7" (tool choice right, payload wrong) | command 1 |

None of these tests is *failing*; they mock the Management Node, so they
encode the author's belief about the API rather than the API. They should be
updated in the same change that resolves the corresponding VERIFY item.

---

## Parameter names with more than one meaning (for the rename)

| Name | Meanings | Where |
|---|---|---|
| `conference_id` | live UUID-or-name; config int; history UUID | `command.py:293-374`; `command.py:432,449,463`; `history.py:77` |
| `participant_id` | status UUID-or-display-name; config int | `command.py:174+`, `status.py:106,190`; `automatic_participant.py:197` |
| `node_id` | `int` (management_vm); `str` (cloud_node, teamsnode) | `status.py:385`; `status.py:419,530` |
| `conference` / `conference_name` / `conference_alias` | scoping name (status); exact name filter (history); dial alias (command) | `status.py:106,190`, `command.py:174+`; `history.py:87,167`; `command.py:119,258` |
| `location` / `location_id` / `system_location` / `outgoing_location` | name-or-id handle; raw status id; FK name-or-id; FK name-or-id | `infrastructure.py:333`, `status.py:151`; `status.py:435,451`; `automatic_participant.py:139`, `command.py:124`; `gateway_rule.py:88` |
| `alias` | exact filter; dial string to create; device registration alias | `alias.py:24,55`; `device.py:83` |
| `settings` | command params; resource fields | `command.py:500-549`; `resource_crud.py` |
| `tag` / `service_tag` / `sync_tag` | same Pexip `tag` concept under three names | `device.py:49`, `status.py:45`, `history.py:93`, `end_user.py:38` |

---

## Needs human review (all VERIFY items, by file:line)

Each needs either a live node (`GET /api/admin/<api>/v1/<resource>/schema/?format=json`
for resources; `GET /api/admin/command/v1/<scope>/<action>/schema/?format=json`
for commands) or the official docs page.

**Cross-cutting**
- P1 — `?<fk>=<configuration URI>` as a list filter: `alias.py:44`,
  `automatic_participant.py:125`, `infrastructure.py:362`, `status.py:144`,
  `status.py:168`, `history.py:132`, `history.py:222`. Check one (e.g.
  `conference_alias/?conference=/api/admin/configuration/v1/conference/<id>/`)
  against `conference_alias/?conference=<id>` and `?conference__id=<id>`.
- P2 — config URIs against status/history records: `status.py:144`,
  `status.py:168`, `history.py:132`, `history.py:222`. Inspect one status
  `worker_vm`, one status `alarm`, one history `participant` record and read
  the actual `system_location` / `node` / `conference` values.

**device.py**
- V1 `device.py:90,103,114,136,149` — `enable_infinity_connect` vs
  `enable_infinity_connect_non_sso` / `enable_infinity_connect_sso` /
  `enable_standard_sso`.
- V2 `device.py:68,115,150` — `tag` exists on `device`?
- V3 `device.py:188,194,196` — status `registration` filterable fields and
  `protocol` enum.

**end_user.py**
- V4 `end_user.py:56-57` — `sync_tag` filterable.

**gateway_rule.py**
- V5 `gateway_rule.py:63` — `priority` in `ordering` (every list call 400s if
  not).
- V6 `gateway_rule.py:103` — `called_device_type` choices.
- V7 `gateway_rule.py:107` — `crypto_mode` choices (`besteffort`/`on`/`off`?).
- V8 `gateway_rule.py:104` — `outgoing_protocol` choices incl. `gms`.

**ldap.py**
- V9 `ldap.py:263-270, 294-301, 313-323, 328-338` — field names
  (`ldap_bind_username`, `ldap_bind_password`, `ldap_user_search_dn`,
  `ldap_user_filter`, `ldap_use_global_catalog`, `ldap_permit_no_tls`);
  existence of `ldap_user_search_filter`, `ldap_permitted_users_regex`,
  `sync_interval_minutes`.
- V10 `ldap.py:7-9, 249-250` — does the config record carry last-sync status?

**alias.py**
- V11 `alias.py:44` — P1.

**automatic_participant.py**
- V12 `automatic_participant.py:161-162` — `keep_conference_alive` enum
  (`keep_conference_alive` / `keep_conference_alive_if_multiple` /
  `keep_conference_alive_never`).
- V13 `automatic_participant.py:163` — `routing` enum (`routing_rule` /
  `manual`).
- V14 `automatic_participant.py:155` — `protocol` enum (`auto`?).
- V15 `automatic_participant.py:125` — P1.

**global_settings.py**
- V16 `global_settings.py:43-46` — `management_session_timeout_secs`,
  `guests_only_timeout` exist on `global`.
- V17 `global_settings.py:22-23` — which listed settings are actually on
  `global`.

**ivr_theme.py**
- V18 `ivr_theme.py:6-8` — API upload of theme packages is possible; reword.

**infrastructure.py**
- V19 `infrastructure.py:362` — P1.
- V20 `infrastructure.py:354,366` — `node_type` choice casing.
- V21 `infrastructure.py:367,375` — `worker_vm.password` present/echoed?

**status.py**
- V22 `status.py:215-220` — `participant_media_stream?participant=<uri>` vs
  `participant/<uuid>/participant_media_stream/`.
- V23 `status.py:143-144` — alarm `node` value type and filterability.
- V24 `status.py:167-168` — status `worker_vm.system_location` value type.
- V25 `status.py:178-179, 309-310, 321-323, 338-340` — status ids equal
  configuration ids?
- V26 `status.py:63-68, 93-100, 170, 243, 272, 301, 494` — filterable fields
  on each status resource.
- V27 `status.py:56` — `service_type` enum spellings.

**history.py**
- V28 `history.py:121, 215` — `conference` vs `conference_name` filter.
- V29 `history.py:131-132, 221-222` — P1+P2.
- V30 `history.py:277-281` — history `alarm` filters.
- V31 `history.py:372-374` — `workervm_status_event` time field name.
- V32 `history.py:236` — `duration` units.
- V33 `history.py:149-158` — every `_GROUP_BY_FIELDS` key exists on the
  record.

**command.py**
- V34 `command.py:471` — `send_device_email` field (`device_id`?).
- V35 `command.py:381-382, 390-394` — `transform_layout` layout vocabulary
  and key names.
- V36 `command.py:137-138` — `dial` `protocol`/`call_type` enums
  (`audio-video`, `auto` not known).
- V37 `command.py:117-128` — `dial` missing `routing`,
  `keep_conference_alive`, `presentation_url`.
- V38 `command.py:278-285` — `transfer` accepts `pin`, `role`.
- V39 `command.py:439-441` — `conference/sync` field name.
- V40 `command.py:481, 530` — `snapshot` / `backup_create` require `name`
  (and passphrase?) — both tools send `{}`.
- V41 `command.py:494` — `backup_restore` field (`backup_id` vs
  `package`+`passphrase`).
- V42 `command.py:523, 543, 557` — minimum bodies for `start_cloudnode`,
  `upgrade`, `software_bundle`.
- V43 `command.py:12-13, 49` — "name or alias" promise vs `name=` lookup.

## Sources consulted (search snippets only; docs.pexip.com not fetchable here)

- Management command API: https://docs.pexip.com/api_manage/api_command.htm
  (endpoint list incl. `send_conference_email`, `send_device_email`, `sync`,
  `dial` with `routing=routing_rule`, schema URL pattern).
- Retrieving, paginating, filtering and ordering resource details:
  https://docs.pexip.com/v14/api_manage/api_resource_details.htm (filtering
  block at end of schema; `aliases__alias__contains` related-filter example;
  `order_by=-field`).
- Management status API: https://docs.pexip.com/v12/api_manage/api_status.htm
  and https://testdocs.pexip.com/api_manage/api_status.htm (per-object
  component paths; `participant` example with `system_location` name).
- Management history API: https://testdocs.pexip.com/api_manage/api_history.htm
  (`workervm_status_event`, `registration_alias`; participant example with
  `conference_name`, `service_tag`).
- Registering devices (non-SSO vs SSO Infinity Connect registration):
  https://docs.pexip.com/v19/admin/registering_devices.htm
- Automatically dialing out to a participant (keep-alive, routing modes):
  https://docs.pexip.com/admin/autodial_participant.htm and
  https://docs.pexip.com/admin/automatically_terminate.htm
- Layout codes: https://developer.pexip.com/docs/api/packages/infinity/interfaces/LayoutEvent
  and https://community.pexip.com/t/plugin-for-virtual-auditorium-va-to-change-layout-view-for-host-and-guest/182
- Client controls (keep_conference_alive enum, dial protocol/role enums):
  https://developer.pexip.com/docs/infinity/web/plugins/webapp-3/plugin-api/infinity-client-controls
- Backups (passphrase required in UI):
  https://docs.pexip.com/v12/admin/backup_restore.htm
- Third-party rendering of the command reference (claims `name` required on
  `snapshot`/`backup_create`; treat as unverified):
  https://context7.com/websites/pexip/llms.txt
