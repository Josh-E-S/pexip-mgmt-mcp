# Tool architecture plan: making pexip-mgmt-mcp a top-ranked MCP server

Status: proposal, 24 Oct 2026. Scope is the tool surface and how it is validated. Packaging, SDK pin, and doc fixes from the 24 Oct review are prerequisites but are out of scope here.

## 1. Where we stand (measured)

| Measure | Today |
|---|---|
| Tools in catalog | 122 (46 config, 39 status, 14 history, 23 command) |
| Catalog size (names + descriptions + schemas) | 82 KB JSON, roughly 23k tokens by chars/3.6; the evals README measured ~36k with the Anthropic tokenizer |
| Heaviest module | Status: 39 tools, ~5k tokens, almost all `list_X` / `get_X` pairs |
| Heaviest single tool | `list_resources` (~770 tokens; a 2,196-char description that inlines the whole resource registry) |
| Description length | min 33 chars, median 134, max 2,196 |
| Naming | no service prefix; `conference_id` means a UUID in some tools and an integer in others (`send_conference_email`) |
| Output | `dict[str, Any]` everywhere, so no `outputSchema`; full Pexip records returned; no concise mode; no byte cap |
| Read/write split | clean: every tool is one of read / create / update / delete / control |
| Safety | server-side read-only gate, platform-tool gate, sensitive-resource gate, audit, redaction |
| Evals | 156 scenarios: deterministic + LLM-graded + live; tool-choice and parameter scoring; no end-to-end answer accuracy, no token or tool-call metrics recorded |

What is already strong: the generic-CRUD-over-a-registry pattern for config, name resolution, annotations on every tool, and the eval harness. The plan below extends those three ideas to the whole server rather than replacing them.

## 2. What "top" means in October 2026

Three audiences score an MCP server, and they want different things.

**Models.** Anthropic's published guidance (Writing tools for agents; Advanced tool use; Tool Search Tool docs) is consistent: tool-selection accuracy degrades past 30 to 50 loaded tools; consolidate overlapping tools; prefix names by service so one search matches the group; return high-signal fields and resolve IDs to names; offer `response_format` concise/detailed (their Slack example cut tokens to about a third); paginate and truncate with a hint on how to narrow; write errors that say how to fix; add `input_examples` for formats JSON Schema cannot express (72% to 90% on complex parameters internally); keep tools independent and idempotent so programmatic callers can run them in parallel. Measure with held-out tasks, tracking accuracy, tool calls, tokens, and tool errors, and read the transcripts.

**Directories.** Glama scores 70% Tool Definition Quality (purpose clarity 25, usage guidelines 20, behavioral transparency 20, parameter semantics 15, conciseness 10, contextual completeness 10) weighted toward the weakest tool, plus 30% Server Coherence (disambiguation, naming consistency, tool-count appropriateness, completeness). Tier A is 3.5 or better. The Claude Connectors Directory review checklist rejects a tool that mixes safe and unsafe HTTP methods behind a `method` parameter, requires `title` plus `readOnlyHint`/`destructiveHint` on every tool, requires freeform-payload tools to name or link the target API, requires actionable errors and right-sized responses, and only accepts remote HTTPS servers (MCPB listings are deprecated; local servers go in a plugin).

**Peers with huge APIs.** How the large-surface servers keep tool counts sane:

| Server | Pattern | Tool count |
|---|---|---|
| GitHub (official) | Toolsets as allow-lists (`--toolsets`, env, `X-MCP-Toolsets` header, `/x/{toolset}` path); default set of 5 toolsets; `--tools` for individual tools; read-only filter applied after toolset expansion; consolidated tools with a `method` parameter; description overrides via config | 22 toolsets |
| Azure (official) | `namespace` mode: one tool per service, `command` + `intent` + `learn=true` for discovery (~30 tools); `single` mode: one `azure` tool; `consolidated` mode: intent-named tools; `all`: 200+. Rationale: VS Code's 128-tool cap | 1 / ~30 / 200+ |
| Kubernetes (containers/) | Generic `resources_list/get/create_or_update/delete` taking kind + apiVersion, plus typed `pods_*`, `nodes_*` for hot paths; 12 toolsets; `denied_resources`; `max_backend_response_bytes`; default log line caps | ~76 |
| AWS API MCP | Two tools: `suggest_aws_commands` (NL to candidates) + `call_aws`; denylist, `elicitList`, `REQUIRE_MUTATION_CONSENT` via elicitation; read-only by IAM access level | 2 to 3 |
| Stripe (hosted) | `stripe_api_search` + `stripe_api_details` for discovery, generic `stripe_api_read` / `stripe_api_write` covering ~150 methods, `search_stripe_documentation`; risky writes need a human confirmation URL | 9 to 15 |
| Cloudflare Code Mode | `search` over the OpenAPI document inside a sandbox, `execute` runs generated code; only the subset reaches context | 2 |
| Shopify Dev | `learn_shopify_api` entry point, docs search, filtered schema introspection, validation tool as guardrail | 4 to 5 |
| Sentry | Natural-language `search_*` tools, "skills" to enable/disable groups, explicitly not exhaustive | ~20 |

