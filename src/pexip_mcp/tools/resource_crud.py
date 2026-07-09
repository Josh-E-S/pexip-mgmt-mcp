"""Generic CRUD tools for any Pexip configuration resource.

Replaces ~340 boilerplate tools (list/get/create/update/delete × 60+ resources)
with 5 generic tools plus a resource registry. The LLM calls
``get_resource_schema(resource)`` to discover fields before create/update.

Resources with custom typed parameters (VMRs, devices, gateway rules, etc.)
keep their own dedicated tools — this module covers everything that previously
used a generic ``settings: dict`` parameter.
"""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context

from pexip_mcp.client import PexipError, extract_id_from_uri
from pexip_mcp.mcp_app import mcp
from pexip_mcp.tools._helpers import (
    create,
    delete,
    get_client,
    read,
    redact_secrets,
    resolve_id_by_field,
    security_resources_allowed,
    update,
)


RESOURCE_REGISTRY: dict[str, dict[str, str]] = {
    # ── Admin auth & authorization ──
    "authentication": {"label": "authentication settings", "lookup_field": "name"},
    "role": {"label": "admin role", "lookup_field": "name"},
    "ldap_role": {"label": "LDAP role", "lookup_field": "name"},
    "permission": {"label": "permission", "lookup_field": "name"},
    "adfs_auth_server": {"label": "AD FS server", "lookup_field": "name"},
    "adfs_auth_server_domain": {"label": "AD FS domain", "lookup_field": "name"},
    "identity_provider": {"label": "identity provider", "lookup_field": "name"},
    "identity_provider_group": {"label": "identity provider group", "lookup_field": "name"},
    "user_group": {"label": "user group", "lookup_field": "name"},
    "user_group_entity_mapping": {"label": "user group entity mapping", "lookup_field": "name"},
    # ── Call routing & signaling ──
    "gms_access_token": {"label": "Google Meet access token", "lookup_field": "name"},
    "gms_gateway_token": {"label": "Google Meet gateway token", "lookup_field": "name"},
    "azure_tenant": {"label": "Azure tenant (Teams CVI)", "lookup_field": "name"},
    "teams_proxy": {"label": "Teams Connector", "lookup_field": "name"},
    "sip_proxy": {"label": "SIP proxy", "lookup_field": "name"},
    "sip_credential": {"label": "SIP credential", "lookup_field": "name"},
    "mssip_proxy": {"label": "MS-SIP proxy", "lookup_field": "name"},
    "h323_gatekeeper": {"label": "H.323 gatekeeper", "lookup_field": "name"},
    "turn_server": {"label": "TURN server", "lookup_field": "name"},
    "stun_server": {"label": "STUN server", "lookup_field": "name"},
    "break_in_allow_list_address": {"label": "break-in allow list address", "lookup_field": "name"},
    "telehealth_profile": {"label": "telehealth profile (Epic)", "lookup_field": "name"},
    "policy_server": {"label": "external policy server", "lookup_field": "name"},
    # ── Service configuration ──
    "registration": {"label": "registration settings", "lookup_field": "name"},
    "conference_sync_template": {"label": "conference sync template", "lookup_field": "name"},
    "ldap_sync_field": {"label": "LDAP sync field mapping", "lookup_field": "name"},
    "ms_exchange_connector": {"label": "Exchange connector", "lookup_field": "name"},
    "exchange_domain": {"label": "Exchange domain", "lookup_field": "name"},
    "scheduled_conference": {"label": "scheduled conference", "lookup_field": "name"},
    "scheduled_alias": {"label": "scheduled alias", "lookup_field": "name"},
    "recurring_conference": {"label": "recurring conference", "lookup_field": "name"},
    "media_library_entry": {"label": "media library entry", "lookup_field": "name"},
    "media_library_playlist": {"label": "media library playlist", "lookup_field": "name"},
    "media_library_playlist_entry": {"label": "media library playlist entry", "lookup_field": "name"},
    # ── Platform infrastructure ──
    "management_vm": {"label": "Management Node", "lookup_field": "name"},
    "licence": {"label": "licence", "lookup_field": "name"},
    "licence_request": {"label": "licence request", "lookup_field": "name"},
    "media_processing_server": {"label": "media processing server", "lookup_field": "name"},
    "diagnostic_graphs": {"label": "diagnostic graph", "lookup_field": "name"},
    "ca_certificate": {"label": "CA certificate", "lookup_field": "name"},
    "tls_certificate": {"label": "TLS certificate", "lookup_field": "name"},
    "certificate_signing_request": {"label": "certificate signing request", "lookup_field": "name"},
    # ── MJX (One-Touch Join) ──
    "mjx_integration": {"label": "MJX integration profile", "lookup_field": "name"},
    "mjx_endpoint": {"label": "MJX endpoint", "lookup_field": "name"},
    "mjx_endpoint_group": {"label": "MJX endpoint group", "lookup_field": "name"},
    "mjx_meeting_processing_rule": {"label": "MJX meeting processing rule", "lookup_field": "name"},
    "mjx_exchange_deployment": {"label": "MJX Exchange deployment", "lookup_field": "name"},
    "mjx_exchange_autodiscover_url": {"label": "MJX Exchange autodiscover URL", "lookup_field": "name"},
    "mjx_graph_deployment": {"label": "MJX Graph deployment", "lookup_field": "name"},
    "mjx_google_deployment": {"label": "MJX Google deployment", "lookup_field": "name"},
    # ── System infrastructure ──
    "dns_server": {"label": "DNS server", "lookup_field": "name"},
    "ntp_server": {"label": "NTP server", "lookup_field": "name"},
    "http_proxy": {"label": "HTTP proxy", "lookup_field": "name"},
    "syslog_server": {"label": "syslog server", "lookup_field": "name"},
    "snmp_network_management_system": {"label": "SNMP NMS", "lookup_field": "name"},
    "smtp_server": {"label": "SMTP server", "lookup_field": "name"},
    "static_route": {"label": "static route", "lookup_field": "name"},
    "ssh_authorized_key": {"label": "SSH authorized key", "lookup_field": "name"},
    # ── Upgrades & backups ──
    "upgrade": {"label": "software upgrade", "lookup_field": "name"},
    "software_bundle": {"label": "software bundle", "lookup_field": "name"},
    "software_bundle_revision": {"label": "software bundle revision", "lookup_field": "name"},
    "autobackup": {"label": "automatic backup schedule", "lookup_field": "name"},
    "system_backup": {"label": "system backup", "lookup_field": "name"},
    "scheduled_scaling": {"label": "Teams scheduled scaling", "lookup_field": "name"},
    # ── Web app ──
    "webapp_alias": {"label": "web app path", "lookup_field": "name"},
    "webapp_branding": {"label": "web app branding package", "lookup_field": "name"},
    "external_webapp_host": {"label": "external web app host", "lookup_field": "name"},
    # ── Policy ──
    "policy_profile": {"label": "policy profile", "lookup_field": "name"},
}

