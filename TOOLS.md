# Tool Catalog

Auto-generated reference of all 122 tools exposed by the pexip-mgmt-mcp server (46 Configuration, 39 Status, 14 History, 23 Command).

Regenerate with: `uv run python scripts/generate_tools_md.py`

| Tool | Title | Read-only | Destructive | Idempotent | Parameters |
|---|---|---|---|---|---|
| `add_automatic_participant` | Add automatic participant | ❌ | ❌ | ❌ | vmr, alias, protocol?, call_type?, role?, system_location?, dtmf_sequence?, streaming?, keep_conference_alive?, routing?, remote_display_name?, description? |
| `add_vmr_alias` | Add conference alias | ❌ | ❌ | ❌ | vmr, alias, description? |
| `backup_create` | Create platform backup | ❌ | ✅ | ❌ |  |
| `backup_restore` | Restore platform backup | ❌ | ✅ | ❌ | backup_id |
| `certificates_import` | Import certificates | ❌ | ✅ | ❌ | settings |
| `create_device` | Create device | ❌ | ❌ | ❌ | alias, username?, password?, description?, primary_owner_email_address?, enable_sip?, enable_h323?, enable_infinity_connect?, tag? |
| `create_end_user` | Create end user | ❌ | ❌ | ❌ | primary_email_address, first_name?, last_name?, display_name?, telephone_number?, mobile_number?, title?, department?, avatar_url? |
| `create_gateway_rule` | Create gateway routing rule | ❌ | ❌ | ❌ | name, priority, match_string, replace_string?, called_device_type?, outgoing_protocol?, outgoing_location?, call_type?, crypto_mode?, enable?, description? |
| `create_ldap_source` | Create LDAP sync source | ❌ | ❌ | ❌ | name, ldap_server, ldap_base_dn, bind_username?, bind_password?, ldap_user_filter?, ldap_user_search_dn?, ldap_user_search_filter?, ldap_permitted_users_regex?, sync_interval_minutes?, description? |
| `create_resource` | Create configuration resource | ❌ | ❌ | ❌ | resource, settings |
| `create_vmr` | Create VMR | ❌ | ❌ | ❌ | name, aliases?, pin?, guest_pin?, allow_guests?, description?, tag?, host_view?, guest_view?, allow_no_pin? |
| `delete_alias` | Delete conference alias | ❌ | ✅ | ✅ | alias_id |
| `delete_automatic_participant` | Delete automatic participant | ❌ | ✅ | ✅ | participant_id |
| `delete_device` | Delete device | ❌ | ✅ | ✅ | device |
| `delete_end_user` | Delete end user | ❌ | ✅ | ✅ | user |
| `delete_gateway_rule` | Delete gateway routing rule | ❌ | ✅ | ✅ | rule |
| `delete_ldap_source` | Delete LDAP sync source | ❌ | ✅ | ✅ | source |
| `delete_resource` | Delete configuration resource | ❌ | ✅ | ✅ | resource, id |
| `delete_vmr` | Delete VMR | ❌ | ✅ | ✅ | vmr |
| `dial_participant` | Dial out to add a participant | ❌ | ✅ | ❌ | conference_alias, destination, protocol?, call_type?, role?, system_location?, streaming?, remote_display_name?, dtmf_sequence? |
| `disconnect_conference` | End a conference (disconnect everyone) | ❌ | ✅ | ✅ | conference_id |
| `disconnect_participant` | Disconnect (kick) a participant | ❌ | ✅ | ✅ | participant_id, conference? |
| `get_active_participant` | Get active participant | ✅ | ❌ | ✅ | participant_id, conference? |
| `get_alarm_history` | Get historical alarm | ✅ | ❌ | ✅ | alarm_id |
| `get_backplane` | Get backplane | ✅ | ❌ | ✅ | backplane_id |
| `get_backplane_history` | Get backplane history | ✅ | ❌ | ✅ | backplane_id |
| `get_backplane_history_media_streams` | Get backplane history media streams | ✅ | ❌ | ✅ | backplane_id |
| `get_backplane_media_streams` | Get backplane media streams | ✅ | ❌ | ✅ | backplane_id |
| `get_cloud_monitored_location` | Get cloud monitored location | ✅ | ❌ | ✅ | location_id |
| `get_cloud_node` | Get cloud overflow node | ✅ | ❌ | ✅ | node_id |
| `get_cloud_overflow_location` | Get cloud overflow location | ✅ | ❌ | ✅ | location_id |
| `get_conference_shard` | Get conference shard | ✅ | ❌ | ✅ | shard_id |
| `get_conference_sync_status` | Get conference sync status | ✅ | ❌ | ✅ | sync_id |
| `get_conferencing_node` | Get conferencing node | ✅ | ❌ | ✅ | node |
| `get_device` | Get device | ✅ | ❌ | ✅ | device |
| `get_end_user` | Get end user | ✅ | ❌ | ✅ | user |
| `get_exchange_scheduler_status` | Get Exchange scheduler status | ✅ | ❌ | ✅ | scheduler_id |
| `get_gateway_rule` | Get gateway routing rule | ✅ | ❌ | ✅ | rule |
| `get_global_settings` | Get global platform settings | ✅ | ❌ | ✅ |  |
| `get_history_conference` | Get historical conference | ✅ | ❌ | ✅ | conference_id |
| `get_history_participant` | Get historical participant | ✅ | ❌ | ✅ | participant_id |
| `get_ivr_theme` | Get IVR theme | ✅ | ❌ | ✅ | theme |
| `get_ldap_source` | Get LDAP sync source | ✅ | ❌ | ✅ | source |
| `get_licensing_status` | Get licensing status | ✅ | ❌ | ✅ |  |
| `get_location` | Get system location | ✅ | ❌ | ✅ | location |
| `get_location_statistics` | Get location load statistics | ✅ | ❌ | ✅ | location |
| `get_location_status` | Get location status | ✅ | ❌ | ✅ | location |
| `get_management_node_status` | Get management node status | ✅ | ❌ | ✅ | node_id |
| `get_mjx_endpoint_status` | Get MJX endpoint status | ✅ | ❌ | ✅ | endpoint_id |
| `get_mjx_meeting_status` | Get MJX meeting status | ✅ | ❌ | ✅ | meeting_id |
| `get_node_event_history` | Get node event history | ✅ | ❌ | ✅ | event_id |
| `get_node_statistics` | Get node load statistics | ✅ | ❌ | ✅ | node |
| `get_node_status` | Get node status | ✅ | ❌ | ✅ | node |
| `get_participant_quality` | Get live participant quality | ✅ | ❌ | ✅ | participant_id, conference? |
| `get_registration_alias` | Get registered alias | ✅ | ❌ | ✅ | alias_id |
| `get_registration_history` | Get registration history | ✅ | ❌ | ✅ | entry_id |
| `get_resource` | Get configuration resource | ✅ | ❌ | ✅ | resource, id |
| `get_resource_schema` | Get resource schema | ✅ | ❌ | ✅ | resource |
| `get_teams_node_call_status` | Get Teams Connector call status | ✅ | ❌ | ✅ | call_id |
| `get_teams_node_status` | Get Teams Connector node status | ✅ | ❌ | ✅ | node_id |
| `get_vmr` | Get VMR | ✅ | ❌ | ✅ | vmr |
| `list_active_conferences` | List active conferences | ✅ | ❌ | ✅ | name?, service_type?, tag?, limit?, offset?, fetch_all? |
| `list_active_participants` | List active participants | ✅ | ❌ | ✅ | conference_name?, role?, protocol?, is_muted?, limit?, offset?, fetch_all? |
| `list_alarm_history` | List alarm history | ✅ | ❌ | ✅ | start_time?, end_time?, level?, limit?, offset?, fetch_all? |
| `list_alarms` | List active alarms | ✅ | ❌ | ✅ | level?, node_name?, limit?, offset?, fetch_all? |
| `list_aliases` | List conference aliases | ✅ | ❌ | ✅ | vmr?, alias?, alias_contains?, limit?, offset? |
| `list_automatic_participants` | List automatic participants | ✅ | ❌ | ✅ | vmr?, alias_contains?, limit?, offset? |
| `list_backplane_history` | List backplane history | ✅ | ❌ | ✅ | limit?, offset?, fetch_all? |
| `list_backplanes` | List backplanes | ✅ | ❌ | ✅ | limit?, offset?, fetch_all? |
| `list_cloud_monitored_locations` | List cloud monitored locations | ✅ | ❌ | ✅ | limit?, offset?, fetch_all? |
| `list_cloud_nodes` | List cloud overflow nodes | ✅ | ❌ | ✅ | limit?, offset?, fetch_all? |
| `list_cloud_overflow_locations` | List cloud overflow locations | ✅ | ❌ | ✅ | limit?, offset?, fetch_all? |
| `list_conference_shards` | List conference shards | ✅ | ❌ | ✅ | conference_name?, limit?, offset?, fetch_all? |
| `list_conference_sync_status` | List conference sync status | ✅ | ❌ | ✅ | limit?, offset?, fetch_all? |
| `list_conferencing_nodes` | List conferencing nodes | ✅ | ❌ | ✅ | location?, name_contains?, node_type?, limit?, offset? |
| `list_devices` | List devices | ✅ | ❌ | ✅ | alias_contains?, owner_email?, tag?, limit?, offset? |
| `list_end_users` | List end users | ✅ | ❌ | ✅ | email_contains?, name_contains?, sync_tag?, limit?, offset? |
| `list_exchange_scheduler_status` | List Exchange scheduler status | ✅ | ❌ | ✅ | limit?, offset?, fetch_all? |
| `list_gateway_rules` | List gateway routing rules | ✅ | ❌ | ✅ | name_contains?, enabled_only?, limit?, offset? |
| `list_history_conferences` | List historical conferences | ✅ | ❌ | ✅ | start_time?, end_time?, name?, service_type?, tag?, limit?, offset?, fetch_all? |
| `list_history_participants` | List historical participants | ✅ | ❌ | ✅ | start_time?, end_time?, conference_name?, call_direction?, call_quality?, protocol?, disconnect_reason?, location?, service_tag?, limit?, offset?, fetch_all? |
| `list_ivr_themes` | List IVR themes | ✅ | ❌ | ✅ | name_contains?, limit?, offset? |
| `list_ldap_sources` | List LDAP sync sources | ✅ | ❌ | ✅ | name_contains?, limit?, offset? |
| `list_location_status` | List location status | ✅ | ❌ | ✅ | name_contains?, limit?, offset?, fetch_all? |
| `list_locations` | List system locations | ✅ | ❌ | ✅ | name_contains?, limit?, offset? |
| `list_management_node_status` | List management node status | ✅ | ❌ | ✅ | limit?, offset? |
| `list_mjx_endpoint_status` | List MJX endpoint status | ✅ | ❌ | ✅ | name_contains?, limit?, offset?, fetch_all? |
| `list_mjx_meeting_status` | List MJX meeting status | ✅ | ❌ | ✅ | limit?, offset?, fetch_all? |
| `list_node_event_history` | List node event history | ✅ | ❌ | ✅ | start_time?, end_time?, limit?, offset?, fetch_all? |
| `list_node_status` | List node status | ✅ | ❌ | ✅ | location?, name_contains?, limit?, offset?, fetch_all? |
| `list_registration_aliases` | List registered aliases | ✅ | ❌ | ✅ | alias_contains?, limit?, offset?, fetch_all? |
| `list_registration_history` | List registration history | ✅ | ❌ | ✅ | alias_contains?, limit?, offset?, fetch_all? |
| `list_registrations` | List current registrations | ✅ | ❌ | ✅ | alias_contains?, protocol?, limit?, offset?, fetch_all? |
| `list_resources` | List configuration resources | ✅ | ❌ | ✅ | resource, name_contains?, filters?, limit?, offset? |
| `list_teams_node_call_status` | List Teams Connector call status | ✅ | ❌ | ✅ | limit?, offset?, fetch_all? |
| `list_teams_node_status` | List Teams Connector node status | ✅ | ❌ | ✅ | limit?, offset?, fetch_all? |
| `list_vmrs` | List VMRs | ✅ | ❌ | ✅ | name?, name_contains?, tag?, limit?, offset? |
| `lock_conference` | Lock a conference | ❌ | ✅ | ✅ | conference_id |
| `mute_guests` | Mute all guests in a conference | ❌ | ✅ | ✅ | conference_id |
| `mute_participant` | Audio-mute a participant | ❌ | ✅ | ✅ | participant_id, conference? |
| `platform_upgrade` | Trigger platform upgrade | ❌ | ✅ | ❌ | settings? |
| `send_conference_email` | Send VMR provisioning email | ❌ | ✅ | ❌ | conference_id |
| `send_device_email` | Send device provisioning email | ❌ | ✅ | ❌ | conference_id |
| `set_conference_layout` | Change a conference's layout | ❌ | ✅ | ✅ | conference_id, host_layout?, guest_layout? |
| `set_participant_role` | Set participant role (chair/guest) | ❌ | ✅ | ✅ | participant_id, role, conference? |
| `start_cloud_node` | Start cloud overflow node | ❌ | ✅ | ❌ | settings? |
| `summarize_calls` | Summarize calls in a time window | ✅ | ❌ | ✅ | start_time, end_time, group_by?, conference_name?, service_tag?, call_direction?, location?, max_records? |
| `sync_conference_ldap` | Sync LDAP conference template | ❌ | ✅ | ❌ | conference_id |
| `take_snapshot` | Take system snapshot | ❌ | ✅ | ❌ |  |
| `transfer_participant` | Transfer a participant | ❌ | ✅ | ❌ | participant_id, conference_alias, role?, pin? |
| `unlock_conference` | Unlock a conference | ❌ | ✅ | ✅ | conference_id |
| `unlock_participant` | Unlock a participant | ❌ | ✅ | ✅ | participant_id, conference? |
| `unmute_guests` | Unmute all guests in a conference | ❌ | ✅ | ✅ | conference_id |
| `unmute_participant` | Audio-unmute a participant | ❌ | ✅ | ✅ | participant_id, conference? |
| `update_device` | Update device | ❌ | ✅ | ✅ | device, alias?, username?, password?, description?, primary_owner_email_address?, enable_sip?, enable_h323?, enable_infinity_connect?, tag? |
| `update_end_user` | Update end user | ❌ | ✅ | ✅ | user, first_name?, last_name?, display_name?, telephone_number?, mobile_number?, title?, department?, avatar_url? |
| `update_gateway_rule` | Update gateway routing rule | ❌ | ✅ | ✅ | rule, name?, priority?, match_string?, replace_string?, called_device_type?, outgoing_protocol?, outgoing_location?, call_type?, crypto_mode?, enable?, description? |
| `update_global_settings` | Update global platform settings | ❌ | ✅ | ✅ | updates |
| `update_ldap_source` | Update LDAP sync source | ❌ | ✅ | ✅ | source, name?, ldap_server?, ldap_base_dn?, bind_username?, bind_password?, ldap_user_filter?, ldap_user_search_dn?, ldap_user_search_filter?, ldap_permitted_users_regex?, sync_interval_minutes?, description? |
| `update_resource` | Update configuration resource | ❌ | ✅ | ✅ | resource, id, settings |
| `update_vmr` | Update VMR | ❌ | ✅ | ✅ | vmr, name?, pin?, guest_pin?, allow_guests?, description?, tag?, host_view?, guest_view? |
| `upload_software_bundle` | Upload software bundle | ❌ | ✅ | ❌ | settings |