The convergent design: **a declarative catalog, a small always-on core, discovery tools instead of giant descriptions, generic read/write tools over a registry for the long tail, typed tools only for hot paths, and toolsets to shape what any one session sees.** Your config layer already does half of this; the plan makes it the whole server.

## 3. Target architecture

### 3.1 One declarative catalog, three rendered modes

Replace "122 decorated functions" with a single `CATALOG` (Python data, not YAML, so it stays type-checked) describing every resource across all four Pexip APIs:

```
ResourceSpec(
  name="worker_vm", api="status", label="Conferencing Node status",
  toolset="health", lookup_field="name", supports_fetch_all=True,
  concise_fields=("name", "node_type", "media_load", "max_media_load", "system_location", "version"),
  fk_fields={"system_location": "system_location"},   # resolved to names in concise mode
  filters=("name__icontains", "system_location"),
  keywords=("node", "load", "media", "capacity"),       # feeds descriptions and tool search
)
```

From that catalog the server renders a tool surface in one of three modes, selected by `PEXIP_TOOL_MODE`:

| Mode | What is registered | For |
|---|---|---|
| `toolsets` (default) | Typed hot-path tools + generic read/write tools, filtered by `PEXIP_TOOLSETS` | Claude Desktop, Claude Code, Cursor, remote connector |
| `all` | Every typed tool for every resource (today's shape, renamed) | Clients with tool search; evals A/B baseline |
| `compact` | 2 tools per API (read + write) plus discovery, about 10 tools | Hosts with hard tool caps (VS Code 128) and multi-server setups |

All three modes share one implementation per operation, so a bug fix lands everywhere and the eval suite runs against each mode with the same cases. `compact` keeps read and write in separate tools (`pexip_config_read(resource, op=list|get)` vs `pexip_config_write(resource, op=create|update|delete)`), which is what the Claude directory rule requires and what Azure's `single` mode would fail.

### 3.2 Toolsets

| Toolset | Contents | Default on |
|---|---|---|
| `core` | `pexip_describe_resources`, `pexip_get_schema`, `pexip_get_platform_health` | always |
| `rooms` | VMR CRUD, aliases, automatic participants (typed) | yes |
| `directory` | end users, devices (typed); LDAP sources via generic | no |
| `dialplan` | gateway rules (typed); locations and nodes (read) | no |
| `config` | generic `pexip_list/get/create/update/delete_config` over the ~75-entry registry (absorbs IVR themes, LDAP, global settings) | yes |
| `live` | active conferences/participants, participant quality, and the 13 live-control commands | yes |
| `health` | alarms, node status, licensing, registrations, and generic `pexip_list/get_status` over the status registry | yes |
| `history` | `summarize_calls`, history conferences/participants (typed), generic `pexip_list/get_history` | yes |
| `platform` | `pexip_run_platform_command(command: enum)`, backups/upgrades via generic; requires `PEXIP_ALLOW_PLATFORM_TOOLS` | no |

Selection: `PEXIP_TOOLSETS=default,dialplan` or `all`; `PEXIP_TOOLS=pexip_get_vmr,...` adds individual tools; `PEXIP_DENY_TOOLS` removes; for the HTTP transport also `X-Pexip-Toolsets` header and `/x/{toolset}` path like GitHub. Precedence, in order: deny list, read-only filter, platform gate, then toolset/tool allow-lists. Read-only wins over an explicit `PEXIP_TOOLS` request, as GitHub does.

Projected counts: `all` 65 to 75 tools; default toolsets about 40 to 45; `compact` about 10. Default lands inside the 30 to 50 band where selection accuracy holds without tool search, and `rooms`+`live` alone is about 25 for a pure operator deployment.

### 3.3 Consolidation rules

Keep a typed tool only when an eval shows the generic tool loses on parameters. Starting split:

- **Status** 39 to 8: typed `list_active_conferences`, `list_active_participants`, `get_active_participant`, `get_participant_quality`, `list_alarms`, `get_licensing_status`; generic `pexip_list_status(resource, filters, limit, offset, fetch_all, response_format)` and `pexip_get_status(resource, id)` over a 20-entry STATUS_REGISTRY (shards, backplanes, cloud nodes, Exchange, MJX, Teams, registrations, sync status, management node, locations).
- **History** 14 to 6: typed `summarize_calls`, `list_history_conferences`, `list_history_participants`, `get_history_participant`; generic `pexip_list_history` / `pexip_get_history` for alarms, backplanes, registrations, node events.
- **Command** 23 to 16: keep the 13 live-control tools typed (they carry the name-resolution logic and distinct annotations); `pexip_send_provisioning_email(target_type: vmr|device, id)` replaces two tools and fixes the `conference_id`-on-a-device bug; `sync_conference_ldap` stays; the 7 platform commands become one `pexip_run_platform_command(command: enum, params)` behind the existing gate.
- **Config** 46 to about 30: fold IVR themes, LDAP sources, and global settings into the registry; keep VMR, alias, automatic participant, end user, device, gateway rule typed because their parameter sets are where the evals already show value.
- **Workflow tool**: add `pexip_get_platform_health` (alarms count by level + licence headroom + node load summary + active conference count in one call). "Is the platform OK?" is the most common operator question and today costs four tool calls. Anthropic's guidance is to build a few workflow tools for high-impact tasks and let evals decide the rest.

Resources become MCP resources too: `pexip://registry` (the catalog) and `pexip://schema/{api}/{resource}` so clients that cache resources stop re-fetching schemas.

### 3.4 Discovery replaces giant descriptions

`pexip_describe_resources(api?: config|status|history, query?: str, detail: names|summary|full)` returns matching registry entries (label, lookup field, filters, concise fields, which generic tool to use). The `list_resources` description shrinks from 2,196 chars to about 300 and points at this tool. This is Azure's `learn=true`, Stripe's `api_search`, and Shopify's `learn_api` in one, and it is what lets the registry grow to every Pexip resource without the catalog growing at all.

### 3.5 Response shaping

Every list/get tool gets:

- `response_format: "concise" | "detailed"` (default concise). Concise returns the registry's `concise_fields` plus `id` and `resource_uri`, with foreign-key URIs resolved to names (`system_location: "/api/admin/.../12/"` becomes `"London DC"`). Detailed returns the redacted full record.
- `fields: list[str] | None` for explicit projection.
- A standard envelope: `{items, count, total_count, offset, has_more, next_offset, truncated, hint}`. `hint` is set whenever the result was truncated or capped and says how to narrow ("add name_contains or a start_time window; or call summarize_calls for totals").
- A byte cap, `PEXIP_MAX_RESPONSE_BYTES` (default 100 KB), applied after projection, so a runaway `fetch_all` cannot flood a 25k-token client limit.
- `outputSchema` via typed return models (`TypedDict` works in SDK 1.28's `structured_output`; carries over to v2). Dual-write `structuredContent` and a text block per spec.

Errors keep the current correlation-ID design but gain a `fix` sentence and one example valid input, per Anthropic's "actionable errors" and the directory's "no bare Bad Request" rule.

### 3.6 Naming and descriptions

- Prefix every tool `pexip_`; pattern `pexip_{verb}_{resource}` with the verb set `list get search create update delete` plus the live-control verbs. Service prefixing is in Anthropic's best-practices doc and makes one tool-search query match the whole server.
- Disambiguate parameters: `conference_uuid` for live Status/Command IDs, `vmr` for config name-or-id, `template_id` for the LDAP sync template. No two meanings for one name.
- Description template, enforced by a test: first sentence says what it does and the Pexip API it hits; a "Use when / Do not use when" pair that names the sibling tool; parameter formats and enums; a one-line returns summary; a link to the Pexip Management API doc page for any tool taking freeform `settings` or `filters` (directory requirement).
- `input_examples` via the tool `meta` field: one minimal, one partial, one full example for every tool with 4+ optional parameters (about 15 tools). Formats like `2026-10-24T00:00:00` UTC and the `pin` string type are exactly the cases Anthropic cites.
- Description floor of 120 characters and a near-duplicate check (Levenshtein on names, cosine on descriptions) in `tests/test_catalog_quality.py`, because Glama weights the weakest tool.
- Legacy names: `PEXIP_LEGACY_TOOL_NAMES=true` registers today's names as aliases for one minor version so existing configs and the skills package keep working; the evals YAML is migrated by script.

### 3.7 Safety additions that peers now ship

Keep everything that exists. Add, in order of value:

- `PEXIP_REQUIRE_MUTATION_CONSENT=true`: destructive tools issue an elicitation ("Disconnect 14 participants from All Hands?") before acting. AWS ships exactly this. On SDK 1.x it uses `ctx.elicit`; on the 2026 spec it becomes an MRTR `input_required` round trip automatically with SDK v2.
- `PEXIP_DENY_TOOLS` / `PEXIP_DENY_RESOURCES` (Kubernetes `denied_resources` analogue) so an operator can hide, say, `end_user` entirely.
- Per-toolset OIDC scopes on the HTTP transport (`pexip.live`, `pexip.config.write`) mapped from the toolset table, so a token can be minted for one toolset.

### 3.8 Transport posture for ranking

The Claude directory only lists remote HTTPS servers. The `--http` path becomes first-class: `stateless_http=True`, `json_response=True` (Anthropic's recommended stateless JSON), header/path toolset selection, OIDC as today, and `ttlMs`/`cacheScope` on `tools/list` once on SDK v2. The stdio path stays for Claude Code and the plugin.

## 4. Validation: how we prove it is better, not just different

### 4.1 Scorecard (every run, every mode)

Extend `evals/scoring.py` to emit a JSON scorecard per run and per mode:

| Metric | Source | Target vs. today's baseline |
|---|---|---|
| Task accuracy (tool choice + params) | existing 156 cases | no regression in any persona slice |
| End-to-end answer accuracy | new QA set (4.2) | 90%+ on `default`, 85%+ on `compact` |
| Tokens per task (catalog + results) | API usage fields | at least 40% lower on `default`, 70% on `compact` |
| Tool calls per task | transcript | lower or equal |
| Wrong-tool rate, param-error rate | transcript + tool errors | each under 3% |
| pass^3 (stability across 3 runs) | repeat LLM cases | report, from MCPMark's method |
| Catalog tokens by mode | deterministic | `default` under 15k, `compact` under 3k |

Run the deterministic subset in CI, the LLM layer nightly or on label, and the live layer against the lab on release.

### 4.2 End-to-end QA set (Anthropic mcp-builder format)

Ten to fifteen read-only, multi-hop questions with single string answers against seeded lab data in a frozen time window, in the `<evaluation><qa_pair>` XML the mcp-builder skill's `evaluation.py` consumes. Examples of the shape:

- "Across calls that ended between 1 and 7 Sept 2026 UTC, which system location had the most participant legs rated 3_bad or worse? Answer with the location name."
- "Which VMR has an automatic participant that dials a SIP destination in the `lab.local` domain and also has guests disallowed? Answer with the VMR name."
- "How many Conferencing Nodes in the London location are proxying nodes? Answer with a number."

Keep 20% of cases held out and written after the redesign, so descriptions are not tuned to the test.

### 4.3 Catalog quality lint (the directory and Glama checks, run locally)

`tests/test_catalog_quality.py` asserts, for every registered tool in every mode: `title` present; exactly one of `readOnlyHint`/`destructiveHint` true; name under 64 chars with `pexip_` prefix; description at least 120 chars and contains "Use when"; freeform-payload tools link the Pexip API docs; no tool mixes read and write operations; no two names within edit distance 2; `outputSchema` present; `input_examples` present when 4+ optional params. This is the Glama rubric and the Claude review checklist made executable.

### 4.4 A/B gates for each consolidation

Every fold (for example Status 39 to 8) ships behind `all` vs `toolsets` and is accepted only when the scorecard shows accuracy held and tokens fell. Anthropic's advice to paste failing transcripts back into Claude Code to refactor the description applies here; the harness should save transcripts per case.

### 4.5 External validation

- Glama already indexes the server as "Pexip Infinity MCP Server". After the rename, request a rescan and track the tier; target A.
- Submit the HTTP transport to the Claude Connectors Directory as a Community connector (needs PyPI/registry publish, a reviewer lab account, privacy policy, docs URL). The pre-submission checklist is section 2's directory column.
- MCP Registry entry plus Docker MCP Catalog PR once the image is published.

## 5. Rollout

| Phase | Work | Gate |
|---|---|---|
| 0 | Record baseline scorecard on today's catalog, all metrics | scorecard committed |
| 1 | Prefix + rename, parameter disambiguation, description template, `input_examples`, catalog lint, legacy alias flag; migrate evals YAML | lint green; accuracy unchanged |
| 2 | Response envelope, concise/detailed, field projection, FK name resolution, byte cap, `outputSchema` | tokens per task down; accuracy unchanged |
| 3 | `CATALOG` data model, `pexip_describe_resources`, MCP resources, `PEXIP_TOOLSETS` / `PEXIP_TOOLS` / deny list, HTTP header selection | default mode under 45 tools and 15k tokens |
| 4 | Status and History generic tools; fold IVR/LDAP/global into config registry; `pexip_get_platform_health`; `pexip_run_platform_command`; provisioning-email fix | A/B accepted per fold |
| 5 | `compact` mode; mutation-consent elicitation; per-toolset scopes | compact 85%+ end-to-end |
| 6 | SDK v2, stateless HTTP, `ttlMs`; publish PyPI, registry, directory, Glama rescan | listed; tier A |

Phases 1 and 2 are mechanical and low-risk. Phase 3 is the architectural change and the one to review carefully. Phases 4 and 5 are where the evals earn their keep.

## 5a. Phase 0 and 1a status (31 Oct 2026)

Done on branch `claude/determined-ride-dgr72l`:

- `mcp>=1.2.0,<2` pinned; Dockerfile and `packaging/mcpb/build.sh` now install the locked dependency set via `uv export`; CI gained an unlocked-install smoke job. A fresh `pip install .` resolves mcp 1.30 and registers 122 tools. The Docker build was not verifiable in the authoring sandbox (no daemon) and needs one local `docker build .` to confirm.
- `scripts/catalog_stats.py` is the baseline instrument. Baselines committed under `evals/baseline/`: full catalog 122 tools / ~22.2k est. tokens; read-only default 76 tools / ~12.0k est. tokens. Set `ANTHROPIC_API_KEY` to record the exact count.
- `tests/test_catalog_quality.py` encodes the rubric. 7 properties pass today; 9 are `xfail(strict=True)` and become the phase-1/2/3 acceptance gates. Notable finding: the 8 `create_*` tools set neither `readOnlyHint` nor `destructiveHint`, which the Claude directory checklist treats as missing.

Still to do for phase 0: run `--llm` three times and `--live` once against the lab and commit the scorecard; record the Glama tier.

## 6. Risks and how the plan handles them

- **Generic tools lose parameter accuracy.** Mitigated by keeping typed tools for hot paths, the discovery tool, `get_schema`, `input_examples`, and the per-fold A/B gate. Stripe and Azure ship this pattern at larger scale.
- **Renames break existing users and the skills package.** Alias flag for one release; `TOOLS.md` carries an old-to-new table; the skills package is updated in the same PR.
- **Fewer tools look "less complete" to a casual reader.** Glama's coherence score rewards appropriate count and completeness, not raw count; `describe_resources` advertises the full surface. README should lead with coverage (every Pexip resource) and the eval scorecard rather than the tool count.
- **Elicitation support varies by client.** Consent is opt-in and degrades to today's behaviour when the client lacks the capability.

## Sources

- Anthropic, Writing effective tools for agents: https://www.anthropic.com/engineering/writing-tools-for-agents
- Anthropic, Advanced tool use (tool search, programmatic calling, input examples): https://www.anthropic.com/engineering/advanced-tool-use
- Tool Search Tool docs: https://platform.claude.com/docs/agents-and-tools/tool-use/tool-search-tool
- Anthropic, Code execution with MCP: https://www.anthropic.com/engineering/code-execution-with-mcp
- Anthropic mcp-builder skill: MCP best practices and evaluation guide (local skill reference files)
- Claude Connectors Directory pre-submission checklist: https://claude.com/docs/connectors/building/review-criteria.md and submission: https://claude.com/docs/connectors/building/submission.md
- GitHub MCP server README and server-configuration docs: https://github.com/github/github-mcp-server
- Azure MCP server concepts and commands: https://learn.microsoft.com/azure/developer/azure-mcp-server/concepts
- Kubernetes MCP server: https://github.com/containers/kubernetes-mcp-server
- AWS API MCP server: https://github.com/awslabs/mcp/tree/main/src/aws-api-mcp-server
- Stripe MCP: https://docs.stripe.com/mcp
- Cloudflare Code Mode: https://developers.cloudflare.com/agents/model-context-protocol/codemode/
- Shopify Dev MCP: https://shopify.dev/docs/apps/build/devmcp
- Sentry MCP: https://github.com/getsentry/sentry-mcp
- Glama scoring rubric (as published on server review pages): https://glama.ai/mcp/servers
- Benchmarks: MCPMark https://arxiv.org/abs/2509.24002 , MCP-Universe https://neurips.cc/virtual/2025/124527 , LiveMCPBench https://arxiv.org/abs/2508.01780
- MCP 2026-07-28 spec summary: https://blog.modelcontextprotocol.io/posts/2026-07-28/
