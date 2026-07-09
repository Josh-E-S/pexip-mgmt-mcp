# Deploying behind Cloudflare Tunnel + Access

This guide assumes you already have a Cloudflare Tunnel set up with Cloudflare
Access (Google SSO or similar) — and want to expose the Pexip MCP server
through it so a remote Claude client (mobile, web, IDE) can use it.

## Security model — read this first

The server's HTTP transport is **safe by default**:

- `--host` defaults to `127.0.0.1` (loopback only). Cloudflare Tunnel running
  on the same box reaches it via localhost; nothing on the public network can.
- If you set `--host 0.0.0.0` (or any non-loopback address), the server
  **refuses to start** unless `PEXIP_MCP_TOKEN=<long-random>` is set in env.
  This is the guardrail against accidentally exposing an unauthenticated MCP
  endpoint.
- `PEXIP_MCP_TOKEN`, when present, is also enforced on loopback binds as
  defense-in-depth. With Cloudflare Access in front it's optional but cheap.

## Recommended posture

```
┌────────────────┐     HTTPS + CF Access (Google SSO    ┌──────────┐
│ Phone / web    │     OR service token headers)        │          │
│ Claude client  │ ───────────────────────────────────► │   CF     │
└────────────────┘                                       │  Edge    │
                                                         └─────┬────┘
                                                               │
                                                       Cloudflare Tunnel
                                                               │
                                                               ▼
                            ┌──────────────────────────────────────────┐
                            │  your box (anywhere with internet)       │
                            │  ┌────────────┐    ┌──────────────────┐  │
                            │  │ cloudflared│ ──►│ pexip-mgmt-mcp  │  │
                            │  │            │    │ on 127.0.0.1:8000│  │
                            │  └────────────┘    └────────┬─────────┘  │
                            └─────────────────────────────┼────────────┘
                                                          │ HTTPS Basic
                                                          ▼
                                              ┌────────────────────────┐
                                              │ Pexip Management Node  │
                                              └────────────────────────┘
```

## 1. Run the server

On the box that's behind your tunnel:

```bash
git clone <repo> && cd pexip-mgmt-mcp
uv sync
cp .env.example .env
# edit .env with PEXIP_HOST / PEXIP_USERNAME / PEXIP_PASSWORD

uv run python -m pexip_mcp --healthcheck   # validate creds first
uv run python -m pexip_mcp --http          # binds 127.0.0.1:8000 by default
```

You should see something like:

```
pexip-mgmt-mcp HTTP transport starting on http://127.0.0.1:8000
  Bind: loopback only — point Cloudflare Tunnel at this address.
  Bearer-token auth: disabled (relying on network layer)
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

For long-running use, wrap in a systemd unit / Docker container / supervisor
of your choice.

## 2. Wire up the Cloudflare Tunnel route

In Cloudflare Zero Trust → **Networks → Tunnels → your tunnel → Public
Hostnames → Add a public hostname**:

- Subdomain: `pexip-mcp` (or whatever you want)
- Domain: your Cloudflare-managed domain
- Service: `HTTP://localhost:8000`

After saving, `https://pexip-mcp.example.com` proxies to your local server.

## 3. Cloudflare Access policy

In Cloudflare Zero Trust → **Access → Applications → Add an application →
Self-hosted**:

- Application domain: the hostname you just created
- **Policy 1 — interactive (browser)**: Action *Allow*, Include *Emails: your-email@…*
- **Policy 2 — programmatic (Claude)**: Action *Service Auth*, Include
  *Service Token: pexip-mcp-claude*

Then create the service token: **Access → Service Auth → Service Tokens →
Create Service Token**, name it `pexip-mcp-claude`. Copy the **Client ID**
and **Client Secret** — you'll only see the secret once.

## 4. Wire into Claude

Use Claude's "Custom connector" / "Remote MCP server" config and supply:

- URL: `https://pexip-mcp.example.com/mcp` (the streamable-HTTP endpoint)
- Headers:
  - `CF-Access-Client-Id`: `<the client id>.access`
  - `CF-Access-Client-Secret`: `<the secret>`

If your Claude client also lets you set an `Authorization: Bearer …` header
*and* you set `PEXIP_MCP_TOKEN` on the server, add that too. Otherwise rely on
Cloudflare Access only.

## 5. (Recommended) Bearer token on the listener

Set a bearer token so the listener itself authenticates every request, rather
than trusting the network layer alone. Generate one, set it on the server, and
paste it into the Claude connector:

```bash
export PEXIP_MCP_TOKEN=$(python -c 'import secrets; print(secrets.token_urlsafe(48))')
uv run python -m pexip_mcp --http
```

The server then 401s anything without `Authorization: Bearer <token>`, even on
loopback — so a co-located process or a misconfigured Access policy can't reach
the admin tool surface unauthenticated. The token must be at least 32
characters; the server refuses to start with a shorter one. Cloudflare Access
in front is complementary, not a substitute: defense in depth, and it's a
single env var plus a single header.

## Docker variant

```bash
docker build -t pexip-mgmt-mcp .
docker run --rm \
  -p 127.0.0.1:8000:8000 \
  -e PEXIP_HOST=manager.example.com \
  -e PEXIP_USERNAME=admin \
  -e PEXIP_PASSWORD=… \
  -e PEXIP_MCP_TOKEN=$(python -c 'import secrets; print(secrets.token_urlsafe(48))') \
  pexip-mgmt-mcp
```

The container binds `0.0.0.0:8000` internally, but the `-p 127.0.0.1:8000:8000`
flag exposes it to the host's loopback only. Cloudflare Tunnel running on the
host reaches it on localhost. `PEXIP_MCP_TOKEN` is required because the
container's bind isn't loopback from its own perspective.

## Troubleshooting

- **`REFUSING TO START`**: you bound to a non-loopback host (or Docker, by
  default). Either bind to 127.0.0.1 or set `PEXIP_MCP_TOKEN`.
- **CF Access returns 403 to Claude**: service token policy not added, or
  Claude isn't sending the `CF-Access-Client-Id` / `CF-Access-Client-Secret`
  headers. Test from the box: `curl -H "CF-Access-Client-Id: …" -H
  "CF-Access-Client-Secret: …" https://pexip-mcp.example.com/mcp/`.
- **Claude connector returns 401**: `PEXIP_MCP_TOKEN` mismatch between server
  and connector config.
- **Claude can't see any tools**: check the server logs for the
  `tools/list` request landing. If it's not arriving, the URL or auth
  is wrong.
