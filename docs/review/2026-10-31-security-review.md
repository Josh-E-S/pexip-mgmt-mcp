# Security review — pexip-mgmt-mcp (2026-10-31)

Adversarial, read-only review of the MCP server exposing the Pexip Infinity
Management API to LLM agents. Threat model as briefed: (1) a prompt-injected or
misbehaving agent trying to escape read-only mode, the platform-tool gate, the
sensitive-resource gate or path-segment validation; (2) unauthenticated or
wrongly-authenticated network clients on `--http`; (3) secret leakage into model
context or logs; (4) supply chain and configuration.

Baseline: `uv run pytest tests/ -q -p no:cacheprovider --no-cov` → **214 passed,
10 xfailed** (green). Installed from lock: `mcp 1.28.1`, `starlette 1.3.1`,
`uvicorn 0.49.0`, `pyjwt 2.13.0`, `httpx 0.28.1`. Findings marked
*empirically confirmed* were reproduced by driving the real ASGI app from
`_build_http_app` with Starlette's `TestClient` (no network, nothing under
`src/`, `tests/`, `evals/` modified).

Severity: **High** = one tool call or one unauthenticated request defeats a
documented control with platform/credential impact; **Medium** = defeats a
documented control under a realistic precondition, or breaks integrity of a
control the docs call authoritative; **Low** = hardening / nuisance-DoS;
**Informational** = accuracy of docs or tests.

---

## High

### H1. Gate coverage: many registry resources and dedicated write tools govern platform trust, credentials or lifecycle but are outside `SENSITIVE_RESOURCES` / `PLATFORM_TOOLS`

**Where.** `src/pexip_mcp/tools/resource_crud.py:31-109` (registry),
`:121-138` (`SENSITIVE_RESOURCES`), `:156-173` (`_guard_sensitive`);
`src/pexip_mcp/mcp_app.py:62-72` (`PLATFORM_TOOLS`); `tools/ldap.py:62-162`,
`tools/global_settings.py:28-52`, `tools/command.py:447-472`.

**Promise.** SECURITY.md:43-56 and `.env.example:176-193` describe the two
opt-in flags as what stands between an injected agent and
"platform access, admin privileges, or trust changes" / "replace or compromise
the whole platform".

**Gap.** With `PEXIP_READ_ONLY=false` and both flags at their defaults, the
following are reachable through plain `create_resource` / `update_resource` /
`delete_resource` or an ungated dedicated tool. Each is argued briefly by the
capability the