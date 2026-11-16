## What and why

<!-- One or two sentences. Link the issue if there is one. -->

## How it was tested

<!-- Commands you ran, and against which Infinity version if the lab was involved. -->

## Checklist

- [ ] `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest -q` pass
- [ ] New or changed tools have a `GUIDANCE` entry, a toolset, and an eval case
- [ ] `TOOLS.md` regenerated if the catalog changed (`uv run python scripts/generate_tools_md.py`)
- [ ] `CHANGELOG.md` updated for user-visible changes
- [ ] No credentials, hostnames of real deployments, or customer data in code, tests or docs
