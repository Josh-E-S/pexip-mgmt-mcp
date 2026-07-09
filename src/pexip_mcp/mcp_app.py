"""FastMCP instance + lifespan management.

What this file owns: the single `mcp` object every tool module decorates against,
and the `lifespan()` async context manager that builds/tears down our shared
PexipClient around the server's run.

A few terms for newcomers:

  - FastMCP is the high-level MCP server framework from the official `mcp` SDK
    (think "FastAPI but for MCP"). You build a `FastMCP(...)` instance, decorate
    functions with `@mcp.tool(...)`, and it handles the JSON-RPC protocol for you.
  - "lifespan" is the standard ASGI/FastAPI pattern for "run code at startup,
    yield control while the server is up, run code at shutdown." FastMCP takes
    one as a kwarg — we use it to construct the PexipClient (one shared HTTP
    client for the whole process) and to close it cleanly on shutdown.
  - The object yielded by lifespan (here, `AppContext`) lands on every tool call
    at `ctx.request_context.lifespan_context`. That's the bridge tool modules
    use to reach our PexipClient — see `tools/_helpers.py::get_client`.

Why this lives separately from server.py: server.py imports every tool module
to register them, and every tool module imports `mcp` from somewhere to call
`@mcp.tool()`. If `mcp` lived in server.py we'd have a circular import. Putting
it here breaks the cycle.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp.server.fastmcp import FastMCP

from pexip_mcp.client import PexipClient
from pexip_mcp.config import PexipSettings

log = logging.getLogger(__name__)


# Use AppContext to hold the PexipClient engine so tool modules can reach it via the request context.
@dataclass
class AppContext:
    """Shared per-server state handed to tool calls through `ctx.request_context.lifespan_context`."""

    pexip: PexipClient
    # When False, the generic CRUD tools refuse to mutate security-critical
    # resources (SSH keys, roles, auth/SSO, certs). See resource_crud.py.
    allow_security_resources: bool = False


# Use _tool_is_read_only to tell a read tool apart from a write/control tool by its annotation.
def _tool_is_read_only(tool: object) -> bool:
    """True only when the tool's annotations mark it readOnlyHint=True."""
    ann = getattr(tool, "annotations", None)
    return bool(ann and ann.readOnlyHint)


# Platform-lifecycle command tools: misuse of any of these can replace or
# compromise the whole deployment (restore over all state, import trust anchors,
# upgrade/ship arbitrary software, spin infra). Gated off unless
# PEXIP_ALLOW_PLATFORM_TOOLS=true, even when writes are otherwise enabled.
PLATFORM_TOOLS: frozenset[str] = frozenset(
    {
        "backup_create",
        "backup_restore",
        "certificates_import",
        "start_cloud_node",
        "take_snapshot",
        "platform_upgrade",
        "upload_software_bundle",
    }
)


# Use enforce_platform_gate to remove the platform-lifecycle tools from the catalog.
def enforce_platform_gate(mcp_instance: FastMCP) -> list[str]:
    """Remove the platform-lifecycle command tools; return the removed names (sorted).

    Runs only when writes are enabled but PEXIP_ALLOW_PLATFORM_TOOLS is not set,
    so a compromised/injected agent cannot reach backup-restore, upgrade, cert
    import, etc. through the normal write surface. Idempotent.
    """
    manager = mcp_instance._tool_manager
    removed = [name for name in PLATFORM_TOOLS if name in manager._tools]
    for name in removed:
        manager.remove_tool(name)
    return sorted(removed)


# Use enforce_read_only to strip every mutating tool from the catalog when read-only mode is on.
def enforce_read_only(mcp_instance: FastMCP) -> list[str]:
    """Remove every non-read-only tool from the server; return the removed names (sorted).

    Read-only mode (PEXIP_READ_ONLY=true) is a server-side safety gate. The MCP
    `readOnlyHint` annotation is only advice the client may ignore — this instead
    *unregisters* every create/update/delete/control tool, so an LLM cannot call
    them at all, leaving only list/get/schema reads. Idempotent: calling it again
    finds nothing left to remove.
    """
    manager = mcp_instance._tool_manager
    removed = [name for name, tool in manager._tools.items() if not _tool_is_read_only(tool)]
    for name in removed:
        manager.remove_tool(name)
    return sorted(removed)


# Use apply_startup_policy to enforce read-only / write-mode policy on the tool catalog.
def apply_startup_policy(server: FastMCP, settings: PexipSettings) -> None:
    """Apply the read-only / write-enabled policy to the server's tool catalog.

    Extracted so it can run in BOTH transports. The stdio path drives it from
    `lifespan`; the `--http` path must call it EAGERLY (see __main__._run_http),
    because the streamable-HTTP app hard-codes its own lifespan and never runs
    ours — so relying on the lifespan chain would leave the read-only gate
    unenforced on the network transport. Idempotent (enforce_read_only is).
    """
    if not settings.verify_tls:
        log.warning(
            "TLS verification disabled (PEXIP_VERIFY_TLS=false) — "
            "credentials are sent without certificate validation. Use only for lab/dev."
        )
    if settings.read_only:
        removed = enforce_read_only(server)
        remaining = len(server._tool_manager._tools)
        log.warning(
            "PEXIP_READ_ONLY enabled (default) — removed %d write/control tools; "
            "%d read-only tools remain.",
            len(removed),
            remaining,
        )
    else:
        # Writes are enabled — make that a loud, deliberate signal, not a silent default.
        writable = sum(
            1 for t in server._tool_manager._tools.values() if not _tool_is_read_only(t)
        )
        log.warning(
            "PEXIP_READ_ONLY=false — the mutating admin surface is ENABLED "
            "(%d create/update/delete/control tools callable). Security-critical "
            "resources remain gated unless PEXIP_ALLOW_SECURITY_RESOURCES=true.",
            writable,
        )
        if not settings.allow_platform_tools:
            gated = enforce_platform_gate(server)
            if gated:
                log.warning(
                    "Platform-lifecycle tools gated off (%d removed): %s. Set "
                    "PEXIP_ALLOW_PLATFORM_TOOLS=true to expose them.",
                    len(gated),
                    ", ".join(gated),
                )
        else:
            log.warning(
                "PEXIP_ALLOW_PLATFORM_TOOLS=true — platform-lifecycle tools "
                "(backup/restore, upgrade, cert import, software upload, ...) "
                "are exposed to the client."
            )
        if settings.allow_security_resources:
            log.warning(
                "PEXIP_ALLOW_SECURITY_RESOURCES=true — generic CRUD may now mutate "
                "SSH keys, admin roles/permissions, auth/SSO, and TLS/CA certificates."
            )


# Use lifespan to manage the server's full lifecycle: Startup, Run, Shutdown.
@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Build the PexipClient on startup, hand it to the server, and close it on shutdown."""
    # 1. STARTUP: Read the .env settings and build the engine (auth mode chosen in config).
    settings = PexipSettings()
    apply_startup_policy(server, settings)
    client = PexipClient.from_settings(settings)
    try:
        # 2. RUN: Pass the object to the server. The function pauses here while the server is running.
        yield AppContext(
            pexip=client,
            allow_security_resources=settings.allow_security_resources,
        )
    finally:
        # 3. SHUTDOWN: When the server is turned off, cleanly close network connections.
        await client.aclose()


# Use mcp as the singleton FastMCP server instance. Other files import this to register tools.
mcp = FastMCP("pexip-mgmt", lifespan=lifespan)
