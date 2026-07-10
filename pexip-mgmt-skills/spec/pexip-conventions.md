# Pexip-mgmt-skills conventions

Local rules on top of the [Agent Skills open standard](./agent-skills.md). The validator (`./scripts/validate-skills.py`) enforces these.

## 1. Frontmatter

Exactly these three keys, in this order:

```yaml
---
name: pexip-<short-name>
description: Use when … Triggers on <symbol-list>. Do NOT use for <anti-trigger>.
license: MIT
---
```

- `name` is kebab-case, prefixed `pexip-`, matches the directory name.
- `description` ≤ 1,536 chars (the Claude Code skill-listing budget cap; safe for any host).
- `license` is `MIT` for everything in this package.

No other frontmatter keys. Host-specific behavior (allowed tools, model invocation rules) belongs in host settings, not in the skill file.

## 2. Directory layout per skill

Flat. No subdirectories inside a skill directory:

```
skills/<domain>/<skill-name>/
├── SKILL.md              # required
├── <topic>.md            # optional sibling detail docs
├── <name>.json           # optional reference data
└── <name>.sh / .py       # optional helper scripts
```

Why flat: one less click to read; easier for the agent to know what's there.

## 3. SKILL.md body shape

Predictable section order so a reader can scan:

```markdown
# <Skill Name>

<One-paragraph what-and-why.>

## When to use
<3-5 bullets, concrete.>

## Field gotchas / safety notes
<one or both, depending on the skill>

## Reference source
- Authoritative Pexip docs: <URL>
- MCP server source: `src/pexip_mcp/tools/<file>.py`
- Related skills: <names>
```

Not every skill needs every section, but the order should be the same.

## 4. Description style

Lead with **when**, then **triggers**, then **anti-triggers**:

> Use when modifying or extending the MCP server's wrappers around the Pexip Configuration API — CRUD on VMRs, aliases, end users, gateway rules, system locations, conferencing nodes, automatic participants, LDAP sync sources, IVR themes, global settings. Triggers on `/api/admin/configuration/v1/`, `conference`, `conference_alias`, `end_user`, `system_location`, `gateway_routing_rule`, `worker_vm`, `automatic_participant`, `ldap_sync_source`, `ivr_theme`, `tools/conference.py`, `tools/alias.py`. Do NOT use for live in-progress meetings (use `pexip-command-api` / `pexip-status-api`) or post-call data (use `pexip-history-api`).

Concrete API symbols and source-file paths help hosts match precisely. Anti-triggers prevent two skills both firing on overlapping requests.

## 5. Sizing

| Component | Target | Hard ceiling |
|---|---|---|
| `description` + `when_to_use` | < 800 chars | 1,536 chars |
| `SKILL.md` body | < 250 lines | 500 lines |
| Sibling `.md` per file | < 300 lines | none |
| Scripts | as small as the task allows | none |
| Asset JSON | < 200 lines | none |

Over the ceiling? Split. Two focused skills beat one bloated one.

## 6. Naming

- Domain folders: lowercase, kebab if multi-word (`management-api`, `room-integration`).
- Skill folders: lowercase kebab-case, prefixed `pexip-`.
- Sibling docs: lowercase kebab-case, no `pexip-` prefix (they're scoped to the skill).
- Scripts: lowercase, snake_case or kebab-case. Match the existing style in the skill.

## 7. "Reference source" footer

Mandatory. Every SKILL.md and every sibling doc ends with the canonical doc URL it draws from. This is non-negotiable — it's how a reader verifies the skill against ground truth and how the next maintainer knows where the content came from.

## 8. Cross-skill references

Inline, by name, not by path:

> For confirmation rules before destructive operations, see `pexip-operations/safety.md`.

The reader (human or agent) resolves the path from the skill name. Paths break when files move; names don't.

## 9. What we don't do

- **No host-specific frontmatter.** No `allowed-tools`, no `disable-model-invocation`, no `context: fork`, no `paths:`, no `hooks:`. These are host concerns; users layer them via host settings.
- **No subdirectories inside a skill.** Flat is faster to read and scan.
- **No skills without a Reference source.** A skill that can't cite its source is not finished.
- **No "future-proofing" sections.** If a feature isn't implemented yet, don't document it as if it were.
