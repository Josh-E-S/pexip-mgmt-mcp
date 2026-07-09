---
name: pexip-external-policy
description: Use when building or extending Pexip's External Policy Server integration — a custom HTTP service Pexip Infinity consults at call setup to make routing, authentication, or admission decisions that go beyond the built-in dial plan. Triggers on `external_policy_server`, `/api/admin/configuration/v1/external_policy_server/`, `policy_request`, `service_lookup`, `participant_avatar_lookup`, `participant_properties_lookup`, "external policy", "policy server", "custom call routing", "per-call decisions", "dynamic VMR". Do NOT use for static dial-plan rules (use `pexip-config-api` / `pexip-operations/dial-plan.md`) or for runtime command/control (use `pexip-command-api`).
license: MIT
---

# Pexip external policy server

The **External Policy API** lets Pexip Infinity outsource per-call decisions to an HTTP service you run. At well-defined hook points (call setup, service lookup, avatar lookup, participant property lookup), Pexip POSTs a request to your endpoint and applies the JSON response — overriding or augmenting the static dial plan.

Use it when the answer to "where should this call go?" depends on data Pexip doesn't have: your CRM, scheduling system, real-time capacity heuristics, custom auth, dynamic VMRs per booking, etc.

> **Coverage:** the MCP server manages external policy servers today through its **generic CRUD** tools — the `policy_server` and `policy_profile` resources are in the resource registry (`resource_crud.py`), so `list_resource` / `get_resource` / `create_resource` / `update_resource` / `delete_resource` all work against them (no dedicated `*_external_policy_server` tools, and no `PEXIP_ALLOW_SECURITY_RESOURCES` gate). This skill covers configuring those servers **and** building the receiver side (the HTTP service Pexip calls).

## When to use

- "Build a dynamic VMR per calendar invite" (booking system → VMR creation on demand)
- "Authenticate calls against our SSO before allowing join"
- "Route calls to the lowest-loaded location at the moment of dial"
- "Inject custom branding / display names per call"
- Adding `external_policy_server` CRUD tools to the MCP server

## When NOT to use

- Static dial plan with regex matching → `pexip-config-api` (`gateway_routing_rule`) / `pexip-operations/dial-plan.md`
- Persistent VMRs configured ahead of time → `pexip-operations/vmr-administration.md`
- Runtime kick/lock/mute → `pexip-command-api`

## Hook points (high-level)

The Pexip External Policy API defines several request types. Pexip POSTs JSON to your endpoint with the request type and call context; you return JSON describing the decision.

| Hook | When fired | Typical use |
|---|---|---|
| `service_lookup` | A call arrives and Pexip needs to find/create the service it joins | Dynamic VMR creation, per-booking conferences |
| `participant_lookup` | Participant identity needs verification | SSO / external auth integration |
| `participant_avatar_lookup` | Need an avatar URL for a participant | Pull from your directory |
| `participant_properties_lookup` | Need custom properties (display name overrides, role, location) | Per-call branding |

Exact request/response schemas vary across Pexip Infinity versions — **read the authoritative doc** before implementing. Pexip ships canned examples for each hook.

## Receiver-side contract

Same general shape as event sinks but synchronous:

1. **Accept POST**, return **200** with a JSON body shaped per Pexip's spec.
2. **Be fast.** Pexip blocks the call setup waiting for your response — multi-second latency is a user-visible "slow to connect" issue.
3. **Be deterministic** for testability. Pexip retries on 5xx but not on 4xx; idempotency-by-input is the easiest contract.
4. **TLS auth.** Pexip can present a client cert; configure mutual TLS if you need to verify the request really came from your Management Node.

## Configuration (via generic CRUD)

Manage policy servers with the generic resource tools, passing `resource="policy_server"`:

```
list_resource(resource="policy_server")
get_resource(resource="policy_server", identifier="<name-or-id>")
create_resource(resource="policy_server", data={"name": …, "url": …, "ssl_cert": …, …})
update_resource(resource="policy_server", identifier="<name-or-id>", data={…})
delete_resource(resource="policy_server", identifier="<name-or-id>")
```

`policy_profile` works the same way. Introspect the exact fields first with
`get_resource_schema(resource="policy_server")` — they shift across Pexip versions.
You can also configure these in Pexip's admin UI under **Call Control → External Policy**.

## Field gotchas (anticipated, verify when implementing)

- Policy server responses can include URIs to dynamically created configuration objects — make sure your creator side responds with valid URIs Pexip can parse.
- The policy server is in the synchronous path of call setup; outages cause join failures. Always have a fallback (e.g. fall through to static dial plan).
- Pexip versions before v30 had some response-schema deltas around service properties; if you support older deployments, branch on version.

## Reference source

- **Authoritative Pexip docs:**
  - External policy overview: https://docs.pexip.com/admin/external_policy.htm
  - API reference: https://docs.pexip.com/api_manage/api_external_policy.htm
- **MCP server source:** managed via the generic CRUD registry in `src/pexip_mcp/tools/resource_crud.py` (`policy_server`, `policy_profile`). A future dedicated `external_policy.py` module could add typed tools, but is not required for coverage.
- **Related skills:** `pexip-config-api` (existing resource model), `pexip-operations/dial-plan.md` (the static-rule alternative), `pexip-event-sinks` (the push-event sibling)
