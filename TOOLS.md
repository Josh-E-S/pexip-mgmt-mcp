# Tool Catalog

Auto-generated reference of all 72 tools exposed by the pexip-mgmt-mcp server (37 Configuration, 11 Status, 7 History, 16 Command, 1 Discovery).

Regenerate with: `uv run python scripts/generate_tools_md.py`

| Tool | Title | Read-only | Destructive | Idempotent | Parameters |
|---|---|---|---|---|---|
| `pexip_add_automatic_participant` | Add automatic participant | ❌ | ✅ | ❌ | vmr, alias, protocol?, call_type?, role?, system_location?, dtmf_sequence?, streaming?, keep_conference_alive?, routing?, remote_display_name?, description? |
| `pexip_add_vmr_alias` | Add conference alias | ❌ | ✅ | ❌ | vmr, alias, description? |
| `pexip_create_device` | Create device | ❌ | ✅ | ❌ | alias, username?, password?, description?, primary_owner_email_address?, enable_sip?, enable_h323?, enable_infinity_connect?, tag? |
| `pexip_create_end_user` | Create end user | ❌ | ✅ | ❌ | primary_email_address, first_name?, last_name?, display_name?, telephone_number?, mobile_number?, title?, department?, avatar_url? |
| `pexip_create_gateway_rule` | Create gateway routing rule | ❌ | ✅ | ❌ | name, priority, match_string, replace_string?, called_device_type?, outgoing_protocol?, outgoing_location?, call_type?, crypto_mode?, enable?, description? |
| `pexip_create_resource` | Create configuration resource | ❌ | ✅ | ❌ | resource, settings |
| `pexip_create_vmr` | Create VMR | ❌ | ✅ | ❌ | name, aliases?, pin?, guest_pin?, allow_guests?, description?, tag?, host_view?, guest_view?, allow_no_pin? |
| `pexip_delete_alias` | Delete conference alias | ❌ | ✅ | ✅ | alias_id |
| `pexip_delete_automatic_participant` | Delete automatic participant | ❌ | ✅ | ✅ | automatic_participant_id |
| `pexip_delete_device` | Delete device | ❌ | ✅ | ✅ | device |
| `pexip_delete_end_user` | Delete end user | ❌ | ✅ | ✅ | user |
| `pexip_delete_gateway_rule` | Delete gateway routing rule | ❌ | ✅ | ✅ | rule |
| `pexip_delete_resource` | Delete configuration resource | ❌ | ✅ | ✅ | resource, id |
| `pexip_delete_vmr` | Delete VMR | ❌ | ✅ | ✅ | vmr |
| `pexip_describe_resources` | Describe resources and tools | ✅ | ❌ | ✅ | api?, query?, detail? |
| `pexip_dial_participant` | Dial out to add a participant | ❌ | ✅ | ❌ | conference_alias, destination, protocol?, call_type?, role?, system_location?, streaming?, remote_display_name?, dtmf_sequence? |
| `pexip_disconnect_conference` | End a conference (disconnect everyone) | ❌ | ✅ | ✅ | conference |
| `pexip_disconnect_participant` | Disconnect (kick) a participant | ❌ | ✅ | ✅ | participant, conference? |
| `pexip_get_active_participant` | Get active participant | ✅ | ❌ | ✅ | participant, conference? |
| `pexip_get_conferencing_node` | Get conferencing node | ✅ | ❌ | ✅ | node |
| `pexip_get_device` | Get device | ✅ | ❌ | ✅ | device |
| `pexip_get_end_user` | Get end user | ✅ | ❌ | ✅ | user |
| `pexip_get_gateway_rule` | Get gateway routing rule | ✅ | ❌ | ✅ | rule |
| `pexip_get_history` | Get history resource | ✅ | ❌ | ✅ | resource, id |
| `pexip_get_history_conference` | Get historical conference | ✅ | ❌ | ✅ | conference_id |
| `pexip_get_history_participant` | Get historical participant | ✅ | ❌ | ✅ | participant_id |
| `pexip_get_licensing_status` | Get licensing status | ✅ | ❌ | ✅ |  |
| `pexip_get_location` | Get system location | ✅ | ❌ | ✅ | location |
| `pexip_get_node_status` | Get node status | ✅ | ❌ | ✅ | node |
| `pexip_get_participant_quality` | Get live participant quality | ✅ | ❌ | ✅ | participant, conference? |
| `pexip_get_platform_health` | Get platform health summary | ✅ | ❌ | ✅ |  |
| `pexip_get_resource` | Get configuration resource | ✅ | ❌ | ✅ | resource, id |
| `pexip_get_resource_schema` | Get resource schema | ✅ | ❌ | ✅ | resource |
| `pexip_get_status` | Get status resource | ✅ | ❌ | ✅ | resource, id |
| `pexip_get_vmr` | Get VMR | ✅ | ❌ | ✅ | vmr |
| `pexip_list_active_conferences` | List active conferences | ✅ | ❌ | ✅ | name?, service_type?, tag?, limit?, offset?, fetch_all?, response_format?, fields? |
| `pexip_list_active_participants` | List active participants | ✅ | ❌ | ✅ | conference_name?, role?, protocol?, is_muted?, limit?, offset?, fetch_all?, response_format?, fields? |
| `pexip_list_alarms` | List active alarms | ✅ | ❌ | ✅ | level?, node_name?, limit?, offset?, fetch_all?, response_format?, fields? |
| `pexip_list_aliases` | List conference aliases | ✅ | ❌ | ✅ | vmr?, alias?, alias_contains?, limit?, offset?, response_format?, fields? |
| `pexip_list_automatic_participants` | List automatic participants | ✅ | ❌ | ✅ | vmr?, alias_contains?, limit?, offset?, response_format?, fields? |
| `pexip_list_conferencing_nodes` | List conferencing nodes | ✅ | ❌ | ✅ | location?, name_contains?, node_type?, limit?, offset?, response_format?, fields? |
| `pexip_list_devices` | List devices | ✅ | ❌ | ✅ | alias_contains?, owner_email?, tag?, limit?, offset?, response_format?, fields? |
| `pexip_list_end_users` | List end users | ✅ | ❌ | ✅ | email_contains?, name_contains?, sync_tag?, limit?, offset?, response_format?, fields? |
| `pexip_list_gateway_rules` | List gateway routing rules | ✅ | ❌ | ✅ | name_contains?, enabled_only?, limit?, offset?, response_format?, fields? |
| `pexip_list_history` | List history resources | ✅ | ❌ | ✅ | resource, start_time?, end_time?, name_contains?, filters?, limit?, offset?, fetch_all?, response_format?, fields? |
| `pexip_list_history_conferences` | List historical conferences | ✅ | ❌ | ✅ | start_time?, end_time?, name?, service_type?, tag?, limit?, offset?, fetch_all?, response_format?, fields? |
| `pexip_list_history_participants` | List historical participants | ✅ | ❌ | ✅ | start_time?, end_time?, conference_name?, call_direction?, call_quality?, protocol?, disconnect_reason?, location?, service_tag?, limit?, offset?, fetch_all?, response_format?, fields? |
| `pexip_list_locations` | List system locations | ✅ | ❌ | ✅ | name_contains?, limit?, offset?, response_format?, fields? |
| `pexip_list_node_status` | List node status | ✅ | ❌ | ✅ | location?, name_contains?, limit?, offset?, fetch_all?, response_format?, fields? |
| `pexip_list_registrations` | List current registrations | ✅ | ❌ | ✅ | alias_contains?, protocol?, limit?, offset?, fetch_all?, response_format?, fields? |
| `pexip_list_resources` | List configuration resources | ✅ | ❌ | ✅ | resource, name_contains?, filters?, limit?, offset?, response_format?, fields? |
| `pexip_list_status` | List status resources | ✅ | ❌ | ✅ | resource, name_contains?, filters?, limit?, offset?, fetch_all?, response_format?, fields? |
| `pexip_list_vmrs` | List VMRs | ✅ | ❌ | ✅ | name?, name_contains?, tag?, limit?, offset?, response_format?, fields? |
| `pexip_lock_conference` | Lock a conference | ❌ | ✅ | ✅ | conference |
| `pexip_mute_guests` | Mute all guests in a conference | ❌ | ✅ | ✅ | conference |
| `pexip_mute_participant` | Audio-mute a participant | ❌ | ✅ | ✅ | participant, conference? |
| `pexip_run_platform_command` | Run a platform lifecycle command | ❌ | ✅ | ❌ | command, params? |
| `pexip_send_provisioning_email` | Send provisioning email | ❌ | ✅ | ❌ | target, target_id |
| `pexip_set_conference_layout` | Change a conference's layout | ❌ | ✅ | ✅ | conference, host_layout?, guest_layout? |
| `pexip_set_participant_role` | Set participant role (chair/guest) | ❌ | ✅ | ✅ | participant, role, conference? |
| `pexip_summarize_calls` | Summarize calls in a time window | ✅ | ❌ | ✅ | start_time, end_time, group_by?, conference_name?, service_tag?, call_direction?, location?, max_records? |
| `pexip_sync_conference_ldap` | Sync LDAP conference template | ❌ | ✅ | ❌ | template_id |
| `pexip_transfer_participant` | Transfer a participant | ❌ | ✅ | ❌ | participant, conference_alias, role?, pin? |
| `pexip_unlock_conference` | Unlock a conference | ❌ | ✅ | ✅ | conference |
| `pexip_unlock_participant` | Unlock a participant | ❌ | ✅ | ✅ | participant, conference? |
| `pexip_unmute_guests` | Unmute all guests in a conference | ❌ | ✅ | ✅ | conference |
| `pexip_unmute_participant` | Audio-unmute a participant | ❌ | ✅ | ✅ | participant, conference? |
| `pexip_update_device` | Update device | ❌ | ✅ | ✅ | device, alias?, username?, password?, description?, primary_owner_email_address?, enable_sip?, enable_h323?, enable_infinity_connect?, tag? |
| `pexip_update_end_user` | Update end user | ❌ | ✅ | ✅ | user, first_name?, last_name?, display_name?, telephone_number?, mobile_number?, title?, department?, avatar_url? |
| `pexip_update_gateway_rule` | Update gateway routing rule | ❌ | ✅ | ✅ | rule, name?, priority?, match_string?, replace_string?, called_device_type?, outgoing_protocol?, outgoing_location?, call_type?, crypto_mode?, enable?, description? |
| `pexip_update_resource` | Update configuration resource | ❌ | ✅ | ✅ | resource, id, settings |
| `pexip_update_vmr` | Update VMR | ❌ | ✅ | ✅ | vmr, name?, pin?, guest_pin?, allow_guests?, description?, tag?, host_view?, guest_view? |
