# Contributing

Thanks for helping. This server exposes an administrative API, so changes are
held to a stricter bar than a typical tool wrapper: every tool is described,
gated, tested and covered by an eval case before it merges.

## Setup

```bash
git clone https://github.com/Josh-E-S/pexip-mgmt-mcp.git
cd pexip-mgmt-mcp
uv sync --locked            # Python 3.11+; installs runtime and dev dependencies
uv run pre-commit install   # optional: run the checks below on every commit
```

No Pexip Infinity deployment is needed. Unit tests mock the Management API with
[respx](https://github.com/lundberg/respx), and a local `.env` is ignored by them.

## Checks

CI runs these on Python 3.11 to 3.14; run them before opening a pull request.

```bash
uv run ruff check .            # lint
uv run ruff format --check .   # formatting (drop --check to fix)
uv run mypy                    # static types for src/pexip_mcp
uv run pytest -q               # unit tests and deterministic eval checks
```

CI also enforces 80% coverage on the full suite, audits dependencies with
`pip-audit`, scans for secrets with gitleaks and analyses the code with CodeQL.

Two optional suites need credentials and are not run in CI:

```bash
uv run pytest evals/ --llm     # LLM-graded tool selection (ANTHROPIC_API_KEY)
uv run pytest evals/ --live    # against a real lab node (.env); never production
```

## Adding or changing a tool

The catalog tests (`tests/test_catalog_quality.py`, `tests/test_eval_coverage.py`)
fail until a tool has all of the following:

1. A `pexip_` prefixed name, a title, and `readOnlyHint` or `destructiveHint`.
2. A docstring plus an entry in `GUIDANCE` (`src/pexip_mcp/tools/_guidance.py`)
   saying when to use it and when not to. The rendered description must be
   120 to 1500 characters and may only name tools that exist.
3. A toolset in `TOOLSET_OF` (`src/pexip_mcp/tools/_catalog.py`).
4. `input_examples` when it has four or more optional parameters.
5. At least one eval case under `evals/cases/`.
6. Unit tests with the HTTP calls mocked.

Prefer extending a generic tool (`pexip_list_resources`, `pexip_list_status`,
`pexip_list_history`) over adding a typed one; add a dedicated tool only when
the model needs parameters or guidance the generic form cannot give.

Then regenerate the catalog: `uv run python scripts/generate_tools_md.py`.

Write tools are removed in read-only mode (the default), and platform lifecycle
commands sit behind `PEXIP_ALLOW_PLATFORM_TOOLS`. New tools that change state
must respect both gates; `docs/identity.md` and `SECURITY.md` describe the model.

## Pull requests

- Keep each pull request to one change, with tests in the same commit.
- Record user-visible changes in `CHANGELOG.md` under "Unreleased".
- Change dependencies in `pyproject.toml` and commit the updated `uv.lock`
  (`uv lock`). The Docker image and the MCPB bundle install from the lock.
- Never include credentials, real deployment hostnames or participant data in
  code, fixtures, logs or screenshots.

## Security issues

Report vulnerabilities privately as described in [SECURITY.md](SECURITY.md),
not in a public issue.
