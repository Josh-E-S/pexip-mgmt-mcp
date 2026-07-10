# Contributing

Adding a skill to `pexip-mgmt-skills`. Read `ARCHITECTURE.md` first for the design rules.

## Scaffold a new skill

```bash
./scripts/new-skill.sh <domain> <skill-name>
# e.g.
./scripts/new-skill.sh events pexip-event-replay
```

Creates `skills/<domain>/<skill-name>/SKILL.md` from `template/new-skill/`. The template's frontmatter, "Reference source" footer, and sectioning all match the conventions.

## Workflow

1. **Pick the right domain folder.** See the table in `README.md`. If your skill doesn't fit, propose a new domain in your PR — don't drop it at the top level.
2. **Write `SKILL.md` first.** Keep it under 250 lines. State *when to use* and *when not to use* prominently. List trigger symbols (API endpoint names, MCP tool names) in the description so the host can match user requests.
3. **Push detail into sibling files.** If the skill grows past 250 lines, split per-workflow detail into `<skill>/<workflow>.md` files and reference them from `SKILL.md`.
4. **Add a "Reference source" footer** linking to the authoritative Pexip doc URL and the relevant MCP server source file.
5. **Validate.**
   ```bash
   ./scripts/validate-skills.py
   ```
6. **Bump `CHANGELOG.md`.**
7. **Open a PR.**

## Frontmatter checklist

Every `SKILL.md` must start with:

```yaml
---
name: pexip-<short-name>
description: Use when … Triggers on <symbol-list>. Do NOT use for <anti-trigger>.
license: MIT
---
```

- `name` matches the directory name exactly.
- Description leads with "Use when…", then trigger symbols, then anti-triggers.
- Combined `description` + `when_to_use` ≤ 1,536 characters (run the validator).
- No host-specific keys (`allowed-tools`, `disable-model-invocation`, etc.). See `spec/pexip-conventions.md`.

## Body structure

A consistent shape readers can predict:

```markdown
# <Skill Name>

<One-paragraph what-and-why.>

## When to use

<3-5 bullets, concrete.>

## Field gotchas / safety notes
<…>

## Reference source
- Authoritative Pexip docs: <URL>
- MCP server source: `src/pexip_mcp/tools/<file>.py`
- Related skills: <sibling skill names>
```

Not every skill needs every section, but the order should be predictable.

## Coverage queue

The Phase-2 list from `README.md`'s roadmap is the priority queue for new skills:

- Per-resource splits: `pexip-vmrs`, `pexip-end-users`, `pexip-gateway-rules`, `pexip-ldap-sync`, `pexip-licensing`, `pexip-alarms`, `pexip-conferencing-nodes`
- New domains: `pexip-cvi-teams`, `pexip-branding-manifest`, `pexip-infrastructure-commands`
- Expand the thinner runbooks with more worked examples: `pexip-event-sinks`, `pexip-external-policy`, `pexip-mjx`

Pick from the queue or propose a new one in an issue first.

## Code style for scripts

- Bash scripts: `#!/usr/bin/env bash`, `set -euo pipefail`, prefer POSIX-ish constructs that work on macOS bash 3.2.
- Python scripts: target Python 3.10+, no external deps unless absolutely necessary. Self-contained `#!/usr/bin/env python3` scripts the user can run without setting up an environment.

## License

By contributing you agree your work is released under MIT (matching the package).
