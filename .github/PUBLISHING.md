# Publishing to marketplaces

The descriptor files in this repo are staged and ready, but **publishing is a
deliberate post-test, post-tag step** — none of this happens automatically.

Order of operations:

1. **Validate against a real/lab node** (OAuth2 ES256 flow + the in-call
   message command — see the two flags in the README / PR).
2. **Tag a release**: `git tag v0.1.0 && git push --tags`. This fires the
   `release.yml` (PyPI) and `docker.yml` (GHCR image) workflows.
3. **Then** submit to the marketplaces below.

A package on **PyPI** (for `uvx`) plus the **official MCP Registry** is the
minimum legitimate footprint; the rest are reach.

---

## 1. PyPI (prerequisite for everything else)

- One-time: on PyPI, add a **Trusted Publisher** for this repo (Publishing →
  add GitHub, repo `Josh-E-S/pexip-mgmt-mcp`, workflow `release.yml`,
  environment `pypi`). No API token needed.
- Tagging `v*` then publishes automatically via `release.yml`.
- Verify: `uvx pexip-mgmt-mcp --healthcheck`.

## 2. Official MCP Registry

Descriptor: [`server.json`](server.json) (already points at the PyPI package).

- Install the CLI: `brew install mcp-publisher` (or download from the
  [registry releases](https://github.com/modelcontextprotocol/registry)).
- Ownership check: the registry verifies the string `mcp-name:
  io.github.josh-e-s/pexip-mgmt-mcp` appears in the **published PyPI README**
  (already added to `README.md` as a comment).
- Authenticate with GitHub and publish:
  ```bash
  mcp-publisher login github
  mcp-publisher publish   # reads ./server.json
  ```
- Keep `server.json`'s `version` in sync with the released PyPI version.
- This can also be automated in `release.yml` (GitHub OIDC) once the flow is
  confirmed — left manual for now to keep CI green.

## 3. Docker MCP Catalog

Draft descriptor: [`packaging/docker-mcp-registry/server.yaml`](packaging/docker-mcp-registry/server.yaml).

- Fork https://github.com/docker/mcp-registry, then run their generator
  (`task create` / `task wizard`) to produce a validated
  `servers/pexip-mgmt-mcp/server.yaml` (+ `tools.json`) — use the draft as
  input. Fill in `source.commit` and an `icon`.
- Open a PR; Docker reviews, then builds + signs the image to
  `mcp/pexip-mgmt-mcp` on Docker Hub and lists it in Docker Desktop's MCP
  Toolkit. Choose **Docker-built** (they build) vs **community-built** (you do).

## 4. Passive directories

mcp.so, PulseMCP, and Glama largely auto-index public GitHub MCP servers and the
official registry — a clean README + a registry entry generally gets you listed
without a separate submission.
