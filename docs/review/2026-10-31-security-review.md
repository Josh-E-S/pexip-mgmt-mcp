# Security review — pexip-mgmt-mcp (2026-10-31)

Adversarial, read-only review of the MCP server that exposes the Pexip Infinity
Management API to LLM agents. Threat model as briefed: (1) a prompt-injected /
misbehaving agent trying to escape read-only mode, the platform-tool gate, the
sensitive-resource gate or path-segment validation; (2) unauthenticated /
wrongly-authenticated clients on `--http` (token + OIDC, PRM discovery,
Host/DNS-rebinding, loopback-behind-tunnel assumptions); (3) secret leakage into
model context or logs; (4) supply chain and config.

Baseline: `uv run pytest tests/ -q -p no:cacheprovider --no-cov` →
**214 passed, 10 xfailed** (green). Installed: `mcp 1.28.1`, `starlette 1.3.1`,
`uvicorn 0.49.0`, `pyjwt 2.13.0`, `httpx 0.28.1`. Findings tagged *(empirical)*
were confirmed by driving the real ASGI app with Starlette's `TestClient`.
Nothing under `src/`, `tests/`, `evals/` was modified.

Severity: **High** = one injected call or one unauthenticated request yields
platform/credential compromise or defeats a documented control; **Medium** =
defeats a control under a realistic precondition, or breaks a control the docs
call authoritative; **Low** = hardening / DoS / defence-in-depth;
**Informational** = doc/test accuracy.

---

## High

### H1. Many high-impact registry resources grant platform access or persistence but are not in `SENSITIVE_RESOURCES` or `PLATFORM_TOOLS`

**Where.** `tools/resource_crud.py:31-109` (`RESOURCE_REGISTRY`), `:121-138`
(`SENSITIVE_RESOURCES`), `:156-173` (`_guard_sensitive`);
`mcp_app.py:62-72` (`PLATFORM_TOOLS`); dedicated tools in `tools/ldap.py`,
`tools/global_settings.py:28-52`, `tools/command.py:447-472`.

**Promise.** SECURITY.md:43-56 states a single prompt injection cannot reach
privilege/persistence/trust changes "the same way it reaches a DNS server", and
that the highest-blast-radius operations are removed unless
`PEXIP_ALLOW_PLATFORM_TOOLS=true`.

**Reality.** With `PEXIP_READ_ONLY=false` and both opt-in flags at their
defaults, the generic CRUD tools (and a few ungated dedicated tools) reach a
large set of resources whose mutation is equivalent to what the gates block.
`_guard_sensitive` only checks membership in the 14-entry `SENSITIVE_RESOURCES`
set; everything else in the ~70-entry registry is freely mutable. Each of the
following is only an argument string away from an already-exposed tool:

- **Credential/trust exfiltration via redirection** — `policy_server`,
  `ldap_sync_source` (`ldap.py`), `ms_exchange_connector`,
  `mjx_exchange_deployment`, `mjx_graph_deployment`, `mjx_google_deployment`,
  `mjx_integration`, `smtp_server`, `http_proxy`, `dns_server`, `static_route`,
  `ntp_server`, `syslog_server`. These hold or transmit service credentials
  (LDAP bind, Exchange/Graph service accounts, SMTP, SNMP) or control where the
  platform resolves names / routes traffic / ships logs. Changing an endpoint
  URL or hostname causes the stored or in-flight credential to be presented to
  attacker infrastructure on the next sync, and causes trust-dependent traffic
  to flow through attacker systems. `dns_server` is even used as the benign
  example in the `create_resource` docstring (`resource_crud.py:266-270`).
- **Call-routing / federation trust** — `azure_tenant`, `teams_proxy`,
  `gms_access_token`, `gms_gateway_token`, `sip_proxy`, `sip_credential`,
  `mssip_proxy`, `h323_gatekeeper`, `turn_server`, `stun_server`. Mutating
  these redirects or relays calls/media.
- **Backup / recovery / lifecycle** — `autobackup` (scheduled off-box backup of
  the whole config, including secrets, to a configurable destination),
  `system_backup`, `upgrade`, `software_bundle`, `software_bundle_revision`,
  `licence`, `licence_request`. The command-API equivalents (`backup_create`,
  `platform_upgrade`, `upload_software_bundle`) *are* in `PLATFORM_TOOLS`, but
  the configuration-API resources that model the same operations are not, so the
  gate is inconsistent. (Whether POST/PATCH on these config resources actually
  performs the operation is Pexip-side — see *Needs human review*.)