_RESOURCE_NAMES = sorted(RESOURCE_REGISTRY)
_RESOURCE_LIST_STR = ", ".join(_RESOURCE_NAMES)

# Resources whose mutation is equivalent to platform takeover or privilege
# escalation: planting an SSH key on the Management Node, minting admin
# roles/permissions, rewriting authentication/SSO trust, or swapping the
# TLS/CA trust anchors. Creating/updating/deleting any of these through the
# generic tool is refused unless PEXIP_ALLOW_SECURITY_RESOURCES=true, so a
# single prompt injection cannot reach them the same way it reaches a DNS
# server. Reads are unaffected (but see redact_secrets on the read paths).
SENSITIVE_RESOURCES: frozenset[str] = frozenset(
    {
        "ssh_authorized_key",
        "authentication",
        "role",
        "ldap_role",
        "permission",
        "adfs_auth_server",
        "adfs_auth_server_domain",
        "identity_provider",
        "identity_provider_group",
        "user_group",
        "user_group_entity_mapping",
        "tls_certificate",
        "ca_certificate",
        "certificate_signing_request",
    }
)


def _validate_resource(resource: str) -> dict[str, str]:
    meta = RESOURCE_REGISTRY.get(resource)
    if meta is None:
        raise PexipError(
            400,
            {
                "resource": [
                    f"Unknown resource {resource!r}. "
                    f"Valid resources: {_RESOURCE_LIST_STR}"
                ]
            },
        )
    return meta


def _guard_sensitive(resource: str, ctx: Context) -> None:
    """Refuse to mutate a security-critical resource unless explicitly allowed.

    Raises PexipError(403) for resources in SENSITIVE_RESOURCES when the server
    was not started with PEXIP_ALLOW_SECURITY_RESOURCES=true.
    """
    if resource in SENSITIVE_RESOURCES and not security_resources_allowed(ctx):
        raise PexipError(
            403,
            {
                "resource": [
                    f"Refusing to mutate security-critical resource {resource!r} "
                    "through the generic tool. This resource can grant platform "
                    "access, admin privileges, or trust changes. Set "
                    "PEXIP_ALLOW_SECURITY_RESOURCES=true to enable it deliberately."
                ]
            },
        )


