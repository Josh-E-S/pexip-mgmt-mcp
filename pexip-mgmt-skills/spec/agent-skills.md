# Agent Skills open standard

This package follows the [Agent Skills open standard](https://agentskills.io), originally published by Anthropic on 2025-12-18 and adopted by ~32 tools as of 2026 — Claude Code, Google's Gemini CLI, OpenAI's Codex CLI, JetBrains' Junie, AWS's Kiro, Block's Goose, Cursor, and others.

A conforming skill is a directory containing a `SKILL.md` file with YAML frontmatter:

```
my-skill/
├── SKILL.md          # required
├── reference.md      # optional — loaded on demand
├── examples.md
└── scripts/
    └── helper.py
```

## Required frontmatter fields

| Field | Purpose |
|---|---|
| `name` | Skill identifier. kebab-case. Matches directory name. |
| `description` | When to use this skill. Surfaced to the host's matcher. |

## Optional standard fields

| Field | Purpose |
|---|---|
| `license` | SPDX identifier. Lets downstream re-distribute. |

## Progressive disclosure

The host loads only `name` + `description` into context up front. The full `SKILL.md` body is loaded when the host (or user) decides to invoke the skill. Sibling files (`reference.md`, `examples.md`, `scripts/*`) are loaded only when `SKILL.md` directs the agent to read them.

This is the core ergonomic of the standard: a skill bundle can ship a megabyte of detail at near-zero token cost until it's actually needed.

## Authoritative references

- Open-standard homepage: https://agentskills.io
- Anthropic's announcement: https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
- Reference implementations: https://github.com/anthropics/skills
- Claude Code's extensions to the standard: https://code.claude.com/docs/en/skills
- Gemini CLI's implementation: https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/skills.md

## Why we stick to the standard

Host-specific extensions (`allowed-tools`, `disable-model-invocation`, `context: fork`, `paths:`, etc. — see Claude Code's docs) are powerful but lock a skill into one runtime. By using only `name` + `description` + `license`, every skill in this package loads unmodified into any Agent Skills host. Hosts that need extra knobs can layer them via their own settings (Claude Code's `skillOverrides`, project `settings.json`, etc.).

See `pexip-conventions.md` for our local rules on top of the standard.
