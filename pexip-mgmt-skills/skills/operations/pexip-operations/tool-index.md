# Tool index — grouped by intent

A curated, intent-grouped lookup for the pexip-mgmt MCP server's tools: find the right tool when you know WHAT you want to do but not its name. For the authoritative, always-current catalog of **all 122 tools** (auto-generated from the server), see the [`TOOLS.md`](https://github.com/josh-e-s/pexip-mgmt-mcp/blob/main/TOOLS.md) in the server repo.

## Live meeting state (Status API — read)

| Tool | Description |
|---|---|
| `list_active_conferences` | Currently-running conference instances. Filter by `name`, `service_type`, `tag`. |
| `list_active_participants` | Currently-connected participants. Filter by `conference_name`, `role`, `protocol`, `is_muted`. |
| `get_active_participant` | One active participant by UUID. |
| `list_node_status` | Live load + sync state for each Conferencing Node. |
| `get_node_status` | One Conferencing Node's live status. |
| `list_alarms` | Active platform alarms. Filter by `level`, `node_name`. |
| `get_licensing_status` | Concurrent port usage vs entitlement, per location. |
| `get_participant_quality` | Live call quality + per-stream stats for one participant. |

## Live meeting control (Command API — write)

| Tool | Idempotent? | Description |
|---|---|---|
| `dial_participant` | NO | Place an outbound call to add a participant to a running conference. |
| `disconnect_participant` | yes | Kick one participant (404 → already gone). |
| `mute_participant` / `unmute_participant` | yes | Audio mute one participant. |
| `video_mute_participant` / `video_unmute_participant` | yes | Video mute one participant. |
| `set_participant_role` | yes | Change role to `chair` or `guest`. |
| `spotlight_participant` / `unspotlight_participant` | yes | Pin a participant in the layout. |
| `transfer_participant` | NO | Move a participant to another conference. |
| `disconnect_conference` | yes | End a meeting (disconnect everyone). DESTRUCTIVE. |
| `lock_conference` / `unlock_conference` | yes | Lock new joiners out. |
| `mute_guests` / `unmute_guests` | yes | Audio mute every participant with role=guest. |
| `set_conference_layout` | yes | Change active layout. See `layouts.json` (sibling of `SKILL.md`). |
| `send_conference_message` | NO | Display a text/banner message to everyone in a conference. |
| `send_participant_message` | NO | Display a text message to one participant. |

## Post-call (History API — read)

| Tool | Description |
|---|---|
| `list_history_conferences` | Completed conference instances in a time window. |
| `get_history_conference` | One past conference instance. |
| `list_history_participants` | Completed participant legs (CDRs). |
| `get_history_participant` | One past participant — includes `bucketed_call_quality` + `historic_call_quality`. |
| `summarize_calls` | Aggregate counts + duration in a time window, grouped by direction/quality/protocol/etc. **Prefer this for reporting.** |

## VMR / conference configuration

| Tool | Description |
|---|---|
| `list_vmrs` / `get_vmr` / `create_vmr` / `update_vmr` / `delete_vmr` | CRUD on Virtual Meeting Rooms. Name-or-id everywhere. |
| `list_aliases` / `add_vmr_alias` / `delete_alias` | Manage dial strings on a VMR. |
| `list_automatic_participants` / `add_automatic_participant` / `delete_automatic_participant` | Auto-dial entries (recorder, streamer) per VMR. |

## Directory

| Tool | Description |
|---|---|
| `list_end_users` / `get_end_user` / `create_end_user` / `update_end_user` / `delete_end_user` | Directory CRUD. Handle is `primary_email_address`. |
| `list_ldap_sources` / `get_ldap_source` / `create_ldap_source` / `update_ldap_source` / `delete_ldap_source` | LDAP / AD sync sources. `get_ldap_source` returns last sync status. |

## Devices & registrations

| Tool | Description |
|---|---|
| `list_devices` / `get_device` / `create_device` / `update_device` / `delete_device` | CRUD on provisioned registration records (alias + creds + protocol flags). Name-or-id by `alias`. |
| `list_registrations` | Live Status-API read of endpoints registered *right now* (alias, node, protocol). |

## Dial plan & policy

| Tool | Description |
|---|---|
| `list_gateway_rules` / `get_gateway_rule` / `create_gateway_rule` / `update_gateway_rule` / `delete_gateway_rule` | Outbound dial-plan rules, evaluated in ascending `priority`. |
| `list_policy_profiles` / `get_policy_profile` / `create_policy_profile` / `update_policy_profile` / `delete_policy_profile` | External + local (Jinja2) policy profiles. `settings` is a dict — discover fields with `get_resource_schema('policy_profile')`. |