- **Management Node & PIN controls** — `management_vm` (SSH enable, authorized
  keys, SNMP v3, node network config), `break_in_allow_list_address` (exempts an
  address from PIN brute-force protection), `update_global_settings`
  (`global_settings.py`) which PATCHes the `global` singleton, including
  break-in resistance / PIN-entry behaviour / crypto mode / session timeout.
- **Browser-facing assets** — `webapp_branding`, `external_webapp_host`,
  `webapp_alias`: branding packages can carry custom JS/CSS served to every web
  join (stored-XSS surface).
- **Provisioning-email path** — `send_conference_email` / `send_device_email`
  (ungated control tools, `command.py:447-472`): provisioning emails carry join
  details and PINs, which bypasses `redact_secrets` since the PIN leaves via
  email rather than the tool response.

**Fix (do not implement).** Treat the gate as a default-deny allow-list rather
than a 14-item deny-list. Concretely: (a) add the credential/trust, routing,
backup-lifecycle, `management_vm`, `policy_*`, `break_in_allow_list_address`,
`smtp_server`, `http_proxy`, `syslog_server`, `static_route`, `webapp_*` and
`global` resources (and the `mjx_*`/`*_token` entries that carry credentials) to
`SENSITIVE_RESOURCES` or a new `PLATFORM_RESOURCES` set that requires
`PEXIP_ALLOW_PLATFORM_TOOLS`; (b) gate `update_global_settings`,
`send_conference_email`, `send_device_email` the same way; (c) consider flipping
the model so a registry entry is non-sensitive only when explicitly flagged
`"risk": "operational"`, so new entries fail closed. Document the taxonomy in
SECURITY.md so the promise matches the code.

### H2. Audit principal is bound per TCP/session, not per request — in the shared OIDC topology the "authoritative who-did-what" log can be wrong *(empirical)*

