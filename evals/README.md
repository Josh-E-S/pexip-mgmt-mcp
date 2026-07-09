# Eval Suite

Tests how well an LLM agent selects, chains, and parameterizes the
pexip-mgmt-mcp tools. Operates in two layers with an optional live mode.

## Quick start

> Running `evals/` on its own prints a partial coverage number (only part of
> `pexip_mcp` is exercised) — that's expected and harmless. The 80% coverage gate
> is enforced only in CI on the full suite, so a subset run never fails on coverage.
> Add `--no-cov` if you want to skip the coverage report entirely.

```bash
# Deterministic only — CI-safe, no API keys needed (332 checks)
uv run pytest evals/

# With LLM scoring — needs ANTHROPIC_API_KEY (~$2 per full run, ~6 min)
uv run pytest evals/ --llm

# Pick the model used for --llm scoring (default: claude-sonnet-5)
PEXIP_EVAL_MODEL=claude-sonnet-5 uv run pytest evals/ --llm

# Run just one persona's cases (cases are tagged) — e.g. the live operator
uv run pytest evals/ --llm -k operator

# Live node integration — needs .env with Pexip creds
uv run pytest evals/ --live

# Live + auto-dial (Status/Command API tests dial out to your endpoint)
PEXIP_EVAL_DIAL_TARGET="sip:test@lab.local" uv run pytest evals/ --live

# Everything
PEXIP_EVAL_DIAL_TARGET="sip:test@lab.local" uv run pytest evals/ --llm --live
```

> **Cost:** every `--llm` request carries the full ~36k-token tool catalog.
> The harness marks it with a prompt-cache breakpoint (`conftest.py`), so all
> but the first request read it from cache at 10% of the input price — a full
> run costs roughly $2 instead of ~$20. Keep that `cache_control` in place.

## What's tested

| File | What it checks | Layer |
|---|---|---|
| `test_tool_selection.py` | Given a prompt, does the agent pick the right tool(s)? | Deterministic + LLM (multi-turn) |
| `test_workflows.py` | Can the agent chain tools in the correct order? | Deterministic + LLM (multi-turn) |
| `test_error_handling.py` | Does it handle 404s, 409s, empty results gracefully? | Deterministic (respx) |
| `test_parameters.py` | Does it pass the right field names and types? | Deterministic + LLM (multi-turn) |
| `test_live_integration.py` | CRUD, status reads, and command actions against a real node | Live only |

All LLM layers run short **multi-turn conversations**: the prompt goes to
Claude with the full tool catalog, each tool call is answered with a mocked
result, and grading happens on the finished transcript. This lets legitimate
protocols complete before scoring — e.g. `get_resource_schema` before
`create_resource`, or listing participants before a destructive command.

## Test cases

All eval cases live in `cases/` as YAML files:

- **`tool_selection.yaml`** (90 cases) — prompt → expected tool(s), with a match mode
- **`parameters.yaml`** (31 cases) — prompt → expected tool + parameter values
- **`workflows.yaml`** (20 cases) — prompt → ordered tool chain with mock returns per step
- **`error_handling.yaml`** (19 cases) — error conditions → expected exception or graceful response

Match modes (`scoring.py`):

| Mode | Passes when |
|---|---|
| `exact` | Exactly the expected tools were called, no extras |
| `subset` | All expected tools appear; extra (e.g. preparatory read) calls are fine |
| `ordered_subset` | Expected tools appear in order; gaps allowed |
| `any_of` | At least one expected tool appears — for prompts where several tools are each a fully legitimate answer |

### Personas covered

Cases are written around the real jobs someone does with a Pexip deployment,
and tagged so you can run one slice at a time (`-k <tag>`):

| Tag | Persona | Example prompt |
|---|---|---|
| `operator` | Live meeting moderator | "Mute all the guests and lock the room" |
| `provisioning` | VMR provisioning admin | "Create a VMR, add an alias, email the owner" |
| `users` / `devices` | User & device admin | "Onboard dana@company.com and register her desk device" |
| `routing` | Dial plan / routing admin | "Disable the PSTN gateway rule" |
| `reporting` | CDR analyst | "Find bad-quality participants from today" |
| `monitoring` | NOC / on-call | "Any alarms, are all nodes up, licensing headroom?" |
| `ldap` | Directory sync admin | "Set up an LDAP sync source for Corp AD" |
| `mjx` | One-Touch-Join room admin | "Are the room endpoints online?" |
| `integrations` | External integrations | "Add a Teams Connector / Azure tenant" |
| `maintenance` | Backup / platform ops | "Take a configuration backup" |