## Infrastructure (read-only)

| Tool | Description |
|---|---|
| `list_locations` / `get_location` | System locations (datacenter / region groupings of nodes). |
| `list_conferencing_nodes` / `get_conferencing_node` | Conferencing Node configuration (the `worker_vm` resource). |
| `list_ivr_themes` / `get_ivr_theme` | Branding bundles assignable to VMRs. |

## MJX — One-Touch Join

| Tool | Description |
|---|---|
| `list_mjx_integrations` / `get_mjx_integration` / `create_mjx_integration` / `update_mjx_integration` / `delete_mjx_integration` | OTJ profiles (calendar source + settings). |
| `list_mjx_endpoints` / `get_mjx_endpoint` / `create_mjx_endpoint` / `update_mjx_endpoint` / `delete_mjx_endpoint` | Room video system CRUD (Cisco CE, Poly OBTP, Logitech Tap, etc.). |
| `list_mjx_endpoint_groups` / `get_mjx_endpoint_group` / `create_mjx_endpoint_group` / `update_mjx_endpoint_group` / `delete_mjx_endpoint_group` | Logical groups of endpoints. |
| `list_mjx_meeting_processing_rules` / ... / `delete_mjx_meeting_processing_rule` | Regex/transform rules for detecting meeting URLs in invite bodies. |
| `list_mjx_exchange_deployments` / ... / `delete_mjx_exchange_deployment` | Exchange on-prem integrations. |
| `list_mjx_exchange_autodiscover_urls` / ... / `delete_mjx_exchange_autodiscover_url` | Exchange autodiscover URL entries. |
| `list_mjx_graph_deployments` / ... / `delete_mjx_graph_deployment` | Office 365 Graph integrations. |
| `list_mjx_google_deployments` / ... / `delete_mjx_google_deployment` | Google Workspace integrations. |

## Call routing & signaling infrastructure

| Tool | Description |
|---|---|
| `list_sip_proxies` / ... / `delete_sip_proxy` | SIP proxy CRUD. |
| `list_sip_credentials` / ... / `delete_sip_credential` | SIP credential CRUD. |
| `list_mssip_proxies` / ... / `delete_mssip_proxy` | Microsoft SIP proxy CRUD. |
| `list_h323_gatekeepers` / ... / `delete_h323_gatekeeper` | H.323 gatekeeper CRUD. |
| `list_turn_servers` / ... / `delete_turn_server` | TURN server CRUD. |
| `list_stun_servers` / ... / `delete_stun_server` | STUN server CRUD. |
| `list_gms_access_tokens` / ... / `delete_gms_access_token` | Google Meet access tokens. |
| `list_gms_gateway_tokens` / ... / `delete_gms_gateway_token` | Google Meet gateway tokens. |
| `list_azure_tenants` / ... / `delete_azure_tenant` | Microsoft Azure tenants (Teams CVI). |
| `list_teams_proxies` / ... / `delete_teams_proxy` | Microsoft Teams Connectors. |
| `list_policy_servers` / ... / `delete_policy_server` | External policy servers. |
| `list_break_in_allow_list_addresses` / ... / `delete_break_in_allow_list_address` | Break-in resistance allow list. |
| `list_telehealth_profiles` / ... / `delete_telehealth_profile` | Epic telehealth profiles. |

## Web app configuration

| Tool | Description |
|---|---|
| `list_webapp_aliases` / ... / `delete_webapp_alias` | Web app path aliases. |
| `list_webapp_brandings` / ... / `delete_webapp_branding` | Web app branding packages. |
| `list_external_webapp_hosts` / ... / `delete_external_webapp_host` | External web app hosts. |

## System infrastructure

| Tool | Description |
|---|---|
| `list_dns_servers` / ... / `delete_dns_server` | DNS servers. |
| `list_ntp_servers` / ... / `delete_ntp_server` | NTP servers. |
| `list_http_proxies` / ... / `delete_http_proxy` | Web proxy servers. |
| `list_syslog_servers` / ... / `delete_syslog_server` | Syslog servers. |
| `list_snmp_network_management_systems` / ... / `delete_snmp_network_management_system` | SNMP NMS. |
| `list_smtp_servers` / ... / `delete_smtp_server` | SMTP servers. |
| `list_static_routes` / ... / `delete_static_route` | Static routes. |
| `list_ssh_authorized_keys` / ... / `delete_ssh_authorized_key` | SSH authorized keys. |

