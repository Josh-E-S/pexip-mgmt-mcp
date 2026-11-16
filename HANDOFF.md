# Handoff: tool-architecture rework (branch `claude/determined-ride-dgr72l`)

Written 16 Nov 2026 for the Claude instance working on Josh's machine. You are
on the pre-rework code (`main` at `e305f2e`, 122 unprefixed tools). Everything
below lives on one branch, pushed to `Josh-E-S/pexip-mgmt-mcp`. `main` has not
been touched. No pull request has been opened.

## 1. Get the code

```bash
git fetch origin
git checkout claude/determined-ride-dgr72l
uv sync --locked
uv run ruff check . && uv run pytest -q      # expect 673 passed, 181 skipped, 2 xfailed
```

Keep committing on this branch and push with `git push -u origin claude/determined-ride-dgr72l`.
Never force-push it. Merge to `main` only when Josh asks (open a PR from this
branch; the repo has no PR template).

## 2. What changed, in one screen

| | `main` (`e305f2e`) | this branch (`f4761a2`) |
|---|---|---|
| Tools in catalog | 122, unprefixed | 72, all `pexip_*` |
| Tools in a default session | 122 | ~60 (toolsets `default`) |
| Est. tokens for the full catalog | ~22k | ~20.5k |
| Tests | 208 unit + evals | 673 passing, lint clean, coverage gate 80% |
| `mcp` SDK | unpinned (2.x breaks import) | `mcp>=1.2.0,<2`, Docker/MCPB install from `uv.lock` |

17 commits, 119 files. The design and the per-phase status live in
`docs/TOOL-ARCHITECTURE-PLAN.md` (sections 5a onward are the status log).

### Breaking changes you will hit on your local MCP config

1. **Tool names are prefixed `pexip_`** (`list_vmrs` is now `pexip_list_vmrs`).
   Set `PEXIP_LEGACY_TOOL_NAMES=true` to also register the old names as aliases
   while you migrate prompts and skills. It doubles the catalog, so turn it off
   when done.
2. **Toolsets.** `PEXIP_TOOLSETS=default` exposes core, rooms, directory, config,
   live, health, history. `dialplan` (gateway rules, locations, node config) and
   `platform` are off unless listed, e.g. `PEXIP_TOOLSETS=default,dialplan` or
   `all`. `PEXIP_TOOLS` adds single tools, `PEXIP_DENY_TOOLS` removes them.
3. **~50 typed tools were folded**, not renamed. Their functionality is reached
   through generic tools that take a `resource` name:
   - configuration CRUD: `pexip_list_resources` / `pexip_get_resource` /
     `pexip_create_resource` / `pexip_update_resource` / `pexip_delete_resource`
     (now also covers `global`, `ivr_theme`, `ldap_sync_source`; `global` and
     `ivr_theme` refuse create/delete).
   - status: `pexip_list_status(resource=...)` / `pexip_get_status(...)`.
   - history: `pexip_list_history(resource=...)` / `pexip_get_history(...)`.
   - `pexip_describe_resources(api=..., query=...)` tells the model which
     resource names exist, their filters, and which dedicated tool to prefer.
   - platform lifecycle commands collapsed into
     `pexip_run_platform_command(command=..., params=...)` (still gated by
     `PEXIP_ALLOW_PLATFORM_TOOLS`).
   - `send_device_email` + `send_vmr_email` became
     `pexip_send_provisioning_email(target="vmr"|"device", target_id=...)`.
4. **Live-control tools take names.** `pexip_mute_participant(participant="Alice")`
   resolves to the UUID server-side; `conference` likewise. UUIDs still work.
5. **Responses are shaped.** List tools return `{"objects": [...], "meta": {...}}`
   with `response_format="concise"` by default (`"detailed"` or an explicit
   `fields` list for more) and a 50 KB byte cap (`PEXIP_MAX_RESPONSE_BYTES`);
   `meta.has_more` / `meta.truncated` plus a hint say when to narrow.
6. **HTTP transport** (`--http`) gained `PEXIP_MCP_PUBLIC_URL`,
   `PEXIP_MCP_ALLOWED_HOSTS`, `PEXIP_MCP_ALLOWED_ORIGINS`. A tunnel or reverse
   proxy hostname must be in `PEXIP_MCP_ALLOWED_HOSTS` or the SDK answers 421.
   stdio is unaffected.

`TOOLS.md` is the generated full catalog (`uv run python scripts/generate_tools_md.py`).
`pexip-mgmt-skills/` (the skills package) is already migrated to the new names.

## 3. Where things are

