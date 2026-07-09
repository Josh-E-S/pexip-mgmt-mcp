# pexip-mgmt-skills

A Claude Code plugin + [Agent Skills](https://agentskills.io) package for operating a **Pexip Infinity** deployment through its management APIs. Bundles the [`pexip-mgmt` MCP server](https://github.com/josh-e-s/pexip-mgmt-mcp) and a curated set of operator runbooks and developer-reference skills.

## What's in here

```
pexip-mgmt-skills/
├── .claude-plugin/plugin.json    Claude Code plugin manifest
├── .mcp.json                     Bundled pexip-mgmt MCP server config
├── spec/                         Agent Skills standard + Pexip conventions
├── template/                     Scaffold for new skills
├── skills/                       The skills, grouped by domain
│   ├── _intake/                  Router skill — start here for open-ended requests
│   ├── operations/               OPERATOR runbooks (use the platform)
│   ├── management-api/           DEVELOPER reference (modify the MCP server)
│   ├── events/                   Event sinks + webhook patterns
│   ├── policy/                   External Policy API
│   └── room-integration/         MJX / One-Touch Join
├── recipes/                      Multi-skill workflows ready to run
└── scripts/                      Install / validate / scaffold tooling
```

## Skill index

| Skill | Domain | Audience |
|---|---|---|
| **pexip-mgmt-intake** | router | both — start here for "I want to use Pexip's management API" |
| **pexip-operations** | operations | operator — kick / lock / report / configure / health-check |
| **pexip-config-api** | management-api | developer — modify Configuration API tool code |
| **pexip-status-api** | management-api | developer — modify Status API tool code |
| **pexip-history-api** | management-api | developer — modify History API tool code |
| **pexip-command-api** | management-api | developer — modify Command API tool code |
| **pexip-event-sinks** | events | both — webhook push events from Pexip |
| **pexip-external-policy** | policy | developer — external policy server hooks |
| **pexip-mjx** | room-integration | both — One-Touch Join for room systems |

See `ARCHITECTURE.md` for design rules. See `CONTRIBUTING.md` for how to add a skill.

## Install

### As a Claude Code plugin (recommended)

```bash
claude --plugin-dir ./pexip-mgmt-skills
```

That gives you all the skills under the `pexip-mgmt:` namespace (`/pexip-mgmt:pexip-operations`, etc.) plus the bundled `pexip-mgmt` MCP server.

Once published to a marketplace, equivalent install:

```bash
/plugin install pexip-mgmt@<marketplace-name>
```

### Individual skills (any Agent Skills host)

Copy whichever skill you want into the host's skills directory. Each `skills/<domain>/<skill-name>/` directory is self-contained:

```bash
cp -r pexip-mgmt-skills/skills/operations/pexip-operations ~/.claude/skills/
```

Works in Claude Code, Gemini CLI, Codex CLI, Cursor, and any other tool that reads the [Agent Skills open standard](https://agentskills.io).

### All skills at once

```bash
./scripts/install.sh ~/.claude/skills/
```

Copies every skill in `skills/**/` into the target directory, flattening the domain grouping (Claude Code expects `<target>/<skill-name>/SKILL.md`).

## Prerequisites

The MCP server config in `.mcp.json` points at the `pexip-mgmt` server (this repo's `src/pexip_mcp/`). Set these env vars before launching:

```bash
export PEXIP_HOST=manager.example.com
export PEXIP_USERNAME=admin
export PEXIP_PASSWORD=...
# Optional:
# export PEXIP_VERIFY_TLS=true
# export PEXIP_TIMEOUT=30
# export PEXIP_MAX_RETRIES=3
# export PEXIP_MCP_DIR=/abs/path/to/pexip-mgmt-mcp
```

If you don't have the MCP server installed, skills still load (the *knowledge* is useful as docs) but tool calls won't have implementations.

## Recipes

Multi-step workflows that compose several skills. Run them by name:

```
/pexip-mgmt:recipe daily-call-report
/pexip-mgmt:recipe kick-and-lock-meeting
/pexip-mgmt:recipe audit-bad-quality-calls
/pexip-mgmt:recipe provision-team-vmr
/pexip-mgmt:recipe webhook-collector-bootstrap
```

See `recipes/` for the full list.

## Roadmap

This package aims to cover **every Pexip Infinity admin and platform API** plus their events. Current state:

- [x] Configuration API — high-level + 4 dev-reference skills
- [x] Status API
- [x] History API
- [x] Command API
- [x] Operator runbook
- [x] Event sinks — webhook push-event config (receiver-side patterns could be expanded)
- [x] External Policy API — via generic CRUD (`policy_server` / `policy_profile`)
- [x] MJX / One-Touch Join — dedicated status tools + CRUD resources
- [ ] Per-resource granular skills (one per VMR / end-user / gateway-rule like Google Workspace's per-API split)
- [ ] Pexip Cloud Connector for MS Teams (CVI)
- [ ] Branding manifest deep-dive
- [ ] Infrastructure / cloud-bursting commands

Contributions welcome. See `CONTRIBUTING.md`.

## Relationship to other packages

- [pexip-mgmt-mcp](https://github.com/josh-e-s/pexip-mgmt-mcp) — the MCP server this package wraps. Server-side admin APIs.

## License

MIT. See `LICENSE`.