**Where.** `__main__.py:165-193` (`OIDCAuth.dispatch` sets
`audit.current_principal` from the request's own token), the MCP SDK's
streamable-HTTP session manager (`streamable_http_manager.py`: one persistent
`run_server` task per `mcp-session-id`), and `audit.py:33-35`.

**Problem.** `docs/identity.md:328-341` says that in the shared `--http` + OIDC
deployment this server's audit log is the *authoritative* per-user trail because
Infinity only sees one service credential. But the MCP streamable-HTTP transport
runs each session's JSON-RPC calls inside a long-lived anyio task created at
`initialize`. The `contextvar` set by the per-request middleware does not
reliably propagate into that pre-existing task's context, and the session is
keyed only by the `mcp-session-id` header — not by the bearer identity.

Confirmed empirically: with an OIDC validator that maps `Bearer alice`→alice and
`Bearer bob`→bob, after alice initializes a session, **bob can present his own
valid token together with alice's `mcp-session-id` and the tool executes,
attributed to `alice@example.com`** (`principal_seen_by_tool: alice@example.com`
for bob's request). So (a) a second authenticated user can ride another user's
session and act under that user's identity, and (b) the audit principal recorded
for mutations is the session-opener, not necessarily the caller — directly
undermining the document's "authoritative trail" claim.

**Fix.** Do not rely on a `contextvar` set in `BaseHTTPMiddleware` for per-call
attribution on streamable-HTTP. Either resolve the principal inside the tool
dispatch path from the current request, or bind the session to the identity that
created it and reject a `mcp-session-id` presented with a different principal.
See also H3 (the middleware style is itself unsupported here) — fixing H3 is a
prerequisite for a clean fix.

### H3. Both auth middlewares subclass `BaseHTTPMiddleware`, which is incompatible with streamable-HTTP and buffers SSE *(known issue — confirmed)*

**Where.** `__main__.py:143,165,203` — `OIDCAuth(BaseHTTPMiddleware)` and
`BearerAuth(BaseHTTPMiddleware)`.

**Confirmation.** The briefed concern is real. Starlette's `BaseHTTPMiddleware`
wraps the downstream app in a `_StreamingResponse` driven by an anyio
memory-stream bridge; it is documented to break long-lived SSE and to interfere
with the ASGI scope/task model that the MCP `StreamableHTTPSessionManager`
relies on (per-session task, `contextvar` propagation, streaming responses). In
this build the SSE path still returns `200 text/event-stream` for `tools/list`
through the wrapper *(empirical)*, so it is not fully broken today, but it is
riding on version-specific behaviour and is the direct cause of H2's
context-propagation failure. It also means every streamed response is mediated
by the bridge rather than passed through as a native ASGI stream.

**Fix.** Re-implement both as pure-ASGI middleware (a `__call__(scope, receive,
send)` class that inspects `scope["headers"]`, short-circuits with a 401, and
otherwise awaits `self.app`), exactly as the MCP SDK's own
`RequireAuthMiddleware`/`BearerAuthBackend` do (`mcp/server/auth/middleware/`).
A pure-ASGI 401 gate adds no streaming bridge and lets the principal be attached
to the ASGI scope rather than a cross-task contextvar.

---

## Medium

### M1. Non-ASCII `Authorization` header makes the static-token gate raise 500, not 401 *(empirical)*

**Where.** `__main__.py:203-210` — `hmac.compare_digest(provided, expected)`
with `provided` taken straight from the header.

**Problem.** `hmac.compare_digest` raises `TypeError: comparing strings with
non-ASCII characters is not supported` when either operand is a `str` containing
a non-ASCII codepoint. Driving the ASGI app with
`Authorization: Bearer \xe9\xe9\xe9` yields **HTTP 500** (unhandled `TypeError`)
instead of 401. A control request with an ASCII wrong token correctly returns
401. So an attacker can distinguish "token comparison reached" from other
rejections, and can trivially trigger 500s (log noise / minor DoS). The OIDC
path is unaffected (it splits/encodes before comparing).

**Fix.** Compare bytes, not text: `hmac.compare_digest(provided.encode("utf-8",
"replace"), expected.encode("utf-8"))`, or guard with a `try/except TypeError`
returning 401. Add a test with a non-ASCII header asserting 401.

### M2. `_prm_url` builds the RFC 9728 `resource_metadata` URL from the OIDC audience, so a typical `api://…` audience yields an unfetchable URL *(known issue — confirmed, empirical)*

**Where.** `__main__.py:221-224` (`_prm_url`), used in the `WWW-Authenticate`
header at `:178-182`; `_prm_endpoint` at `:227-239`.

**Confirmation.** `_prm_url` does `base = settings.oidc_audience; base.rstrip("/")
+ _PRM_PATH`. With the documented audience `api://pexip-mcp`
(`.env.example:212`, `docs/identity.md:304`) the emitted header is
`resource_metadata="api://pexip-mcp/.well-known/oauth-protected-resource"`
*(empirical)* — an `api://` URI a spec-aware MCP client cannot fetch, so RFC 9728
discovery fails and the client cannot auto-complete the OAuth handshake. The PRM
*document* is served correctly at the real path; only the advertised URL is
wrong. The audience (a resource identifier) and the PRM document's own https URL
are being conflated.

**Fix.** Derive the PRM URL from the actual request (scheme + Host +
`_PRM_PATH`) or from a configured external base URL
(`PEXIP_PUBLIC_URL`/`PEXIP_MCP_EXTERNAL_URL`), never from `oidc_audience`. Keep
`resource` in the body equal to the audience, but make `resource_metadata` an
absolute https URL that resolves.

### M3. No Host/Origin allow-list is configured, so DNS-rebinding protection depends entirely on the loopback default and silently disables on `--host 0.0.0.0` *(empirical)*

**Where.** `__main__.py:122-214` (`_build_http_app` never sets
`transport_security`); `mcp_app.py:184` (`FastMCP("pexip-mgmt")` uses default
host `127.0.0.1`). SDK behaviour: `fastmcp/server.py:178-181` enables DNS-rebind
protection with `allowed_hosts=["127.0.0.1:*","localhost:*","[::1]:*"]` **only
when the configured host is loopback**; `transport_security.py:38-40` defaults
protection **off** otherwise.

**Problem.** The MCP server object is constructed with the default loopback host
regardless of the CLI `--host`, so in this build DNS-rebind protection is on and
keyed to loopback Host headers — confirmed: Host `localhost`/`127.0.0.1`
(no port) and `pexip-mcp.example.com` are rejected, only `localhost:8000` /
`127.0.0.1:9999` pass *(empirical)*. Two consequences:
(a) the public hostname a Cloudflare Tunnel forwards (`pexip-mcp.example.com`)
is **rejected** with 421 unless an operator adds it — DEPLOY.md does not mention
this, so a correct deployment appears broken, inviting operators to disable
protection; (b) nothing in this repo validates Host/Origin itself — it is
entirely delegated to the SDK default, and if the FastMCP host were ever set to
the bind host (so `0.0.0.0`), protection would turn **off**. The briefed
`_LOOPBACK_HOSTS` set (`__main__.py:31`) governs only the *bind guard*, not Host
validation, and it does not cover `0.0.0.0`, `::`, `127.0.0.2`, or `localhost`
resolving to `::1`.

**Fix.** Set an explicit `TransportSecuritySettings` with the operator's real
external hostname(s) in `allowed_hosts`/`allowed_origins`, sourced from config
(e.g. `PEXIP_MCP_ALLOWED_HOSTS`), and document in DEPLOY.md that the tunnel
public hostname must be listed. Do not let the Host allow-list implicitly follow
the bind address.

### M4. Loopback bind is treated as trusted, but a co-located reverse proxy (the documented Cloudflare Tunnel posture) forwards external traffic to it with no token required

**Where.** `__main__.py:75-103` (`_check_safe_to_bind` returns `None` — "safe" —
for any loopback host with no token and no OIDC); DEPLOY.md:9-18,46-67 shows the
recommended posture running with "Downstream auth: disabled (relying on network
layer)".

**Problem.** The safe-to-bind guard equates "bound to 127.0.0.1" with "only
reachable by trusted local callers". In the documented tunnel deployment that is
false: `cloudflared` runs on the same host and forwards arbitrary internet
traffic to `127.0.0.1:8000`. If the Cloudflare Access policy is missing,
misconfigured, or bypassed, the full admin tool surface is reachable with **no
MCP-layer authentication at all**, because the server chose not to require one on
loopback. DEPLOY.md:110-126 correctly recommends a token "for defense in depth"
but the server permits the tokenless posture, and §1's sample output advertises
"auth: disabled" as a normal state.

**Fix.** When `--http` is selected, require downstream auth (token or OIDC)
*regardless of bind address* unless an explicit `PEXIP_MCP_INSECURE_LOOPBACK=1`
escape hatch is set; or at minimum treat the presence of a forwarding proxy as
the default assumption and make tokenless loopback the opt-in, not the default.
Update DEPLOY.md so the baseline shows a token set.

### M5. OIDC `aud` accepts list audiences and there is no `azp`/`sub` requirement, widening confused-deputy exposure

**Where.** `oidc.py:105-119` — `jwt.decode(..., audience=self._audience,
options={"require": ["exp","iss","aud"]})`.

**Analysis of the OIDC checks (mostly good, with gaps):**
- Algorithm allow-list is asymmetric-only (`RS*/ES*`), HS256 excluded — good,
  avoids the alg-confusion pitfall (`oidc.py:34`).
- `iss` is a plain string equality in PyJWT (`api_jwt.py:_validate_iss`) — good.
- `exp` required, 30s leeway — reasonable.
- JWKS fetched https-only (`_require_https`, `oidc.py:79-81,167-170`) — good.
- **`aud` list handling:** PyJWT (`_validate_aud`) accepts the token if the
  configured audience appears *anywhere* in a list `aud`. A token minted for
  `["api://other-app","api://pexip-mcp"]` is accepted. For a confused-deputy
  control this is weaker than a strict single-audience match; `strict_aud` is
  not set. Combined with no `azp`/`client_id` check, a token legitimately issued
  to a *different* client that merely lists this audience is accepted.
- **`sub` not required:** `require` lists only `exp/iss/aud`. A token with no
  `sub` passes; `principal_of` then falls back through email/upn and can land on
  `"unknown"` (`oidc.py:135-141`), producing unattributable audit lines.
- **No replay/`jti` tracking and no `nbf`/`iat` sanity beyond leeway** — standard
  for stateless bearer validation, acceptable, but worth noting a stolen token is
  replayable until `exp`.
- **JWKS fetch failure at request time:** `get_signing_key_from_jwt` raising is
  caught and converted to `OIDCValidationError` → 401 (`oidc.py:100-102`). So an
  IdP JWKS outage fails closed (401), which is correct, but it means a transient
  IdP blip denies all access; `PyJWKClient` here is constructed with default
  caching (`cache_keys=False`), so every unknown-kid triggers a network fetch.

**Fix.** Pass `options={"require":["exp","iss","aud","sub"]}`; set
`strict_aud=True` (requiring a string audience) or post-validate that `aud` is
exactly the configured value; optionally enforce an expected `azp`/`client_id`.
Enable `PyJWKClient(..., cache_keys=True, lifespan=...)` so JWKS is cached and a
brief IdP outage doesn't 401 every call.

### M6. `list_resources` forwards arbitrary caller-controlled `filters` keys/values straight into the query string, enabling relation traversal and response-shape/format changes

**Where.** `resource_crud.py:230-235` — `params.update(filters)` then
`client.list(resource, **params)`; `client.py:198-203` passes `**params` to
httpx as query params. Also `schema()` hard-codes `format=json` but `list()`
does not constrain keys.

**Problem.** `_safe_segment`/`_safe_resource_path` only validate the URL *path*
segments, not query keys/values. `filters` is `dict[str, Any]` with no
allow-list, so a caller can send Django/Tastypie-style lookups the tool author
never intended: `{"field__in": "..."}`, relation-spanning
`{"primary_owner__role__name": "..."}`, ordering `{"order_by": "..."}`, and —
most relevant to data exposure — `{"format": "xml"}` or `{"format": "jsonp",
"callback": "..."}`. httpx percent-encodes `/` and `..` in query *values*
(confirmed: `order_by=../x` → `order_by=..%2Fx`), so this is not path traversal,
but it is a filter/format injection: a `format` override can change the response
representation (and `redact_secrets` only understands dict/list JSON — a
non-JSON body would pass through unredacted), and relation lookups can surface
fields/objects outside the intended resource. The dedicated list tools
(`gateway_rule.py:63` sets `order_by`, etc.) build their params from typed
kwargs and are not affected; `list_resources` is the open door.

**Fix.** Allow-list permitted filter keys per resource (or at least reject keys
that aren't plain field names — e.g. forbid `format`, `callback`, and anything
not matching `^[a-z][a-z0-9_]*(__[a-z0-9_]+)*$`), and always pin
`format=json` server-side so the response shape (and therefore redaction) is
guaranteed. Reject `__` relation spans unless explicitly intended.

### M7. `redact_secrets` key coverage misses several secret fields that exist in this codebase's resources, and does not cover raw-returning read paths

**Where.** `_helpers.py:68-104` (`_SECRET_KEY_SUFFIXES`, `_SECRET_KEY_EXACT`);
call sites mapped below.

**Coverage gaps.** The suffix/exact sets cover `password`, `*secret`,
`*private_key`, `*passphrase`, `client_secret`, and exact `token`,
`access_token`, `gateway_token`, `key_data`, `pin`, `guest_pin`. But fields that
appear in the gated/registry resources this server exposes are **not** matched:
- `ssh_authorized_key` field is `keydata` (confirmed in test fixture
  `test_security_hardening.py:139` — `{"keydata": "..."}`), not `key_data`, so
  it is **not redacted**.
- `shared_secret` / `psk` (IPsec, backplane) — only `*secret` matches
  `shared_secret` (suffix ok), but `psk` does not.
- `snmp_community` / SNMP v3 auth+priv passwords — `*_community` not matched;
  SNMP v3 `*_password` is matched only if the field literally ends `password`.
- `api_key` — not matched (`_SECRET_KEY_EXACT` has `token` not `api_key`; suffix
  list has no `key`).
- `refresh_token` — not matched (`access_token` is exact-listed but
  `refresh_token` is not; no `*token` suffix).
- TURN/STUN credential fields (`username`/`password` pairs — password matches,
  username does not, which is probably fine).

**Unwrapped read paths.** Not every read path is wrapped. `redact_secrets` wraps
`resource_crud` get/list/create/update returns, `conference.list/get_vmr`,
`device.list/get`, `ldap.list/get`, `global_settings.get`. **Not wrapped:**
`end_user.*` (no secret fields — fine), all of `status.py` and `history.py`
(status/history generally lack config secrets, but `get_resource_schema`,
`get_gateway_rule`, `get_location`, `get_conferencing_node`, `get_ivr_theme`,
and the `create_*`/`update_*` returns in `gateway_rule`, `device` create/update
(device create/update return raw), `conference.create_vmr`/`update_vmr`
(**deliberately** raw per the docstring at `conference.py:71-73`), and
`ldap.create/update` returns). The deliberate raw VMR returns mean a freshly set
`pin`/`guest_pin` is echoed back into model context — acceptable by design but
worth noting it is a standing PIN-in-context exposure. More importantly,
`device.create_device`/`update_device` return `client.get` **without**
`redact_secrets` (`device.py:313-314, 351-352`), so a device `password` set via
create/update is echoed back unredacted, unlike the read paths which do wrap.

**Fix.** Add `keydata`, `api_key`, `refresh_token`, `psk`, `snmp_community`
(and SNMP v3 auth/priv keys) to the secret sets; add a `*key` suffix carefully
(avoid matching `public_key`/`lookup_field`); wrap `device.create/update` (and
`ldap.create/update`, `gateway_rule.create/update`) returns in `redact_secrets`
for parity with the read paths; reconsider whether create/update_vmr needs to
echo the PIN at all (return a boolean "pin_set" instead).

---

## Low

### L1. `_safe_segment` regex permits `.`, `..`-free dotted values and a bare `.`; combined with httpx normalisation this is safe today but brittle

**Where.** `client.py:39-56` — `^[A-Za-z0-9_.-]+$` with a separate `".." not in
text` check.

**Analysis.** The explicit `".." in text` check is what actually stops
traversal; the regex alone would allow `..`. A single `.` passes the regex and
the `..` check (confirmed: `"."` → allowed). A lone `.` as a path segment is a
no-op that httpx collapses (confirmed: `.../conference/./` → `.../conference/`),
so it is harmless in practice, but the safety depends on httpx's dot-segment
normalisation rather than on the validator. `-` and `.` are needed for UUIDs and
float-free ids, so they can't simply be dropped. No encoded-traversal bypass was
found (`%2e%2e`, `%2F` are rejected by the regex; httpx encodes stray `/` in
values). This is defence-in-depth brittleness, not an exploit.

**Fix.** Reject a segment that is exactly `.` or `..` and reject leading/trailing
`.`; keep the character class. Add tests for `"."`, `".."`, `"a."`, `".a"`.

### L2. No MCP session idle-timeout / cap — session table grows unbounded

**Where.** `__main__.py:149-155` builds the session manager via
`mcp.streamable_http_app()` with defaults; the SDK supports
`session_idle_timeout` and it is not set.

**Problem.** Stateful streamable-HTTP sessions are keyed by `mcp-session-id` and
held in `_server_instances` with no expiry unless `session_idle_timeout` is
configured. A client (or attacker past the auth layer) can open sessions without
bound, each holding a task and transport — a slow resource-exhaustion vector.
Compounds H2 (long-lived sessions are exactly what carry the stale principal).

**Fix.** Pass a `session_idle_timeout` and consider a max-session cap; document
that TLS/rate-limiting at the proxy is still required (SECURITY.md:236 already
says so).

### L3. `.env` is auto-loaded from the current working directory

**Where.** `config.py:42` — `SettingsConfigDict(env_file=".env", ...)`;
pydantic-settings resolves `.env` relative to CWD (confirmed:
`Path(env_file).expanduser()` with a relative path).

**Problem.** `PexipSettings()` reads a `.env` from wherever the process happens
to start. For a server launched by an MCP client (Claude Desktop stdio, `uvx`)
the CWD is not necessarily the project dir, so an unrelated `.env` sitting in
that directory — or one planted in a shared working dir — would be read and could
inject `PEXIP_*` values (e.g. flip `PEXIP_READ_ONLY`, point `PEXIP_HOST`
elsewhere, disable TLS). Low severity because env vars already take precedence
and the normal deployment sets them explicitly, but the implicit CWD read is a
foot-gun. `PEXIP_MCP_TOKEN` is read via `os.environ` (`__main__.py:260`), *not*
through `PexipSettings`, so it is not subject to `.env` autoload — a small
inconsistency (the token can't be set in `.env` for the bind guard even though
`.env.example:97` implies it can).

**Fix.** Pin `env_file` to an absolute path derived from a config dir, or gate
`.env` loading behind an explicit flag; make `PEXIP_MCP_TOKEN` consistent (read
it through settings too, or document that it must be a real env var).

### L4. HEALTHCHECK runs with the admin credentials every 30s; Dockerfile is otherwise solid

**Where.** `Dockerfile:49-53`, `docker-compose.yml:73-79`.

**Problem (minor).** The container healthcheck invokes `--healthcheck`, which
builds a `PexipClient` from the admin creds and calls `schema("conference")`
every 30s. This is authenticated admin traffic on a timer; a failure prints
`Pexip API error <status> (ref <id>)` to stderr (no body — good,
`__main__.py:64-66`). Not a leak, but it keeps admin credentials exercised and
produces steady admin-auth log volume on the node. The redaction of the error is
correct. The base image is pinned by digest, the final stage runs as non-root
(`useradd -m -u 1000 mcp; USER mcp`), deps install from the frozen lockfile, and
no secrets are baked into layers (creds come from `env_file`/`-e` at runtime) —
all good.

**Fix (optional).** Point the healthcheck at a cheaper unauthenticated liveness
check, or widen the interval; accept as-is if node-side log volume is fine.

---

## Informational

### I1. Read-only enforcement is correctly applied on both transports *(verified)*

`apply_startup_policy` runs eagerly in `_run_http` (`__main__.py:279-282`) and
again inside `lifespan` for stdio (`mcp_app.py:166-180`); both call
`enforce_read_only` which *unregisters* non-`readOnlyHint` tools from the tool
manager (`mcp_app.py:91-104`). Confirmed empirically over the real HTTP
transport: `tools/list` returned 77 tools, **none** non-read, under the
read-only default, and the SDK's own session lifespan (`lifespan=lambda app:
self.session_manager.run()`) plus the wrapper's delegated lifespan both run. No
tool annotated `read` performs a mutation — every `@mcp.tool(annotations=read…)`
body only calls `client.list/get/schema` or `paginate_all`; all
create/update/delete/command bodies carry `create/update/delete/control`
annotations. So no read-annotated tool can mutate state. The one caveat is H1
(the gates that run *after* read-only is lifted), not read-only itself.

### I2. Upstream error bodies are not leaked to the client *(verified)*

`PexipError(upstream=True)` renders only `status + correlation_id` in its
client-facing string; the body is logged at DEBUG via `.detail()`
(`client.py:92-115, 376-393`). `_fetch_token` wraps token-endpoint failures the
same way (`client.py:520-530`) — a 4xx/5xx from `/oauth/token/` does not expose
`error_description`/`error` to the model. No tool catches `PexipError` and
returns `e.body`; the only `.body` reads are status-code branches
(`disconnect_participant` 404 → friendly note, `command.py:193-199`). Good.

### I3. Audit line forgery via newline injection in the principal is possible but low-impact

`audit.record` (`audit.py:50-69`) builds a space-joined `key=value` line and
logs it. The principal comes from `principal_of(claims)` (OIDC email/upn/sub) or
the credential identity. An IdP that allows a `\n` in an email/`preferred_username`
claim could inject a forged second audit line. The contextvar is reset in a
`finally` (`__main__.py:189-193`), so it does not leak across requests on the
*same* task — but see H2 for the separate cross-session problem. Low: requires a
malicious/permissive IdP.

**Fix.** Sanitise the principal (strip CR/LF, cap length) before logging; prefer
a structured/JSON log formatter over hand-built key=value.

### I4. Dependency pins and supply chain are reasonable

`pyproject.toml` pins `mcp>=1.2.0,<2` (the `<2` is justified — 2.x removed
`mcp.server.fastmcp`), `pyjwt[crypto]>=2.10.1`, etc.; the Docker/MCPB builds
install from the frozen `uv.lock` (`Dockerfile:26-28`, `build.sh`), CI runs
`uv sync --locked` and `uvx pip-audit` (`.github/workflows/ci.yml`). The MCPB
bundle vendors native `cryptography` and is correctly flagged platform-specific.
`isSecret`/`sensitive` flags are set on password and OAuth2 private-key fields in
`server.json`, `packaging/mcpb/manifest.json`, and
`packaging/docker-mcp-registry/server.yaml`. No pinned-but-vulnerable versions
were spotted; `pip-audit` is the live gate (its result is CI-time, not re-run
here — see *Needs human review*).

### I5. A security test asserts a property that this review disputes

`tests/test_security_hardening.py:187-198`
(`test_build_http_app_wrapper_has_lifespan`) asserts only that
`app.router.lifespan_context is not None`. That is a **vacuous** check: a default
`Starlette()` always has a non-None `_DefaultLifespan` (confirmed). The test
therefore does not prove the mounted app's lifespan actually runs — it would pass
even if the delegation at `__main__.py:151-155` were deleted. The real guarantee
comes from `_run_http` calling `apply_startup_policy` eagerly (I1), not from this
test. Recommend strengthening it to assert the inner lifespan is entered (e.g.
that the PexipClient is built / read-only pruning occurred). No security test
asserts anything false, but this one asserts something weaker than its name
claims.

---

## Confirmed strengths

- Read-only is the secure default and is enforced by *removing* tools from the
  catalog on both transports, not by advisory hints (I1, verified empirically).
- Platform-lifecycle *command* tools are gated off by default even with writes
  on (`enforce_platform_gate`); the 14 most obvious privilege/trust *resources*
  are gated (`SENSITIVE_RESOURCES`). H1 is about completeness, not absence.
- Path segments are validated against traversal before f-string interpolation,
  and httpx percent-encodes query values, so no URL traversal was found.
- Upstream (and token-endpoint) error bodies are never returned to the client;
  full detail is DEBUG-logged under a correlation id (I2).
- OIDC uses an asymmetric-only algorithm allow-list, string issuer match,
  https-only JWKS, required `exp/iss/aud`, and fails closed on JWKS errors.
- Static token: min-32-char enforced, constant-time compared (modulo M1's
  non-ASCII edge), and required on non-loopback binds.
- OAuth2-to-Pexip uses a short-lived ES256 JWT assertion, cached/refreshed with a
  lock, with secrets kept out of logs.
- VMR creation is PIN-by-default (`allow_no_pin` opt-in).
- Container: digest-pinned base, non-root user, lockfile install, no secrets in
  layers.

---

## Needs human review (not provable from code alone)

1. **Pexip-side semantics of config-API writes** for `autobackup`,
   `system_backup`, `upgrade`, `software_bundle*`, `licence*`, `management_vm`,
   `policy_server`, `webapp_branding` — does a POST/PATCH actually perform the
   backup/upgrade/restore/branding-deploy, and does the stored credential get
   presented to a changed endpoint on the next sync? H1's ranking assumes it
   does; confirm against the Management API schema for each.
2. **Whether Pexip enforces LDAPS with a pinned/validated CA** for
   `ldap_sync_source`, and TLS cert validation for `smtp_server`/`http_proxy`/
   Exchange/MJX connectors — if it does, the "redirect to attacker host to
   capture the bind credential" vector in H1 is blunted.
3. **Cloudflare Access semantics** — whether the Service Auth / email policies in
   DEPLOY.md actually fail closed, and whether a request can reach
   `127.0.0.1:8000` via the tunnel without passing Access (M4 assumes it can
   under misconfiguration).
4. **Whether the deployed MCP client ever reuses one `mcp-session-id` across
   users** in the shared OIDC topology — H2 is demonstrable in isolation; the
   real-world impact depends on client behaviour and on whether sessions are
   per-user in practice.
5. **`pip-audit` result** — CI runs it; it was not re-executed here. Confirm the
   current lockfile has no known-vulnerable transitive deps at review time.
6. **Pexip Management API `format`/filter handling** (M6) — whether Pexip honours
   a `format=xml`/`jsonp` query override or Django-style relation lookups on the
   admin API; if it ignores them, M6 drops to Low.
