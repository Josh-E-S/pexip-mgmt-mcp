# Architecture

How `pexip-mgmt-skills` is laid out and why. Read this if you're contributing a skill or reorganizing existing ones.

## Design principles

1. **One skill per coherent concept.** A skill should answer one kind of question well. Not "all of Pexip" and not "one HTTP endpoint".
2. **Progressive disclosure.** `SKILL.md` stays small (target < 250 lines). Detail lives in sibling `.md` files that load only when the agent needs them.
3. **Self-contained directories.** Every skill folder ships everything it needs (instructions, sub-docs, scripts, assets). Copy-paste portable to any Agent Skills host.
4. **Open-standard frontmatter.** Use only fields from the [Agent Skills spec](https://agentskills.io): `name`, `description`, `license`. No host-specific extensions in the canonical SKILL.md.
5. **Two audiences, two skill flavors.**
   - **Operator runbooks** (`skills/operations/`) — tell the agent how to *use* the MCP server to do real work. Phrased as playbooks.
   - **Developer reference** (`skills/management-api/`) — tell the agent how to *modify the MCP server's code* for a given API surface. Phrased as API docs.

## Directory layout

```
pexip-mgmt-skills/
├── .claude-plugin/plugin.json    # Plugin manifest (installable as /plugin install pexip-mgmt)
├── .mcp.json                     # Bundled MCP server config (Claude Code reads this)
├── README.md                     # Index + install + roadmap
├── ARCHITECTURE.md               # This file
├── CONTRIBUTING.md               # How to add a skill
├── CHANGELOG.md                  # Versioned changes
├── LICENSE                       # MIT
├── spec/                         # Standards reference
│   ├── agent-skills.md           # Pinned link to the open standard
│   └── pexip-conventions.md      # Our local rules on top of the spec
├── template/                     # Scaffold for new skills
│   └── new-skill/                # `./scripts/new-skill.sh foo` copies this
├── skills/                       # Skills, grouped by domain
│   ├── _intake/                  # Router skills, always loaded first
│   ├── operations/               # Operator playbooks
│   ├── management-api/           # Developer reference per admin API
│   ├── events/                   # Event sinks / webhooks
│   ├── policy/                   # External Policy API
│   └── room-integration/         # MJX / room systems
└── scripts/                      # Repo-wide tooling
```

### Why domain folders under `skills/`

Matches [anthropics/skills](https://github.com/anthropics/skills) (Creative & Design, Document Skills, Enterprise & Communication, etc.). Helps human navigation as the SDK grows past ~20 skills. **Domain folders are organizational only** — Claude Code and other hosts still discover skills by walking to the `SKILL.md` file; the domain folder name doesn't appear in the skill identifier.

### Why a leading underscore on `_intake/`

The `_` keeps router skills sorted to the top of file listings. Convention only; not load-bearing.

## Skill anatomy

Every skill is a directory with at minimum:

```
my-skill/
└── SKILL.md          # Frontmatter + body. REQUIRED.
```

Larger skills add sibling files (no subdirectories — flat is easier to navigate):

```
my-skill/
├── SKILL.md          # Entry point — short, links to siblings.
├── detail-a.md       # Detail doc, loaded on demand.
├── detail-b.md
├── cheatsheet.json   # Reference data.
└── helper.sh         # Optional script.
```

The agent loads `SKILL.md` first, then loads sibling `.md` files only when the work matches. Reference siblings from `SKILL.md` with brief explanations of when to read each.

See `template/new-skill/` for a working scaffold.

## Frontmatter conventions

The three required fields:

```yaml
---
name: pexip-foo
description: Use when …. Triggers on <symbol1>, <symbol2>, …. Do NOT use for ….
license: MIT
---
```

### `name`

- kebab-case
- Prefixed `pexip-` for discoverability
- Matches the directory name
- Max 64 chars (Claude Code limit, lower in practice)

### `description`

- Lead with **when to use it** ("Use when…")
- Then list **trigger symbols** — API method names, tool names, error messages the user might paste
- End with **anti-triggers** ("Do NOT use for…") to keep loading precision high

Why the symbol-stuffing: hosts use the description to decide whether to surface a skill. Listing concrete identifiers (`onPeerDisconnect`, `summarize_calls`, `list_active_participants`) matches the user's actual phrasing better than abstract verbs ("control meetings").

Hard cap: 1,536 characters combined `description` + `when_to_use` (Claude Code's listing budget). Keep it tight.

### `license`

Always `MIT` for this package. Lets downstream re-distribute without checking each skill.

### What we DON'T put in frontmatter

To stay open-standard-portable, we avoid Claude-Code-specific keys:
- `allowed-tools` — host-specific
- `disable-model-invocation` / `user-invocable` — host-specific
- `context: fork`, `agent:` — host-specific
- `paths:` — host-specific
- `hooks:` — host-specific
- `argument-hint`, `arguments` — host-specific
- `model`, `effort` — host-specific

A host that supports these can layer them via its own settings (`skillOverrides`, project `settings.json`).

## Sizing rules

| Component | Target | Hard ceiling |
|---|---|---|
| `description` + `when_to_use` | < 800 chars | 1,536 chars |
| `SKILL.md` body | < 250 lines | 500 lines |
| Sibling `.md` per file | < 300 lines | none (loaded on demand) |
| Scripts | as small as the task allows | none |
| Asset JSON | < 200 lines | none |

Over the ceiling? Split into more skills. Splitting is cheap; one giant skill is hard to discover and expensive in context.

## Routing between skills

Skills can refer to other skills by name. `pexip-mgmt-intake` is the canonical router — it asks 2-3 scoping questions and points the agent at the right tier-2 skill. Inline cross-links inside a SKILL.md body are fine too:

> For the post-call equivalent of this analysis, see `pexip-operations/reporting.md`.

Avoid hard dependencies between skills (no "you must read X first"). Each skill should be self-sufficient.

## "Reference source" footer

Every SKILL.md ends with a section pointing at:

1. The **authoritative Pexip doc URL** for the API surface this skill covers
2. The **source file** in the MCP server (e.g., `src/pexip_mcp/tools/conference.py`) if applicable

This lets a human (or another agent) verify the skill against ground truth quickly.

## Validation

`./scripts/validate-skills.py` lints every `skills/**/SKILL.md`:

- Frontmatter has the three required fields
- `name` matches the directory name
- `description` + `when_to_use` ≤ 1,536 chars
- Body has a final "Reference source" or "Authoritative docs" section
- No host-specific frontmatter keys

Run it before pushing changes.

## Skill organization

Skills are grouped under **domain folders** (`skills/<domain>/<skill-name>/`) rather than a flat `skills/`, because the package is designed to grow to 30+ skills (per-resource: `pexip-vmrs`, `pexip-end-users`, …). Domain folders pre-organize that growth; on install the domain folder is flattened so hosts see `<skill-name>/SKILL.md`.