@mcp.tool(annotations=read("List configuration resources"))
async def list_resources(
    ctx: Context,
    resource: str,
    name_contains: str | None = None,
    filters: dict[str, Any] | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """List any Pexip configuration resource that has no dedicated tool.

    This is the catch-all listing tool. Supported resources by area:

    - Admin auth & roles: authentication, role, ldap_role, permission,
      adfs_auth_server, adfs_auth_server_domain, identity_provider,
      identity_provider_group, user_group, user_group_entity_mapping.
    - Integrations & signaling: teams_proxy (Microsoft Teams Connectors),
      azure_tenant (Teams CVI tenant), gms_access_token, gms_gateway_token
      (Google Meet), ms_exchange_connector, exchange_domain, sip_proxy,
      sip_credential, mssip_proxy, h323_gatekeeper, turn_server, stun_server,
      policy_server, policy_profile, break_in_allow_list_address,
      telehealth_profile.
    - Scheduling & sync: registration, conference_sync_template,
      ldap_sync_field, scheduled_conference, scheduled_alias,
      recurring_conference.
    - Media library: media_library_entry, media_library_playlist,
      media_library_playlist_entry.
    - Platform & certificates: management_vm, licence, licence_request,
      media_processing_server, diagnostic_graphs, ca_certificate,
      tls_certificate, certificate_signing_request.
    - MJX / One-Touch Join: mjx_integration, mjx_endpoint, mjx_endpoint_group,
      mjx_meeting_processing_rule, mjx_exchange_deployment,
      mjx_exchange_autodiscover_url, mjx_graph_deployment,
      mjx_google_deployment.
    - System infrastructure: dns_server, ntp_server, http_proxy,
      syslog_server, snmp_network_management_system, smtp_server,
      static_route, ssh_authorized_key.
    - Backups & upgrades: system_backup (existing system backups), autobackup
      (backup schedule), upgrade, software_bundle, software_bundle_revision,
      scheduled_scaling.
    - Web app: webapp_alias, webapp_branding, external_webapp_host.

    Call get_resource_schema(resource) to discover filterable fields.

    Args:
        resource: API resource name from the list above (e.g. "sip_proxy",
            "system_backup", "teams_proxy", "dns_server").
        name_contains: Case-insensitive substring match on the name field.
        filters: Additional query filters as key-value pairs (e.g.
            {"enable": true}). Keys must match the resource's field names.
        limit: Max results per page (default 20).
        offset: Pagination offset.
    """
    _validate_resource(resource)
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if name_contains:
        params["name__icontains"] = name_contains
    if filters:
        params.update(filters)
    return redact_secrets(await get_client(ctx).list(resource, **params))


@mcp.tool(annotations=read("Get configuration resource"))
async def get_resource(
    ctx: Context,
    resource: str,
    id: int | str,
) -> dict[str, Any]:
    """Get a single configuration resource by integer id or by name.

    Args:
        resource: API resource name (see list_resources for the full list).
        id: Integer id, numeric string, or the resource's name — names are
            resolved automatically, so there is no need to list first.
    """
    meta = _validate_resource(resource)
    client = get_client(ctx)
    resolved = await resolve_id_by_field(
        client, resource, id, field=meta["lookup_field"]
    )
    return redact_secrets(await client.get(resource, resolved))


@mcp.tool(annotations=create("Create configuration resource"))
async def create_resource(
    ctx: Context,
    resource: str,
    settings: dict[str, Any],
) -> dict[str, Any]:
    """Create a new configuration resource.

    Simple resources need only their obvious fields — e.g. a DNS server is
    just {"address": "10.0.0.53"}, an NTP server {"address": "pool.ntp.org"},
    a syslog server {"address": "10.0.0.99", "port": 514} — so create those
    directly. Call get_resource_schema(resource) first only when you are
    unsure which fields are required.

    Security-critical resources (ssh_authorized_key, authentication, role,
    permission, identity_provider, tls_certificate, ca_certificate, and
    similar) are refused here unless the server was started with
    PEXIP_ALLOW_SECURITY_RESOURCES=true.

    Args:
        resource: API resource name (see list_resources for the full list).
        settings: Field values for the new resource (must include required fields).
    """
    _validate_resource(resource)
    _guard_sensitive(resource, ctx)
    if not settings:
        raise PexipError(400, {"settings": ["At least one field is required"]})
    client = get_client(ctx)
    location = await client.create(resource, settings)
    return redact_secrets(await client.get(resource, extract_id_from_uri(location)))


@mcp.tool(annotations=update("Update configuration resource"))
async def update_resource(
    ctx: Context,
    resource: str,
    id: int | str,
    settings: dict[str, Any],
) -> dict[str, Any]:
    """Patch a configuration resource. Only provided fields are changed.

    Args:
        resource: API resource name (see list_resources for the full list).
        id: Integer id, numeric string, or the resource's name — names are
            resolved automatically, so there is no need to list first.
        settings: Fields to update.
    """
    meta = _validate_resource(resource)
    _guard_sensitive(resource, ctx)
    if not settings:
        raise PexipError(400, {"settings": ["At least one field is required"]})
    client = get_client(ctx)
    resolved = await resolve_id_by_field(
        client, resource, id, field=meta["lookup_field"]
    )
    await client.update(resource, resolved, settings)
    return redact_secrets(await client.get(resource, resolved))


@mcp.tool(annotations=delete("Delete configuration resource"))
async def delete_resource(
    ctx: Context,
    resource: str,
    id: int | str,
) -> dict[str, Any]:
    """Delete a configuration resource. Irreversible.

    Args:
        resource: API resource name (see list_resources for the full list).
        id: Integer id, numeric string, or the resource's name — names are
            resolved automatically, so there is no need to list first.
    """
    meta = _validate_resource(resource)
    _guard_sensitive(resource, ctx)
    client = get_client(ctx)
    resolved = await resolve_id_by_field(
        client, resource, id, field=meta["lookup_field"]
    )
    await client.delete(resource, resolved)
    return {"deleted": True, "resource": resource, "id": resolved}