## Admin authentication & authorization

| Tool | Description |
|---|---|
| `list_authentications` / ... / `delete_authentication` | Authentication settings. |
| `list_roles` / ... / `delete_role` | Account roles. |
| `list_ldap_roles` / ... / `delete_ldap_role` | LDAP roles. |
| `list_permissions` / ... / `delete_permission` | Permissions. |
| `list_adfs_auth_servers` / ... / `delete_adfs_auth_server` | AD FS servers. |
| `list_adfs_auth_server_domains` / ... / `delete_adfs_auth_server_domain` | AD FS domains. |
| `list_identity_providers` / ... / `delete_identity_provider` | Identity providers. |
| `list_identity_provider_groups` / ... / `delete_identity_provider_group` | Identity provider groups. |
| `list_user_groups` / ... / `delete_user_group` | User groups. |
| `list_user_group_entity_mappings` / ... / `delete_user_group_entity_mapping` | User group entity mappings. |

## Platform infrastructure

| Tool | Description |
|---|---|
| `list_management_vms` / ... / `delete_management_vm` | Management Nodes. |
| `list_licences` / ... / `delete_licence` | Licensing. |
| `list_licence_requests` / ... / `delete_licence_request` | License requests. |
| `list_media_processing_servers` / ... / `delete_media_processing_server` | Media processing servers. |
| `list_diagnostic_graphs` / ... / `delete_diagnostic_graphs` | Diagnostic graphs. |
| `list_ca_certificates` / ... / `delete_ca_certificate` | CA certificates. |
| `list_tls_certificates` / ... / `delete_tls_certificate` | TLS certificates. |
| `list_certificate_signing_requests` / ... / `delete_certificate_signing_request` | Certificate signing requests (CSRs). |

## Service configuration (additional)

| Tool | Description |
|---|---|
| `list_registration_settings` / ... / `delete_registration` | Global registration settings. |
| `list_conference_sync_templates` / ... / `delete_conference_sync_template` | Conference sync templates. |
| `list_ldap_sync_fields` / ... / `delete_ldap_sync_field` | LDAP sync field mappings. |
| `list_ms_exchange_connectors` / ... / `delete_ms_exchange_connector` | Exchange servers (caution: prefer Secure Scheduler). |
| `list_exchange_domains` / ... / `delete_exchange_domain` | Exchange domains (caution: prefer Secure Scheduler). |
| `list_recurring_conferences` / ... / `delete_recurring_conference` | Recurring conferences (caution: prefer UI/Scheduler). |
| `list_scheduled_conferences` / ... / `delete_scheduled_conference` | Scheduled conferences (caution: prefer UI/Scheduler). |
| `list_scheduled_aliases` / ... / `delete_scheduled_alias` | Scheduled conference aliases (caution: prefer UI/Scheduler). |
| `list_media_library_entries` / ... / `delete_media_library_entry` | Media playback library entries. |
| `list_media_library_playlists` / ... / `delete_media_library_playlist` | Media playback playlists. |
| `list_media_library_playlist_entries` / ... / `delete_media_library_playlist_entry` | Playlist entries. |

## Upgrades, backups & scaling

| Tool | Description |
|---|---|
| `list_upgrades` / ... / `delete_upgrade` | Upgrade management. |
| `list_software_bundles` / ... / `delete_software_bundle` | Software bundles. |
| `list_software_bundle_revisions` / ... / `delete_software_bundle_revision` | Software bundle revisions. |
| `list_system_backups` / ... / `delete_system_backup` | System backups. |
| `list_autobackups` / ... / `delete_autobackup` | Automatic backup configuration. |
| `list_scheduled_scalings` / ... / `delete_scheduled_scaling` | Teams scheduled scaling. |

## Platform-wide

| Tool | Description |
|---|---|
| `get_global_settings` / `update_global_settings` | Singleton at `/configuration/v1/global/1/`. Affects the whole platform. |
| `get_resource_schema(resource=…)` | Fetch the live JSON schema for any resource. Use before guessing field names or enum values. |

## Not exposed

- DTMF injection (`participant/dtmf`) and text overlay (`participant/set_text_overlay`) — inject content into live calls.
- Platform commands (`update_software`, `restart_conferencing_node`, `cloud_node_create` / `_delete`).
- Backplane media stats (`/status/backplane/`), connectivity matrix.

If a user asks for one of these, surface that the MCP server doesn't expose it and point them at either the Pexip admin UI or extending the server.
