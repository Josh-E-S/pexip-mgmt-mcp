# Live Node Validation Test Plan

Test every pexip-mgmt MCP tool category against a real Pexip Infinity lab node. Work through each phase in order — later phases depend on resources created in earlier ones. Record pass/fail and any field name mismatches or unexpected errors.

**Lab node:** `manager.example.com`
**Test clients:** SIP client + WebRTC client (for generating live calls)

---

## Phase 1 — Read-only smoke test (no mutations)

Verify connectivity, auth, and that list/get tools return valid data.

```
1. Get the live JSON schema for VMRs:
   → get_resource_schema("conference")

2. List system locations:
   → list_locations()

3. List conferencing nodes:
   → list_conferencing_nodes()

4. Get global settings:
   → get_global_settings()

5. List IVR themes:
   → list_ivr_themes()

6. List current alarms:
   → list_alarms()

7. Get licensing status:
   → get_licensing_status()

8. List active conferences (expect empty or existing):
   → list_active_conferences()

9. List existing VMRs:
   → list_vmrs()

10. List end users:
    → list_end_users()
```

**Pass criteria:** All return valid JSON with `objects` arrays or single objects. No auth errors, no 404s on known resources.

---

## Phase 2 — Configuration CRUD (create → read → update → delete)

### 2a. VMR lifecycle

```
1. Create a test VMR:
   → create_vmr(name="test-validation-room", description="MCP test", pin="1234")

2. Read it back by name:
   → get_vmr("test-validation-room")

3. Add an alias:
   → add_vmr_alias(vmr="test-validation-room", alias="test-val@example.com")

4. List aliases filtered to our VMR:
   → list_aliases(vmr="test-validation-room")

5. Update the VMR description:
   → update_vmr("test-validation-room", description="MCP test - updated")

6. Delete the alias:
   → delete_alias(<alias_id from step 4>)

7. Delete the VMR:
   → delete_vmr("test-validation-room")

8. Confirm it's gone:
   → get_vmr("test-validation-room")  — should raise 404
```

### 2b. End user lifecycle

```
1. Create:
   → create_end_user(primary_email_address="mcptest@example.com", first_name="MCP", last_name="Test")

2. Read by email:
   → get_end_user("mcptest@example.com")

3. Update:
   → update_end_user("mcptest@example.com", first_name="Updated")

4. Delete:
   → delete_end_user("mcptest@example.com")
```

### 2c. Device lifecycle

```
1. Create:
   → create_device(alias="mcp-test-device@lab.local", enable_sip=true)

2. Read by alias:
   → get_device("mcp-test-device@lab.local")

3. Update:
   → update_device("mcp-test-device@lab.local", description="test device")

4. Delete:
   → delete_device("mcp-test-device@lab.local")
```

### 2d. Gateway rule lifecycle

```
1. Create:
   → create_gateway_rule(name="mcp-test-rule", match_string="^9999", replace_string="", protocol="sip", priority=9999)

2. Read by name:
   → get_gateway_rule("mcp-test-rule")

3. Delete:
   → delete_gateway_rule("mcp-test-rule")
```

### 2e. Policy profile lifecycle

```
1. Create:
   → create_policy_profile(name="mcp-test-policy")

2. Update:
   → update_policy_profile("mcp-test-policy", settings={"description": "test"})

3. Delete:
   → delete_policy_profile("mcp-test-policy")
```

---

## Phase 3 — Settings-dict resources (spot check)

These all use the `settings` dict pattern. Test one from each module to verify the resource name and API path are correct.

```
1. Schema discovery first:
   → get_resource_schema("dns_server")
   → get_resource_schema("sip_proxy")
   → get_resource_schema("webapp_alias")
   → get_resource_schema("role")
   → get_resource_schema("mjx_integration")

2. System — list DNS servers:
   → list_dns_servers()

3. System — list NTP servers:
   → list_ntp_servers()

4. System — list SMTP servers:
   → list_smtp_servers()

5. Call routing — list SIP proxies:
   → list_sip_proxies()

6. Call routing — list TURN servers:
   → list_turn_servers()

7. Call routing — list Azure tenants:
   → list_azure_tenants()

8. Call routing — list Google Meet gateway tokens:
   → list_gms_gateway_tokens()

9. Call routing — list Teams Connectors:
   → list_teams_proxies()

10. Web app — list webapp aliases:
    → list_webapp_aliases()

11. Admin auth — list roles:
    → list_roles()

12. Admin auth — list identity providers:
    → list_identity_providers()

13. Platform — list management nodes:
    → list_management_vms()

14. Platform — list CA certificates:
    → list_ca_certificates()

15. Platform — list TLS certificates:
    → list_tls_certificates()

16. MJX — list integrations:
    → list_mjx_integrations()

17. MJX — list endpoint groups:
    → list_mjx_endpoint_groups()

18. MJX — list meeting processing rules:
    → list_mjx_meeting_processing_rules()

19. Service config — list registration settings:
    → list_registration_settings()

20. Upgrade — list software bundles:
    → list_software_bundles()

21. Upgrade — list system backups:
    → list_system_backups()
```

