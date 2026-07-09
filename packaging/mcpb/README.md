# MCPB bundle (Claude Desktop one-click install)

This builds a [MCP Bundle](https://github.com/modelcontextprotocol/mcpb) (`.mcpb`,
formerly `.dxt`) so a non-developer can install the Pexip MCP server in Claude
Desktop with a double-click and fill in their host + credentials via prompts —
no JSON editing, no `uv`/`pip`.

## Build

```bash
npm install -g @anthropic-ai/mcpb        # one-time: the packer CLI
./build.sh                               # vendors deps + packs pexip-mgmt-mcp.mcpb
```

Then double-click `pexip-mgmt-mcp.mcpb` (or Claude Desktop → Settings →
Extensions → install from file).

## Caveats (read before sharing)

- **Platform-specific.** The bundle vendors `cryptography` (native, pulled in by
  `pyjwt[crypto]` for OAuth2). A `.mcpb` built on macOS arm64 will not run on
  Windows x64. Build one per target platform, or steer users to Docker / `uvx`
  for portability.
- **Needs a `python` on PATH.** MCPB Python bundles run the host's `python`;
  the deps are vendored but the interpreter is not.
- **Untested end-to-end here.** This is scaffolding — build it and verify the
  install + a tool call locally before distributing.

## What the prompts map to

The `user_config` block in `manifest.json` collects the host, auth mode, and
credentials and injects them as the `PEXIP_*` env vars the server reads (see the
repo README's Configuration section). Secrets (`password`, `oauth2_private_key`)
are stored by Claude Desktop in the OS keychain, not in plain config.
