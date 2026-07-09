#!/usr/bin/env bash
#
# Build the MCPB (.mcpb) bundle for one-click install in Claude Desktop.
#
# Prereqs:
#   - python (matching the platform you'll install on)
#   - the mcpb CLI:  npm install -g @anthropic-ai/mcpb
#
# IMPORTANT: this bundle vendors native dependencies (cryptography, via
# pyjwt[crypto]). The resulting .mcpb is therefore PLATFORM-SPECIFIC — build it
# on the same OS/arch you intend to install on (e.g. build on macOS arm64 for an
# Apple-silicon laptop). For a cross-platform story, prefer Docker or `uvx`.
#
# Untested end-to-end: this scaffolding is provided for you to build + install
# locally and verify before sharing the .mcpb.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
BUILD="$HERE/build"

rm -rf "$BUILD"
mkdir -p "$BUILD/server/lib"

cp "$HERE/manifest.json" "$BUILD/manifest.json"
cp "$HERE/main.py" "$BUILD/server/main.py"
cp "$ROOT/.github/icon.png" "$BUILD/icon.png"   # extension icon shown in Claude Desktop

# Vendor the package + all runtime deps into server/lib for a self-contained bundle.
# Prefer python3 (macOS/Linux often lack a bare `python`); override with PYTHON=...
PYTHON="${PYTHON:-$(command -v python3 || command -v python)}"
if [[ -z "$PYTHON" ]]; then
  echo "error: no python3/python on PATH — install Python 3 first" >&2
  exit 1
fi
"$PYTHON" -m pip install "$ROOT" --target "$BUILD/server/lib" --upgrade

cd "$BUILD"
if command -v mcpb >/dev/null 2>&1; then
  mcpb pack . "$HERE/pexip-mgmt-mcp.mcpb"
  echo "Built: $HERE/pexip-mgmt-mcp.mcpb"
else
  echo "Bundle staged at: $BUILD"
  echo "Install the mcpb CLI (npm i -g @anthropic-ai/mcpb), then: mcpb pack $BUILD <out>.mcpb"
fi
