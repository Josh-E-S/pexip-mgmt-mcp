# Security Policy

## Reporting a vulnerability

Please report suspected security vulnerabilities **privately** — do not open a
public issue for anything exploitable.

- Preferred: open a [GitHub private security advisory](https://github.com/Josh-E-S/pexip-mgmt-mcp/security/advisories/new).
- Alternatively, email the maintainer listed in the repository profile.

Please include enough detail to reproduce (affected version, configuration,
and steps). We aim to acknowledge reports within 5 business days.

## Supported versions

This project is pre-1.0. Security fixes are applied to the latest released
version on the `main` branch. Pin to a released version and upgrade promptly
when a fix ships.

## Security model

This server wraps the **Pexip Infinity Management API** — a full administrative
surface. Treat it with the same care as the admin credentials it uses.

- **Credentials.** The server authenticates to the Management Node with either a
  local admin username/password (`basic`) or an OAuth2 client (`oauth2`, JWT
  bearer assertion). Supply them via environment variables / secret storage —
  never commit them. The MCPB and registry manifests mark the password and
  OAuth2 private key as secret fields.
- **Least privilege.** The credential's Pexip role determines what the server
  can do. Create a scoped Administrator Role for the server rather than reusing
  a full superuser, especially when enabling writes.
- **Read-only mode (default).** The server starts in read-only mode: every
  mutating tool (create/update/delete and all Command-API control actions) is
  unregistered at startup, leaving only list/get/schema reads. This is enforced
  server-side — it removes the tools from the catalog entirely, not just via
  advisory MCP annotations. Set `PEXIP_READ_ONLY=false` to deliberately opt in
  to the mutating admin surface (logged loudly at startup).
- **Security-critical resources.** When writes are enabled, the generic CRUD
  tools still refuse to create/update/delete security-critical resources — SSH
  authorized keys, admin roles/permissions, authentication/SSO configuration,
  and TLS/CA certificates — unless `PEXIP_ALLOW_SECURITY_RESOURCES=true` is set.
  This keeps a single prompt injection from planting an SSH key or minting an
  admin role through the same path used to add a DNS server.
- **Platform-lifecycle tools.** The highest-blast-radius command tools (backup
  create/restore, certificate import, platform upgrade, software-bundle upload,
  cloud-node start, snapshot) are removed from the catalog at startup even when
  writes are enabled, unless `PEXIP_ALLOW_PLATFORM_TOOLS=true`. One injected
  call to these could replace or compromise the whole platform, so exposing them
  is a deliberate, logged opt-in. Per-call human approval for the remaining
  destructive tools is left to the MCP client via the `destructiveHint`
  annotation.
- **Secret redaction.** Read tools mask secret-bearing fields (passwords, bind
  passwords, private keys, tokens) before returning records, so credentials are
  not echoed into the model context or provider logs.
- **Audit logging.** Every mutating call (create/update/delete/command) emits a
  structured line on the `pexip_mcp.audit` logger with the action, resource,
  resolved id, outcome, latency, and principal (the OIDC identity when present,
  else the server credential). See [docs/identity.md](docs/identity.md).
- **Error handling.** Management-Node error bodies are not returned to the
  client — the caller gets a generic message plus a correlation id, and the full
  detail is logged internally under that id, so upstream internals never reach
  the model.
- **Destructive tools.** Even outside read-only mode, tools that mutate state
  carry MCP `destructiveHint` annotations so a well-behaved client can prompt
  before acting. These are hints; do not rely on them as an access control.
- **Transport & client auth.** The default transport is stdio (no network
  listener). The optional `--http` transport refuses to bind a non-loopback
  address unless downstream auth is configured: either a static bearer token
  (`PEXIP_MCP_TOKEN`, min 32 chars, constant-time compared — generate one with
  `pexip-mgmt-mcp --generate-token`) or OIDC validation against your own IdP
  (`PEXIP_MCP_AUTH_MODE=oauth`, which checks JWT signature/issuer/audience/
  scopes and attaches the caller's identity for audit). See
  [docs/identity.md](docs/identity.md). Terminate TLS and apply rate limiting at
  a reverse proxy in front of it.
- **TLS.** Certificate verification to the Management Node is on by default.
  `PEXIP_VERIFY_TLS=false` is for lab/self-signed nodes only and logs a warning.
