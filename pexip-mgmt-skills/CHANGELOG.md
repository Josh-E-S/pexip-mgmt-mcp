# Changelog

All notable changes to this package. Follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added

- Initial package scaffolding: plugin manifest, `.mcp.json`, README, ARCHITECTURE, CONTRIBUTING, spec/, template/, scripts/.
- Skills migrated from `.claude/skills/`:
  - `pexip-operations` (operator runbook, refactored from `references/` subdirs to sibling files).
  - `pexip-config-api`, `pexip-status-api`, `pexip-history-api`, `pexip-command-api` (developer reference per admin API).
- New skills:
  - `pexip-mgmt-intake` (router skill — asks 2-3 scoping questions, routes to the right tier-2 skill).
  - `pexip-event-sinks` (webhook push-event configuration and receiver patterns).
  - `pexip-external-policy` (external policy server config via generic CRUD, plus receiver-side guidance).
  - `pexip-mjx` (One-Touch Join for room systems).
- Recipes:
  - `daily-call-report` — pull a daily usage report via `summarize_calls` and format as Markdown.
  - `kick-and-lock-meeting` — live ops playbook with safety prompts.
  - `audit-bad-quality-calls` — quality forensics over a time window.
  - `provision-team-vmr` — new VMR + aliases + automatic participant in one flow.
  - `webhook-collector-bootstrap` — event sink setup guide + secure receiver skeleton.
- Scripts: `install.sh`, `validate-skills.py`, `new-skill.sh`.

## [0.1.0] — TBD

First tagged release once the Phase 1 skills are flushed out and validated against a real Pexip Infinity deployment.