| Area | Files |
|---|---|
| Server subclass, prefixing, gates, startup policy | `src/pexip_mcp/mcp_app.py` |
| Toolsets, resource registries (status/history), platform gate list | `src/pexip_mcp/tools/_catalog.py` |
| Per-tool guidance (use_when / avoid / docs / examples), rendered into descriptions | `src/pexip_mcp/tools/_guidance.py` |
| Response shaping, byte cap, concise field sets | `src/pexip_mcp/tools/_shaping.py` |
| Shared generic list/get implementation | `src/pexip_mcp/tools/_generic.py`, wrappers `status_generic.py`, `history_generic.py` |
| Discovery tool + `pexip://registry`, `pexip://schema/{resource}` resources | `src/pexip_mcp/tools/discovery.py` |
| `pexip_get_platform_health` workflow tool | `src/pexip_mcp/tools/health.py` |
| Generic config CRUD, filter validation, singleton guards | `src/pexip_mcp/tools/resource_crud.py` |
| HTTP auth gates, transport security | `src/pexip_mcp/__main__.py` |
| Settings (new: toolsets, tools, deny_tools, mcp_public_url, allowed hosts/origins) | `src/pexip_mcp/config.py` |
| Catalog quality lint (Glama rubric + Claude directory checklist as tests) | `tests/test_catalog_quality.py` |
| Eval-coverage ratchet (every tool needs an eval case) | `tests/test_eval_coverage.py` |
| Eval harness: cache-usage recorder, scorecard | `evals/conftest.py`, `evals/catalog.py`, `evals/baseline/*.json` |
| Catalog size report | `scripts/catalog_stats.py --as-deployed` |
| Review findings that drove phases 1-4 | `docs/review/2026-10-31-*.md` |

## 4. Conventions that the tests enforce

- Every tool: `pexip_` prefix, title, `readOnlyHint` or `destructiveHint`,
  description 120-1500 chars containing "use when", an entry in `GUIDANCE`
  (`_guidance.py`), `input_examples` when it has 4+ optional params, a toolset
  in `TOOLSET_OF`, and at least one eval case under `evals/cases/`. Adding a
  tool without these fails `tests/test_catalog_quality.py` or
  `tests/test_eval_coverage.py`.
- Descriptions may only name tools that are registered (stale names fail a test).
- Two `xfail(strict=True)` remain in `test_catalog_quality.py`: output schema on
  get tools, and near-duplicate names. Remove the marker when the work lands.
- Guidance strings use single quotes inside; FastMCP strips unknown keys from
  structured output, so `ListMeta` must stay exhaustive.
- Eval runs with `--llm` record prompt-cache hit rate and warn below 80%;
  `PEXIP_EVAL_SCORECARD_JSON=path` and `PEXIP_EVAL_USAGE_JSON=path` write the
  numbers out. Run the eval suite with caching on (it is the default in
  `evals/conftest.py`); a cold cache makes the cost figures meaningless.

## 5. Open work, in priority order

### 5.1 Needs the lab (Josh will drive, you assist)

`docs/review/MANUAL-REVIEW-QUEUE.md` has 14 rows of field names, enum values and
payload shapes that could not be verified from the repo, because the mocked
tests pin whatever the code sends. The fastest check for most rows is
`pexip_get_resource_schema("<resource>")` against the lab node. For each row the
outcome is: works as is (close it), wrong field (fix code + test fixture + eval
case together), or capability missing (add a typed parameter). Note the Infinity
version when fixing; field names drift between releases.

Highest value rows: #1 (`set_conference_layout` codes vs names), #2 (FK-URI
filters on 7 list tools; if wrong, location/VMR-scoped lists silently return
everything), #6 (participant media stream path), #7 (dial_participant enums),
#9/#14 (device provisioning email payload).

### 5.2 Needs an API key or the lab (not run from the sandbox)

- LLM eval baseline, both sides, so the consolidation has before/after numbers:
  ```bash
  git checkout b67386f && PEXIP_EVAL_SCORECARD_JSON=/tmp/before.json uv run pytest evals/ --llm
  git checkout claude/determined-ride-dgr72l && PEXIP_EVAL_SCORECARD_JSON=/tmp/after.json uv run pytest evals/ --llm
  ```
  Then `uv run pytest evals/ --live` against the lab. Compare tool-selection and
  parameter accuracy; the compact-mode work (phase 5) is gated on these numbers.
- `docker build .` once (the Dockerfile now installs from `uv.lock`; the sandbox
  had no daemon).
- Check the Glama listing tier after the branch merges.

### 5.3 Deliberately not started

- Phase 5: compact description mode, mutation-consent elicitation, per-toolset
  OIDC scopes. Wait for the eval numbers.
- Phase 6: migrate to MCP SDK 2.x (`FastMCP` became `MCPServer`,
  `mcp.server.fastmcp` removed), stateless HTTP, publish to PyPI / MCP registry /
  Claude directory. Bump the `mcp<2` pin only as part of this.
- Smaller debt: FK-name resolution in concise mode (show a location name, not
  its URI), dependabot `uv` ecosystem (it still watches `pip`), de-duplicating
  the shaping path between `shape_list` and `finalize_result`.

## 6. Things that bit us (so you do not repeat them)

- `mcp` 2.x installs by default on a fresh machine and breaks the import; the
  pin and the lock-based installs are the fix. CI has an unlocked-install smoke job.
- The platform gate compared bare names after the prefix was added and removed
  nothing; gates now compare `name.removeprefix("pexip_")`.
- The byte cap must measure the indented JSON FastMCP actually sends, not
  compact JSON.
- Licensing status uses `<kind>_count` / `<kind>_total`, not `used` / `total`.
- History time fields differ per resource (`time_raised` for alarms, `time` for
  node events); the registry carries them, do not hard-code `start_time`.
- `PEXIP_TOOLSETS` enforcement prunes the shared tool registry; the HTTP test
  fixture sets `PEXIP_TOOLSETS=all` and resets `mcp._session_manager`.
