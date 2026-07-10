<p align="center">
  <img src="https://raw.githubusercontent.com/Josh-E-S/pexip-mgmt-mcp/main/.github/logo.png" alt="Infinity MCP" width="200">
</p>

# MCP Server for Pexip Infinity

[![CI](https://github.com/Josh-E-S/pexip-mgmt-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/Josh-E-S/pexip-mgmt-mcp/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

<!-- mcp-name: io.github.josh-e-s/pexip-mgmt-mcp -->

MCP (Model Context Protocol) server for the **Pexip Infinity Management API**. It
gives an LLM-based agent everything it needs to manage and operate a Pexip
Infinity deployment in plain language. It exposes **122 curated tools** covering
all four admin API categories: Configuration, Status, History, and Command.

> **Disclaimer:** This is an independent, community-built project. It is **not
> affiliated with, endorsed by, or sponsored by Pexip**. It uses Pexip's public
> Management API and sends **no telemetry or analytics**. The server needs **no
> external network access** beyond the Pexip Management Node you configure, plus
> your own identity provider if you choose to use OIDC. It never sends your data
> anywhere else.

## Quick start

You'll need your Pexip **Management Node hostname** plus credentials. **OAuth2 is
recommended for production**; **basic auth** (admin username + password) is
recommended only for **dev/lab** environments. See
[Configuration](#configuration) to set up an OAuth2 client.

The server starts **read-only** by default: it can list and report, but every
create / update / delete / control tool is removed from the catalog until you
explicitly enable writes. Connect first, confirm it works, then decide.

> **Note:** prebuilt packages are **not yet published**. The one-click bundle and
> the published CLI below ship on release; until then, build the bundle or run
> from source (see [Other ways to run](#other-ways-to-run)).

### ① Claude Desktop: one-click install

The simplest path: no terminal, no JSON.

1. **Download** the `.mcpb` bundle for your OS (**macOS** or **Windows**) from the
   [latest release](https://github.com/Josh-E-S/pexip-mgmt-mcp/releases/latest).
2. **Double-click** it. Claude Desktop opens an install dialog showing the server
   and the permissions it requests.
3. **Fill in the form** with your Management Node **host** and either an **OAuth2
   client** (recommended) or an **admin username + password** (dev/lab only).
   Leave **read-only** on. Click install.
4. **Try it.** Ask Claude: _"List the VMRs on my Pexip node"_ or _"Show me the
   Pexip system status."_

To enable writes later, edit the server in Claude Desktop's settings and turn
**read-only** off.

<!-- Screenshot: Claude Desktop .mcpb install dialog + config form -->

### ② Manual config: Claude Code & other MCP hosts

For Claude Code, Cursor, or any MCP host that takes a JSON server config. Install
the CLI once (`pipx install pexip-mgmt-mcp`, available on release), then add the
server. Use **OAuth2** for production:

```json
{
  "mcpServers": {
    "pexip-mgmt": {
      "command": "pexip-mgmt-mcp",
      "env": {
        "PEXIP_HOST": "pexip-mgr.example.com",
        "PEXIP_AUTH_MODE": "oauth2",
        "PEXIP_OAUTH2_CLIENT_ID": "your-client-id",
        "PEXIP_OAUTH2_PRIVATE_KEY": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
      }
    }
  }
}
```

For **dev/lab**, use basic auth instead: swap the `PEXIP_AUTH_MODE` /
`PEXIP_OAUTH2_*` keys for `"PEXIP_USERNAME": "admin"` and `"PEXIP_PASSWORD": "..."`.
See [Configuration](#configuration) for all options.

- **Enable writes:** add `"PEXIP_READ_ONLY": "false"` to `env` (read-only is the
  default).
- **Claude Code shortcut** (instead of hand-editing JSON):
  ```bash
  # OAuth2 (recommended for production)
  claude mcp add pexip-mgmt \
    -e PEXIP_HOST=pexip-mgr.example.com \
    -e PEXIP_AUTH_MODE=oauth2 \
    -e PEXIP_OAUTH2_CLIENT_ID=your-client-id \
    -e PEXIP_OAUTH2_PRIVATE_KEY="$(cat oauth2_private_key.pem)" \
    -- pexip-mgmt-mcp

  # basic auth (dev/lab only)
  claude mcp add pexip-mgmt \
    -e PEXIP_HOST=pexip-mgr.example.com \
    -e PEXIP_USERNAME=admin \
    -e PEXIP_PASSWORD=... \
    -- pexip-mgmt-mcp
  ```

<!-- Screenshot: Claude Code /mcp showing pexip-mgmt connected -->

### Other ways to run

- **Docker (self-hosted HTTP transport):** run alongside your Infinity; serves
  on `127.0.0.1:8000`, front it with a tunnel/proxy. See [DEPLOY.md](DEPLOY.md).
- **From source (developers):** clone the repo, then:
  ```bash
  pip install -e .
  cp .env.example .env          # edit with your Management Node details
  python -m pexip_mcp --healthcheck
  # OK: connected to pexip-mgr.example.com as admin, schema fetched
  ```
  See [Testing](#testing) for the full dev workflow.

Distribution channels (PyPI, the GHCR Docker image, and marketplace listings for
the official MCP Registry / Docker MCP Catalog) are staged and planned for a
future release.

## Contents

- [Quick start](#quick-start)
- [Coverage](#coverage)
- [How it fits together](#how-it-fits-together)
- [Configuration](#configuration)
- [Quality: the eval suite](#quality-the-eval-suite)
- [Skills SDK](#skills-sdk)
- [Testing](#testing)

## Coverage

| API | Tools | What it covers |
|---|---|---|
| **Configuration** | 46 | VMRs + aliases, end users, devices, gateway rules, automatic participants, IVR themes, LDAP sync, locations + Conferencing Nodes, global settings, schema introspection, plus **generic CRUD** (`list/get/create/update/delete_resource`) over ~70 registry resources: SIP/H.323/MS-SIP proxies, TURN/STUN, Teams Connectors, Azure tenants, Google Meet tokens, MJX (endpoints, integrations, deployments), DNS/NTP/SMTP/syslog/SNMP, certificates (CA/TLS/CSR), admin roles + identity providers, backups + upgrades, web app hosting, policy profiles, and more |
| **Status** | 39 | Live conferences + per-node shards, participants + media streams, per-participant call quality, registrations, node/location status + load stats, backplanes, alarms, licensing, cloud overflow, Exchange scheduler, MJX endpoints + meetings, Teams Connector nodes + calls |
| **History** | 14 | Conference + participant CDRs, server-side aggregation (`summarize_calls`), alarm history, backplane history, registration history, node event history |
| **Command** | 23 | Active call control: dial, disconnect, mute/unmute (participant or all guests), set role, lock/unlock, transfer, layout, messages, LDAP sync, provisioning emails, backup create/restore, certificate import, snapshot, upgrade |

The full catalog with per-tool annotations and parameters is in
[TOOLS.md](TOOLS.md) (regenerate with `uv run python scripts/generate_tools_md.py`).

**This MCP server is designed to optimize tool use.** High-traffic resources
(VMRs, users, devices, rules) get dedicated typed tools; the ~70 remaining
configuration resources share five generic CRUD tools backed by a resource
registry. That keeps the catalog at 122 tools, which lowers per-request token use
and improves the agent's tool selection (verified by the
[eval suite](#quality-the-eval-suite)).

## How it fits together

```mermaid
flowchart LR
    subgraph Agent["MCP client"]
        A["Claude Desktop / Claude Code /<br/>any MCP host"]
    end
    subgraph Server["pexip-mgmt-mcp"]
        B["FastMCP<br/>122 tools + annotations"]
        C["Name → UUID resolution<br/>read-only mode<br/>auto-pagination"]
        D["Async HTTP client<br/>basic / OAuth2 JWT<br/>429-aware retry"]
    end
    subgraph Pexip["Pexip Infinity Management Node"]
        E["Configuration API"]
        F["Status API"]
        G["History API"]
        H["Command API"]
    end
    A -- "stdio / HTTP + bearer" --> B --> C --> D
    D --> E & F & G & H
```

Source layout:

```
src/pexip_mcp/
├── client.py                 # Async PexipClient (all 4 API categories), 429-aware retry
├── config.py                 # PexipSettings (env-driven, pydantic-settings)
├── mcp_app.py                # FastMCP instance + lifespan
├── server.py                 # Imports tool modules to trigger registration
├── __main__.py               # Entry point + --healthcheck + --http
└── tools/
    ├── _helpers.py           # get_client, resolve_id_by_field, paginate_all, annotation presets
    ├── command.py            # Active call control + name→UUID resolvers
    ├── status.py             # Live state + per-participant quality
    ├── history.py            # CDRs + summarize_calls aggregation
    ├── resource_crud.py      # Generic CRUD + resource registry (~70 resources)
    ├── schema.py             # Live schema introspection
    └── conference.py, end_user.py, device.py, gateway_rule.py, alias.py,
        automatic_participant.py, infrastructure.py, ldap.py,
        ivr_theme.py, global_settings.py   # dedicated typed CRUD per resource
```

## Configuration

All env vars are `PEXIP_*` prefixed and loaded from `.env` (or the process
environment). See [.env.example](.env.example) for an annotated template.

| Variable | Default | Purpose |
|---|---|---|
| `PEXIP_HOST` | required | Management Node hostname or IP, no scheme |
| `PEXIP_AUTH_MODE` | `basic` | `oauth2` (recommended for production) or `basic` (dev/lab) |
| `PEXIP_OAUTH2_CLIENT_ID` | oauth2 only | OAuth2 Client ID from the Pexip UI |
| `PEXIP_OAUTH2_PRIVATE_KEY` | oauth2 only | OAuth2 client "Private key" (ES256, shown once) |
| `PEXIP_OAUTH2_TOKEN_URL` | `https://<host>/oauth/token/` | Override the token endpoint |
| `PEXIP_OAUTH2_SCOPE` | `is_admin use_api` | OAuth2 scopes requested |
| `PEXIP_USERNAME` | basic only | Admin username (typically `admin`) |
| `PEXIP_PASSWORD` | basic only | Admin password |
| `PEXIP_VERIFY_TLS` | `true` | Set `false` for self-signed lab nodes |
| `PEXIP_TIMEOUT` | `30` | HTTP timeout in seconds |
| `PEXIP_MAX_RETRIES` | `3` | Retries on 429 rate-limit responses |
| `PEXIP_READ_ONLY` | `true` | Expose only read tools; remove all write/control tools. **On by default;** set `false` to enable writes |
| `PEXIP_ALLOW_SECURITY_RESOURCES` | `false` | Allow generic CRUD to mutate security-critical resources (SSH keys, roles, auth, certs). Only relevant when writes are enabled |
| `PEXIP_ALLOW_PLATFORM_TOOLS` | `false` | Expose platform-lifecycle command tools (backup/restore, upgrade, cert import, software upload, cloud-node start, snapshot). Removed at startup unless enabled, even with writes on |
| `PEXIP_MCP_AUTH_MODE` | `token` | How HTTP clients authenticate to this server: `token` (static bearer) or `oauth` (OIDC). Only affects `--http`. See [docs/identity.md](docs/identity.md) |
| `PEXIP_MCP_TOKEN` | unset | Bearer token for the `--http` transport (required for non-loopback binds; min 32 chars). Run `pexip-mgmt-mcp --generate-token` |
| `PEXIP_OIDC_ISSUER` | unset | Issuer URL; required when `PEXIP_MCP_AUTH_MODE=oauth` (validate OIDC JWTs from your own IdP: Entra/Google/Okta/on-prem) |
| `PEXIP_OIDC_AUDIENCE` | unset | Expected token audience; required when `PEXIP_MCP_AUTH_MODE=oauth` |
| `PEXIP_OIDC_REQUIRED_SCOPES` | unset | Space-separated scopes the JWT must carry (optional) |
| `PEXIP_OIDC_JWKS_URI` | discovered | Override the JWKS endpoint (default: discovered from the issuer) |

### Read-only mode (default)

The server runs in **read-only mode by default**: only the read tools
(list / get / schema) are exposed. Every create, update, delete, and Command-API
control tool is removed from the catalog at startup, so the LLM cannot mutate the
deployment even if it tries. This is enforced server-side: the tools are gone
from the catalog, not merely flagged with an advisory `readOnlyHint`.

To enable the mutating admin surface, set `PEXIP_READ_ONLY=false` (logged loudly
at startup). Even then, generic CRUD refuses to touch security-critical
resources (SSH keys, admin roles/permissions, authentication/SSO, TLS/CA certs)
unless you also set `PEXIP_ALLOW_SECURITY_RESOURCES=true`. Pair writes with a
least-privilege Pexip Administrator Role for defense in depth.

### Authentication: OAuth2 vs basic

Two modes, selected by `PEXIP_AUTH_MODE`:

- **`oauth2`** (recommended for production): an OAuth2 **JWT bearer assertion**
  (ES256). The server signs a short-lived JWT with the client's private key and
  exchanges it at `https://<host>/oauth/token/` for a 1-hour bearer token (cached
  and auto-refreshed). It authenticates once per hour instead of on every request
  and keeps a reusable admin password out of the server's environment.
- **`basic`** (dev/lab only): a local Management Node admin username + password.
  Works out of the box on every Infinity deployment and is the quickest way to
  get started, but sends admin credentials on each request. Not recommended for
  production.

**Set up an OAuth2 client** in the Pexip admin UI under **Users & Devices >
OAuth2 Clients**: add a client, then copy its **Client ID** and **Private key**
(the private key is shown only once). You also enable Management API OAuth2 and
attach an Administrator Role, per Pexip's
[Managing API access via OAuth2](https://docs.pexip.com/admin/managing_API_oauth.htm).
Then set `PEXIP_AUTH_MODE=oauth2`, `PEXIP_OAUTH2_CLIENT_ID`, and
`PEXIP_OAUTH2_PRIVATE_KEY`.

<!-- Screenshot: Pexip admin UI, Users & Devices > OAuth2 Clients -->


## Quality: the eval suite

The [`evals/`](evals/) suite measures whether an LLM can drive these tools
correctly from natural language. It defines **156 scenarios** written as real
admin requests ("mute all the guests in AllHands", "point the syslog server at
10.0.0.99"), graded automatically across three layers:

| Layer | What runs | Cost |
|---|---|---|
| Deterministic (332 checks) | Every eval case is validated against the live tool registry (tools exist, parameter names match signatures) | free, in CI |
| LLM-graded (`--llm`) | Each prompt goes to Claude with the full tool catalog; multi-turn conversations with mocked API responses; graded on tool choice, parameters, and chain order | ~$2 / full run (tool catalog is prompt-cached) |
| Live (`--live`, 33 tests) | CRUD, status reads, and call commands against a real Infinity node, including auto-dialing a test call and moderating it by name | free (your lab) |

Scoring supports exact / subset / ordered-subset / any-of tool matching,
per-step parameter checks with acceptable-alternative values, and optional
steps for chains where server-side name resolution makes a lookup legitimate
but unnecessary. See [evals/README.md](evals/README.md) for the case format
and how to add scenarios.

Current state: the full suite passes: **698 passed, 12 skipped, 0 failures**
across all four layers (208 unit + 332 deterministic eval checks + LLM-graded +
33 live), 86% coverage. The 12 skips are env-gated live cases (e.g. no dial
target set). Reproduce the full run with `uv run pytest tests/ evals/ --llm
--live`, or the free deterministic subset (540 checks) with
`uv run pytest tests/ evals/`.

## Skills SDK

[`pexip-mgmt-skills/`](./pexip-mgmt-skills/) is a self-contained
[Agent Skills](https://agentskills.io) (open standard) + Claude Code plugin
package that wraps this MCP server with operator runbooks and
developer-reference skills. Built to be extractable: `cp -r pexip-mgmt-skills/`
out and you have a complete, plug-installable SDK that loads in Claude Code,
Gemini CLI, Codex CLI, Cursor, or any other compliant host.

Currently ships 9 skills across 6 domains:

| Domain | Skill | Audience |
|---|---|---|
| router | `pexip-mgmt-intake` | both, start here for open-ended requests |
| operations | `pexip-operations` | operator: kick / lock / report / configure |
| management-api | `pexip-config-api` | developer: modify Configuration API tool code |
| management-api | `pexip-status-api` | developer: Status API |
| management-api | `pexip-history-api` | developer: History API |
| management-api | `pexip-command-api` | developer: Command API |
| events | `pexip-event-sinks` | both, configure Pexip's webhook push-event destinations |
| policy | `pexip-external-policy` | developer: external policy server config (via generic CRUD) |
| room-integration | `pexip-mjx` | both, One-Touch Join |

See [`pexip-mgmt-skills/README.md`](./pexip-mgmt-skills/README.md) for the
install instructions and
[`pexip-mgmt-skills/ARCHITECTURE.md`](./pexip-mgmt-skills/ARCHITECTURE.md)
for the design rules. The companion
[awesome-pexip-skills](https://github.com/Josh-E-S/awesome-pexip-skills)
covers the **client-side** (webapp3, `@pexip/infinity`, `@pexip/media`).
Install both for full Pexip coverage.

## Testing

```bash
uv run pytest                  # 208 unit + 332 deterministic eval checks, 86% coverage
uv run pytest tests/           # 208 unit tests (mocked HTTP via respx), ~2s
uv run pytest evals/           # 332 deterministic eval checks, free
uv run pytest evals/ --llm     # LLM-graded evals (needs ANTHROPIC_API_KEY, ~$2)
uv run pytest evals/ --live    # integration against a real node (needs .env)
uv run ruff check src tests evals
```

Every run prints a coverage report, but the **80% gate is enforced only in CI on the
full suite** (`--cov-fail-under=80` in `.github/workflows/ci.yml`), so subset runs
like `uv run pytest evals/` show partial coverage without failing. Unit tests mock
the Pexip Management API with [respx](https://github.com/lundberg/respx); the retry
suite monkeypatches `asyncio.sleep` so backoff tests run instantly.

## License

[MIT](LICENSE)
