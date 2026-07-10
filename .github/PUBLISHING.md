# Publishing to marketplaces

The descriptor files in this repo are staged and ready, but **publishing is a
deliberate, fully manual step** — there is no CI automation for it. A version
tag (`v*`) does **not** publish anything; PyPI and Docker/GHCR publishing were
deliberately removed from CI (see below) so a tag push can never trigger a
release by accident.

Order of operations:

1. **Validate against a real/lab node** (OAuth2 ES256 flow + the in-call
   message command — see the two flags in the README / PR).
2. **Publish by hand** using the commands below, from your own machine.
3. **Then** submit to the marketplaces below.

A package on **PyPI** (for `uvx`) plus the **official MCP Registry** is the
minimum legitimate footprint; the rest are reach.

---

## 1. PyPI (prerequisite for everything else)

- One-time: on PyPI, generate an **API token** for this project (Account
  settings → API tokens).
- Publish manually from your machine:
  ```bash
  uv build
  uv publish --token <your-pypi-token>
  ```
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

## 3. Docker / GHCR image (manual)

- Build and push by hand when you want an image published, no CI involved:
  ```bash
  docker build -t ghcr.io/josh-e-s/pexip-mgmt-mcp:<version> .
  docker push ghcr.io/josh-e-s/pexip-mgmt-mcp:<version>
  ```
- There is no CI workflow for Docker anymore (removed along with the
  auto-publish trigger) — `docker build .` locally is the only validation
  until/unless you want a build-only CI check back.

## 5. Docker MCP Catalog

Draft descriptor: [`packaging/docker-mcp-registry/server.yaml`](packaging/docker-mcp-registry/server.yaml).

- Fork https://github.com/docker/mcp-registry, then run their generator
  (`task create` / `task wizard`) to produce a validated
  `servers/pexip-mgmt-mcp/server.yaml` (+ `tools.json`) — use the draft as
  input. Fill in `source.commit` and an `icon`.
- Open a PR; Docker reviews, then builds + signs the image to
  `mcp/pexip-mgmt-mcp` on Docker Hub and lists it in Docker Desktop's MCP
  Toolkit. Choose **Docker-built** (they build) vs **community-built** (you do).

## 6. Claude Desktop (MCPB bundle)

Bundle: [`packaging/mcpb/build.sh`](packaging/mcpb/) vendors the deps and packs a
`.mcpb` the user double-clicks to install (a form collects host + credentials —
no JSON). Builds locally today, no registry required:

```bash
npm install -g @anthropic-ai/mcpb
./packaging/mcpb/build.sh
```

Platform-specific (vendors native deps) — build one per target OS. Optionally
submit the `.mcpb` to the directory at https://desktopextensions.com, or just
share the file directly.

## 7. Passive directories

mcp.so, PulseMCP, and Glama largely auto-index public GitHub MCP servers and the
official registry — a clean README + a registry entry generally gets you listed
without a separate submission.
