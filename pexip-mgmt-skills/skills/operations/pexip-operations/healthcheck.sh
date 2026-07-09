#!/usr/bin/env bash
# Smoke-test the pexip-mgmt MCP server is reachable and authed.
#
# Usage:
#   ./healthcheck.sh                # runs against the pexip_mcp module on PYTHONPATH
#   PEXIP_MCP_DIR=/path bash ./healthcheck.sh
#
# Reads PEXIP_HOST / PEXIP_USERNAME / PEXIP_PASSWORD / PEXIP_VERIFY_TLS from
# env (or .env in the MCP server dir).
#
# Exits 0 on success, non-zero with a stderr message on failure.
set -euo pipefail

# Resolve where the server source lives.
MCP_DIR="${PEXIP_MCP_DIR:-}"
if [[ -z "$MCP_DIR" ]]; then
    # Try a few common spots relative to this script's directory.
    here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    for candidate in \
        "$here/../../.." \
        "$here/../../../.." \
        "$here/../../../../.." \
    ; do
        if [[ -f "$candidate/pyproject.toml" ]] && grep -q "pexip_mcp" "$candidate/pyproject.toml" 2>/dev/null; then
            MCP_DIR="$(cd "$candidate" && pwd)"
            break
        fi
    done
fi

if [[ -z "$MCP_DIR" ]]; then
    echo "error: could not locate pexip-mgmt-mcp source. Set PEXIP_MCP_DIR." >&2
    exit 2
fi

if command -v uv >/dev/null 2>&1; then
    cd "$MCP_DIR" && exec uv run python -m pexip_mcp --healthcheck
else
    cd "$MCP_DIR" && exec python -m pexip_mcp --healthcheck
fi