## Adding a new case

1. Add an entry to the appropriate YAML file in `cases/`
2. Run `uv run pytest evals/ -k <case-id>` to validate it (free deterministic layer)
3. If adding an `--llm` case, run with `--llm` to check Claude's actual behavior

### Case format: tool_selection.yaml

```yaml
- id: my-case-name
  prompt: "Natural language request"
  expected_tools: [tool_name_1, tool_name_2]
  match: exact | subset | ordered_subset | any_of
  # Optional: mocked results fed back for intermediate calls during the
  # multi-turn conversation (tools not listed here return {}).
  mock_returns:
    some_lookup_tool: {objects: [{id: "uuid-1", name: "Thing"}], meta: {total_count: 1}}
  tags: [category, ...]
```

### Case format: workflows.yaml

```yaml
- id: my-workflow
  prompt: "Multi-step request"
  steps:
    # `optional: true` marks a lookup the model MAY make but doesn't have to —
    # the server resolves names to UUIDs itself, so listing first is
    # legitimate but unnecessary. The matcher accepts either path.
    - tool: list_active_conferences
      optional: true
      params_contain: {}
      returns: {objects: [{id: "conf-uuid-1", name: "Standup"}], meta: {total_count: 1}}
    - tool: lock_conference
      # A list value means any-of: the model may pass the UUID from the
      # lookup OR the name from the prompt (resolved server-side).
      params_contain: {conference_id: ["conf-uuid-1", "Standup"]}
      returns: {status: "success"}
  tags: [category, ...]
```

### Case format: parameters.yaml

```yaml
- id: my-param-case
  prompt: "Request with specific values"
  expected_tool: tool_name
  expected_params:
    field_name: "expected_value"
  params_present: [field_that_must_exist]
  # Optional, same semantics as tool_selection: feed realistic results to
  # preparatory calls (e.g. get_resource_schema) before the graded call.
  mock_returns: {}
  tags: [category, ...]
```

## Flags

| Flag | What it does | Requirements |
|---|---|---|
| `--llm` | Sends prompts to Claude API and scores tool selection | `ANTHROPIC_API_KEY` env var, `anthropic` package |
| `--live` | Runs integration tests against a real Pexip node | `.env` with `PEXIP_*` credentials |
| `PEXIP_EVAL_DIAL_TARGET` | SIP URI or alias for auto-dial tests (Status/Command) | Set as env var, e.g. `sip:cisco@lab.local` |
| `PEXIP_EVAL_MODEL` | Model id used for `--llm` scoring (default `claude-sonnet-5`) | Set as env var |

## Live call tests (auto-dial)

The `--live` suite includes Status and Command API tests that need an
active call. Instead of requiring you to manually dial in, the test
fixture automatically:

1. Creates a temporary VMR (`eval-live-call-room`)
2. Dials out to `PEXIP_EVAL_DIAL_TARGET` using `dial_participant`
3. Waits 5 seconds for the call to connect
4. Runs status reads (list participants, get quality) and command actions
   (mute, lock, send message, disconnect) — including targeting the
   participant and conference **by name** to exercise server-side resolution
5. Disconnects everyone and deletes the VMR

If `PEXIP_EVAL_DIAL_TARGET` is not set, the status/command tests are
skipped with a clear message. The CRUD, history, and error tests still
run without it.

The target can be any endpoint reachable from your lab node:
- A registered SIP device: `sip:cisco@lab.local`
- A Pexip test call alias (if configured): `test-call@lab.local`
- An external SIP endpoint: `sip:echo@provider.example`

## Architecture

```
evals/
├── conftest.py              # Fixtures: tool registry, clients, CLI flags, prompt caching
├── scoring.py               # Scorers: exact, subset, ordered_subset, any_of, params
├── cases/
│   ├── tool_selection.yaml  # 90 tool selection cases
│   ├── parameters.yaml      # 31 parameter correctness cases
│   ├── workflows.yaml       # 20 multi-step workflow cases
│   └── error_handling.yaml  # 19 error handling cases
├── test_tool_selection.py   # Multi-turn selection grading
├── test_workflows.py        # Chain matcher: ordered steps, optional lookups, any-of params
├── test_error_handling.py
├── test_parameters.py       # Multi-turn parameter grading
└── test_live_integration.py
```
