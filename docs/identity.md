# Identity & authentication

This server sits between an MCP client (an LLM agent) and the Pexip Infinity
Management API. There are **two independent auth boundaries**, and it helps to
keep them separate:

```
   MCP client (agent)  ──[ Boundary B ]──▶  pexip-mgmt-mcp  ──[ Boundary A ]──▶  Pexip Infinity
        (who may use                          (this server)                      (admin REST API)
         THIS server?)                                                (how does the server log in?)
```

- **Boundary A — server → Infinity.** How this server authenticates *to* Pexip.
  Configured with `PEXIP_AUTH_MODE` (`basic` or `oauth2`). See the main README
  and `.env.example`. This document is **not** about Boundary A.
- **Boundary B — client → server.** How an MCP client authenticates *to this
  server* over the `--http` transport. That's what this document covers.

> **stdio needs none of this.** When the server runs over stdio (Claude Desktop
> or `uvx pexip-mgmt-mcp`), there is no network listener and no
> Boundary B — the client *is* the local process. Boundary B only applies to the
> `--http` transport.

## The Boundary-B ladder

Pick the rung that matches your deployment. **Default is a static token; OAuth is
opt-in.** Nothing here requires a third-party proxy or a new vendor.

| Rung | Who it's for | Set |
|------|--------------|-----|
| **None** | stdio, or loopback bind reached over a trusted private network | *(nothing)* |
| **Static token** *(default)* | one admin or a small trusted team | `PEXIP_MCP_TOKEN` |
| **OIDC (oauth)** | a team that wants per-user identity, and already runs an IdP | `PEXIP_MCP_AUTH_MODE=oauth` + `PEXIP_OIDC_*` |

A non-loopback bind refuses to start unless a static token **or** OAuth is
configured — the server will not expose an unauthenticated admin surface on a
routable address.

### Rung 2 — static bearer token (default)

The token is a shared secret: the **same value** goes in the server's env and in
the client's `Authorization: Bearer` header. Generate a strong one:

```bash
pexip-mgmt-mcp --generate-token
# prints:  PEXIP_MCP_TOKEN=<43-char random>
```

Set that value in the server env, and send the same value from the client. The
token must be at least 32 characters; the server refuses to start with a shorter
one. It is compared in constant time.

This works fully offline / air-gapped and needs nothing else.

### Rung 3 — OIDC (opt-in)

For a shared `--http` deployment where you want to know *which* admin did what,
point the server at an OIDC provider **you already run** — Microsoft Entra,
Google, Okta, or an on-prem OIDC server. No new vendor, no proxy: the server
itself validates the bearer JWT against your IdP's public keys (JWKS).

```bash
PEXIP_MCP_AUTH_MODE=oauth
PEXIP_OIDC_ISSUER=https://login.microsoftonline.com/<tenant-id>/v2.0
PEXIP_OIDC_AUDIENCE=api://pexip-mcp            # must match the token's aud
PEXIP_OIDC_REQUIRED_SCOPES=pexip.read pexip.write   # optional
# PEXIP_OIDC_JWKS_URI=...   # optional; discovered from the issuer if unset
```

What the server checks on every request: signature (against JWKS), `iss`, `aud`
(so a token minted for a different app is rejected), `exp`, and any required
scopes. Validation is local — the only thing it reaches is your own IdP's JWKS
endpoint.

Issuer examples:
- **Entra:** `https://login.microsoftonline.com/<tenant-id>/v2.0`
- **Google:** `https://accounts.google.com`
- **Okta:** `https://<your-org>.okta.com/oauth2/<auth-server-id>`
- **On-prem OIDC** (Keycloak/ADFS/etc.): whatever issuer it advertises.

The audience must be bound to *this* server (register it as an application /
resource in your IdP and use its identifier as `PEXIP_OIDC_AUDIENCE`). Reject
generic audiences like `api`.

The server also publishes a discovery document at
`/.well-known/oauth-protected-resource` (RFC 9728) so spec-aware MCP clients can
find your IdP, and returns a `WWW-Authenticate` challenge pointing at it on 401.

## What OIDC does and doesn't give you here

In the common shared-server setup the server holds **one** Infinity credential
(Boundary A) and every admin shares it upstream. So:

- **Identity & audit** — Boundary B gives each request a real principal
  (`sub`/email). Because Infinity's own audit log sees only the shared service
  account, **this server's log is the authoritative "who did what"** in this
  topology. (In the stdio, one-credential-per-person model, Infinity's log
  already answers that, so this matters specifically for the shared `--http`
  case.) Every mutating call emits one structured line on the `pexip_mcp.audit`
  logger — `action`, `resource`, resolved `id`, `outcome`, `duration_ms`, and
  `principal` — where the principal is the OIDC identity when present, else the
  server's credential identity. See "Audit logging" below.
- **Authorization** — enforced *here* via scopes (`PEXIP_OIDC_REQUIRED_SCOPES`)
  and the server's own `read_only` / sensitive-resource gates, layered in front
  of Infinity's role. Infinity can't distinguish the admins, so its role is the
  ceiling for everyone.

If you need Infinity itself to enforce a different role per admin, give each
person their own Infinity OAuth2 client on Boundary A instead — at the cost of
managing per-user upstream credentials.

## Audit logging

Every state-changing call (create / update / delete / command) emits one
key=value line on the `pexip_mcp.audit` logger — successes at INFO, failures at
WARNING. Example:

```
audit action=update resource=conference id=42 outcome=ok duration_ms=13 principal=oauth2:mcp-svc
audit action=delete resource=gateway_rule id=3 outcome=error status=404 duration_ms=8 principal=josh@example.com ref=9f2a1c04
```

- **principal** — the OIDC token identity in `oauth` mode, otherwise the
  server's own credential (`basic:<user>` / `oauth2:<client-id>`).
- **id** — the *resolved* target (the integer id the name resolved to), so the
  record shows exactly which object was touched, not just the argument passed.
- **ref** — on failure, a correlation id that also appears in the error the
  client receives, so a reported error maps straight back to this line.

Reads (list/get/schema) are intentionally not audited. No secrets appear in
audit lines. Ship the `pexip_mcp.audit` logger wherever you keep your audit
trail; it is independent of the app's other logging.

## Error handling

Errors from the Management Node are returned to the client as a generic
message plus a correlation id (`Pexip API error 500 (ref 9f2a1c04)`), never the
raw upstream body — which could carry internal detail. The full body is logged
internally at DEBUG under the same id. Errors the server raises itself
(validation, the sensitive-resource guard, etc.) keep their helpful messages,
since those are ours and safe to show.

## Not a substitute

Boundary B (this document) authenticates clients to the server. It does **not**
change how the server logs in to Infinity — that's Boundary A (`PEXIP_AUTH_MODE`)
and is configured independently.