**Pass criteria:** Each returns a valid response (even if `objects` is empty). Any 404 means the resource name is wrong for this Infinity version — note it.

---

## Phase 4 — Live call test (Status + Command APIs)

**Prerequisite:** Place a call into a VMR using the SIP or WebRTC test client.

### 4a. Status reads during a live call

```
1. List active conferences:
   → list_active_conferences()
   — Note the conference UUID

2. List active participants:
   → list_active_participants(conference_name="<name from step 1>")
   — Note the participant UUID

3. Get participant detail:
   → get_active_participant("<participant_uuid>")

4. Get live call quality:
   → get_participant_quality("<participant_uuid>")
   — Should return participant + media_streams

5. List conference shards:
   → list_conference_shards()

6. List node status:
   → list_node_status()

7. Get node load statistics:
   → get_node_statistics("<node_name>")

8. List registered aliases:
   → list_registration_aliases()

9. List current registrations (device.py):
   → list_registrations()
```

### 4b. Command actions during a live call

```
1. Mute the participant:
   → mute_participant("<participant_uuid>")

2. Unmute:
   → unmute_participant("<participant_uuid>")

3. Video mute:
   → video_mute_participant("<participant_uuid>")

4. Video unmute:
   → video_unmute_participant("<participant_uuid>")

5. Lock the conference:
   → lock_conference("<conference_uuid>")

6. Unlock:
   → unlock_conference("<conference_uuid>")

7. Mute all guests:
   → mute_guests("<conference_uuid>")

8. Unmute all guests:
   → unmute_guests("<conference_uuid>")

9. Send a message to all:
   → send_conference_message("<conference_uuid>", text="MCP test message")

10. Send a message to one participant:
    → send_participant_message("<participant_uuid>", text="Hello from MCP")

11. Set layout:
    → set_conference_layout("<conference_uuid>", host_layout="1:0")

12. Disconnect the participant:
    → disconnect_participant("<participant_uuid>")

13. Confirm disconnect idempotency:
    → disconnect_participant("<participant_uuid>")
    — Should return success with "already disconnected" note
```

---

## Phase 5 — History API (after the call ends)

Wait 30 seconds after the call ends, then:

```
1. List recent conference history:
   → list_history_conferences(start_time="<today_iso>T00:00:00")

2. Get the conference detail:
   → get_history_conference("<conference_id from step 1>")

3. List participant history:
   → list_history_participants(start_time="<today_iso>T00:00:00")

4. Get participant detail with quality:
   → get_history_participant("<participant_id>")
   — Should include bucketed_call_quality

5. Summarize calls:
   → summarize_calls(start_time="<today_iso>T00:00:00", end_time="<tomorrow_iso>T00:00:00", group_by="protocol")

6. List alarm history:
   → list_alarm_history()

7. List node event history:
   → list_node_event_history()
```

---

## Phase 6 — Error handling

```
1. Get a nonexistent VMR by name:
   → get_vmr("this-does-not-exist-12345")
   — Should return 404 error

2. Update with empty fields:
   → update_vmr("test-room", )  (no fields)
   — Should return 400 error

3. Delete a nonexistent resource:
   → delete_vmr(99999)
   — Should return 404 error

4. Invalid schema resource:
   → get_resource_schema("not_a_real_resource")
   — Should return an error

5. Summarize with invalid group_by:
   → summarize_calls(start_time="2026-01-01T00:00:00", end_time="2026-01-02T00:00:00", group_by="invalid")
   — Should return 400 with valid options listed
```

---

## Results template

| Phase | Test | Result | Notes |
|---|---|---|---|
| 1 | get_resource_schema | ⬜ | |
| 1 | list_locations | ⬜ | |
| ... | ... | ⬜ | |

Mark each: ✅ pass, ❌ fail (note the error), ⚠️ partial (works but unexpected response shape).

Any field name mismatches or resource path 404s should be logged — those are the fixes needed before publishing.
