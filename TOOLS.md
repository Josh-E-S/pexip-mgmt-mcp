# Tool Catalog

Auto-generated reference of all 122 tools exposed by the pexip-mgmt-mcp server (46 Configuration, 39 Status, 14 History, 23 Command).

Regenerate with: `uv run python scripts/generate_tools_md.py`

| Tool | Title | Read-only | Destructive | Idempotent | Parameters |
|---|---|---|---|---|---|
| `pexip_add_automatic_participant` | Add automatic participant | ❌ | ✅ | ❌ | vmr, alias, protocol?, call_type?, role?, system_location?, dtmf_sequence?, streaming?, keep_conference_alive?, routing?, remote_display_name?, description? |
| `pexip_add_vmr_alias` | Add conference alias | ❌ | ✅ | ❌ | vmr, alias, description? |
| `pexip_backup_create` | Create platform backup | ❌ | ✅ | ❌ |  |
| `pexip_backup_restore` | Restore platform backup | ❌ | ✅ | ❌ | backup_id |
| `pexip_certificates_import` | Import certificates | ❌ | ✅ | ❌ | settings |
| `pexip_create_device` | Create device | ❌ | ✅ | ❌ | alias, username?, password?, description?, primary_owner_email_address?, enable_sip?, enable_h323?, enable_infinity_connect?, tag? |
| `pexip_create_end_user` | Create end user | ❌ | ✅ | ❌ | primary_email_address, first_name?, last_name?, display_name?, telephone_number?, mobile_number?, title?, department?, avatar_url? |
| `pexip_create_gateway_rule` | Create gateway routing rule | ❌ | ✅ | ❌ | name, priority, match_string, replace_string?, called_device_type?, outgoing_protocol?, outgoing_location?, call_type?, crypto_mode?, enable?, description? |
| `pexip_create_ldap_source` | Create LDAP sync source | ❌ | ✅ | ❌ | name, ldap_server, ldap_base_dn, bind_username?, bind_password?, ldap_user_filter?, ldap_user_search_dn?, ldap_user_search_filter?, ldap_permitted_users_regex?, sync_interval_minutes?, description? |
| `pexip_create_resource` | Create configuration resource | ❌ | ✅ | ❌ | resource, settings |
| `pexip_create_vmr` | Create VMR | ❌ | ✅ | ❌ | name, aliases?, pin?, guest_pin?, allow_guests?, description?, tag?, host_view?, guest_view?, allow_no_pin? |
| `pexip_delete_alias` | Delete conference alias | ❌ | ✅ | ✅ | alias_id |
| `pexip_delete_automatic_participant` | Delete automatic participant | ❌ | ✅ | ✅ | automatic_participant_id |
| `pexip_delete_device` | Delete device | ❌ | ✅ | ✅ | device |
| `pexip_delete_end_user` | Delete end user | ❌ | ✅ | ✅ | user |
| `pexip_delete_gateway_rule` | Delete gateway routing rule | ❌ | ✅ | ✅ | rule |
| `pexip_delete_ldap_source` | Delete LDAP sync source | ❌ | ✅ | ✅ | source |
| `pexip_delete_resource` | Delete configuration resource | ❌ | ✅ | ✅ | resource, id |
| `pexip_delete_vmr` | Delete VMR | ❌ | ✅ | ✅ | vmr |
| `pexip_dial_participant` | Dial out to add a participant | ❌ | ✅ | ❌ | conference_alias, destination, protocol?, call_type?, role?, system_location?, streaming?, remote_display_name?, dtmf_sequence? |
| `pexip_disconnect_conference` | End a conference (disconnect everyone) | ❌ | ✅ | ✅ | conference |
| `pexip_disconnect_participant` | Disconnect (kick) a participant | ❌ | ✅ | ✅ | participant, conference? |
| `pexip_get_active_participant` | Get active participant | ✅ | ❌ | ✅ | participant, conference? |
| `pexip_get_alarm_history` | Get historical alarm | ✅ | ❌ | ✅ | alarm_id |
| `pexip_get_backplane` | Get backplane | ✅ | ❌ | ✅ | backplane_id |
| `pexip_get_backplane_history` | Get backplane history | ✅ | ❌ | ✅ | backplane_id |
| `pexip_get_backplane_history_media_streams` | Get backplane history media streams | ✅ | ❌ | ✅ | backplane_id |
| `pexip_get_backplane_media_streams` | Get backplane media streams | ✅ | ❌ | ✅ | backplane_id |
| `pexip_get_cloud_monitored_location` | Get cloud monitored location | ✅ | ❌ | ✅ | location_id |
| `pexip_get_cloud_node` | Get cloud overflow node | ✅ | ❌ | ✅ | cloud_node_id |
| `pexip_get_cloud_overflow_location` | Get cloud overflow location | ✅ | ❌ | ✅ | location_id |
| `pexip_get_conference_shard` | Get conference shard | ✅ | ❌ | ✅ | shard_id |
| `pexip_get_conference_sync_status` | Get conference sync status | ✅ | ❌ | ✅ | sync_id |
| `pexip_get_conferencing_node` | Get conferencing node | ✅ | ❌ | ✅ | node |
| `pexip_get_device` | Get device | ✅ | ❌ | ✅ | device |
| `pexip_get_end_user` | Get end user | ✅ | ❌ | ✅ | user |
| `pexip_get_exchange_scheduler_status` | Get Exchange scheduler status | ✅ | ❌ | ✅ | scheduler_id |
| `pexip_get_gateway_rule` | Get gateway routing rule | ✅ | ❌ | ✅ | rule |
| `pexip_get_global_settings` | Get global platform settings | ✅ | ❌ | ✅ |  |
| `pexip_get_history_conference` | Get historical conference | ✅ | ❌ | ✅ | conference_id |
| `pexip_get_history_participant` | Get historical participant | ✅ | ❌ | ✅ | participant_id |
| `pexip_get_ivr_theme` | Get IVR theme | ✅ | ❌ | ✅ | theme |
| `pexip_get_ldap_source` | Get LDAP sync source | ✅ | ❌ | ✅ | source |
| `pexip_get_licensing_status` | Get licensing status | ✅ | ❌ | ✅ |  |
| `pexip_get_location` | Get system location | ✅ | ❌ | ✅ | location |
| `pexip_get_location_statistics` | Get location load statistics | ✅ | ❌ | ✅ | location |
| `pexip_get_location_status` | Get location status | ✅ | ❌ | ✅ | location |
| `pexip_get_management_node_status` | Get management node status | ✅ | ❌ | ✅ | node_id |
| `pexip_get_mjx_endpoint_status` | Get MJX endpoint status | ✅ | ❌ | ✅ | endpoint_id |
| `pexip_get_mjx_meeting_status` | Get MJX meeting status | ✅ | ❌ | ✅ | meeting_id |
| `pexip_get_node_event_history` | Get node event history | ✅ | ❌ | ✅ | event_id |
| `pexip_get_node_statistics` | Get node load statistics | ✅ | ❌ | ✅ | node |
| `pexip_get_node_status` | Get node status | ✅ | ❌ | ✅ | node |
| `pexip_get_participant_quality` | Get live participant quality | ✅ | ❌ | ✅ | participant, conference? |
| `pexip_get_registration_alias` | Get registered alias | ✅ | ❌ | ✅ | registration_alias_id |
| `pexip_get_registration_history` | Get registration history | ✅ | ❌ | ✅ | entry_id |
| `pexip_get_resource` | Get configuration resource | ✅ | ❌ | ✅ | resource, id |
| `pexip_get_resource_schema` | Get resource schema | ✅ | ❌ | ✅ | resource |
| `pexip_get_teams_node_call_status` | Get Teams Connector call status | ✅ | ❌ | ✅ | call_id |
| `pexip_get_teams_node_status` | Get Teams Connector node status | ✅ | ❌ | ✅ | teams_node_id |
| `pexip_get_vmr` | Get VMR | ✅ | ❌ | ✅ | vmr |
| `pexip_list_active_conferences` | List active conferences | ✅ | ❌ | ✅ | name?, service_type?, tag?, limit?, offset?, fetch_all?, response_format?, fields? |
| `pexip_list_active_participants` | List active participants | ✅ | ❌ | ✅ | conference_name?, role?, protocol?, is_muted?, limit?, offset?, fetch_all?, response_format?, fields? |
| `pexip_list_alarm_history` | List alarm history | ✅ | ❌ | ✅ | start_time?, end_time?, level?, limit?, offset?, fetch_all? |
| `pexip_list_alarms` | List active alarms | ✅ | ❌ | ✅ | level?, node_name?, limit?, offset?, fetch_all?, response_format?, fields? |
| `pexip_list_aliases` | List conference aliases | ✅ | ❌ | ✅ | vmr?, alias?, alias_contains?, limit?, offset?, response_format?, fields? |
| `pexip_list_automatic_participants` | List automatic participants | ✅ | ❌ | ✅ | vmr?, alias_contains?, limit?, offset?, response_format?, fields? |
| `pexip_list_backplane_history` | List backplane history | ✅ | ❌ | ✅ | limit?, offset?, fetch_all? |
| `pexip_list_backplanes` | List backplanes | ✅ | ❌ | ✅ | limit?, offset?, fetch_all? |
| `pexip_list_cloud_monitored_locations` | List cloud monitored locations | ✅ | ❌ | ✅ | limit?, offset?, fetch_all? |
| `pexip_list_cloud_nodes` | List cloud overflow nodes | ✅ | ❌ | ✅ | limit?, offset?, fetch_all? |
| `pexip_list_cloud_overflow_locations` | List cloud overflow locations | ✅ | ❌ | ✅ | limit?, offset?, fetch_all? |
| `pexip_list_conference_shards` | List conference shards | ✅ | ❌ | ✅ | conference_name?, limit?, offset?, fetch_all? |
| `pexip_list_conference_sync_status` | List conference sync status | ✅ | ❌ | ✅ | limit?, offset?, fetch_all? |
| `pexip_list_conferencing_nodes` | List conferencing nodes | ✅ | ❌ | ✅ | location?, name_contains?, node_type?, limit?, offset?, response_format?, fields? |
| `pexip_list_devices` | List devices | ✅ | ❌ | ✅ | alias_contains?, owner_email?, tag?, limit?, offset?, response_format?, fields? |
| `pexip_list_end_users` | List end users | ✅ | ❌ | ✅ | email_contains?, name_contains?, sync_tag?, limit?, offset?, response_format?, fields? |
| `pexip_list_exchange_scheduler_status` | List Exchange scheduler status | ✅ | ❌ | ✅ | limit?, offset?, fetch_all? |
| `pexip_list_gateway_rules` | List gateway routing rules | ✅ | ❌ | ✅ | name_contains?, enabled_only?, limit?, offset?, response_format?, fields? |
| `pexip_list_history_conferences` | List historical conferences | ✅ | ❌ | ✅ | start_time?, end_time?, name?, service_type?, tag?, limit?, offset?, fetch_all?, response_format?, fields? |
| `pexip_list_history_participants` | List historical participants | ✅ | ❌ | ✅ | start_time?, end_time?, conference_name?, call_direction?, call_quality?, protocol?, disconnect_reason?, location?, service_tag?, limit?, offset?, fetch_all?, response_format?, fields? |
| `pexip_list_ivr_themes` | List IVR themes | ✅ | ❌ | ✅ | name_contains?, limit?, offset? |
| `pexip_list_ldap_sources` | List LDAP sync sources | ✅ | ❌ | ✅ | name_contains?, limit?, offset?, response_format?, fields? |
| `pexip_list_location_status` | List location status | ✅ | ❌ | ✅ | name_contains?, limit?, offset?, fetch_all?, response_format?, fields? |
| `pexip_list_locations` | List system locations | ✅ | ❌ | ✅ | name_contains?, limit?, offset?, response_format?, fields? |
| `pexip_list_management_node_status` | List management node status | ✅ | ❌ | ✅ | limit?, offset? |
| `pexip_list_mjx_endpoint_status` | List MJX endpoint status | ✅ | ❌ | ✅ | name_contains?, limit?, offset?, fetch_all? |
| `pexip_list_mjx_meeting_status` | List MJX meeting status | ✅ | ❌ | ✅ | limit?, offset?, fetch_all? |
| `pexip_list_node_event_history` | List node event history | ✅ | ❌ | ✅ | start_time?, end_time?, limit?, offset?, fetch_all? |
| `pexip_list_node_status` | List node status | ✅ | ❌ | ✅ | location?, name_contains?, limit?, offset?, fetch_all?, response_format?, fields? |
| `pexip_list_registration_aliases` | List registered aliases | ✅ | ❌ | ✅ | alias_contains?, limit?, offset?, fetch_all?, response_format?, fields? |
| `pexip_list_registration_history` | List registration history | ✅ | ❌ | ✅ | alias_contains?, limit?, offset?, fetch_all? |
| `pexip_list_registrations` | List current registrations | ✅ | ❌ | ✅ | alias_contains?, protocol?, limit?, offset?, fetch_all?, response_format?, fields? |
| `pexip_list_resources` | List configuration resources | ✅ | ❌ | ✅ | resource, name_contains?, filters?, limit?, offset?, response_format?, fields? |
| `pexip_list_teams_node_call_status` | List Teams Connector call status | ✅ | ❌ | ✅ | limit?, offset?, fetch_all? |
| `pexip_list_teams_node_status` | List Teams Connector node status | ✅ | ❌ | ✅ | limit?, offset?, fetch_all? |
| `pexip_list_vmrs` | List VMRs | ✅ | ❌ | ✅ | name?, name_contains?, tag?, limit?, offset?, response_format?, fields? |
| `pexip_lock_conference` | Lock a conference | ❌ | ✅ | ✅ | conference |
| `pexip_mute_guests` | Mute all guests in a conference | ❌ | ✅ | ✅ | conference |
| `pexip_mute_participant` | Audio-mute a participant | ❌ | ✅ | ✅ | participant, conference? |
| `pexip_platform_upgrade` | Trigger platform upgrade | ❌ | ✅ | ❌ | settings? |
| `pexip_send_conference_email` | Send VMR provisioning email | ❌ | ✅ | ❌ | vmr_id |
| `pexip_send_device_email` | Send device provisioning email | ❌ | ✅ | ❌ | vmr_id |
| `pexip_set_conference_layout` | Change a conference's layout | ❌ | ✅ | ✅ | conference, host_layout?, guest_layout? |
| `pexip_set_participant_role` | Set participant role (chair/guest) | ❌ | ✅ | ✅ | participant, role, conference? |
| `pexip_start_cloud_node` | Start cloud overflow node | ❌ | ✅ | ❌ | settings? |
| `pexip_summarize_calls` | Summarize calls in a time window | ✅ | ❌ | ✅ | start_time, end_time, group_by?, conference_name?, service_tag?, call_direction?, location?, max_records? |
| `pexip_sync_conference_ldap` | Sync LDAP conference template | ❌ | ✅ | ❌ | template_id |
| `pexip_take_snapshot` | Take system snapshot | ❌ | ✅ | ❌ |  |
| `pexip_transfer_participant` | Transfer a participant | ❌ | ✅ | ❌ | participant, conference_alias, role?, pin? |
| `pexip_unlock_conference` | Unlock a conference | ❌ | ✅ | ✅ | conference |
| `pexip_unlock_participant` | Unlock a participant | ❌ | ✅ | ✅ | participant, conference? |
| `pexip_unmute_guests` | Unmute all guests in a conference | ❌ | ✅ | ✅ | conference |
| `pexip_unmute_participant` | Audio-unmute a participant | ❌ | ✅ | ✅ | participant, conference? |
| `pexip_update_device` | Update device | ❌ | ✅ | ✅ | device, alias?, username?, password?, description?, primary_owner_email_address?, enable_sip?, enable_h323?, enable_infinity_connect?, tag? |
| `pexip_update_end_user` | Update end user | ❌ | ✅ | ✅ | user, first_name?, last_name?, display_name?, telephone_number?, mobile_number?, title?, department?, avatar_url? |
| `pexip_update_gateway_rule` | Update gateway routing rule | ❌ | ✅ | ✅ | rule, name?, priority?, match_string?, replace_string?, called_device_type?, outgoing_protocol?, outgoing_location?, call_type?, crypto_mode?, enable?, description? |
| `pexip_update_global_settings` | Update global platform settings | ❌ | ✅ | ✅ | updates |
| `pexip_update_ldap_source` | Update LDAP sync source | ❌ | ✅ | ✅ | source, name?, ldap_server?, ldap_base_dn?, bind_username?, bind_password?, ldap_user_filter?, ldap_user_search_dn?, ldap_user_search_filter?, ldap_permitted_users_regex?, sync_interval_minutes?, description? |
| `pexip_update_resource` | Update configuration resource | ❌ | ✅ | ✅ | resource, id, settings |
| `pexip_update_vmr` | Update VMR | ❌ | ✅ | ✅ | vmr, name?, pin?, guest_pin?, allow_guests?, description?, tag?, host_view?, guest_view? |
| `pexip_upload_software_bundle` | Upload software bundle | ❌ | ✅ | ❌ | settings |
