"""Audit logging for state-changing Management API calls.

Every mutation the server performs against Pexip (create / update / delete /
command) emits one structured line on the `pexip_mcp.audit` logger. This is the
server's accountability record — "who did what, to which object, with what
outcome" — and in the shared `--http` + OIDC topology it is the *authoritative*
per-user trail, because Infinity only sees the one service credential the server
authenticates with (see docs/identity.md).

The principal is resolved in this order:
  1. `current_principal` — a per-request identity set by the OIDC middleware
     (the token's sub/email) when downstream OAuth is in use;
  2. otherwise the client's own credential identity (basic user / oauth2 client),
     which is all that exists in stdio / static-token deployments.

Lines are key=value, one per call, so they grep and ship cleanly without a JSON
pipeline. Secrets never appear here — only the action, resource, resolved id,
outcome, latency, and principal.
"""
from __future__ import annotations

import logging
from contextvars import ContextVar

# Per-request caller identity, set by the OIDC middleware when available.
# Defaults to None so the client falls back to its credential identity.
current_principal: ContextVar[str | None] = ContextVar("current_principal", default=None)

audit_logger = logging.getLogger("pexip_mcp.audit")


# Use resolve_principal to pick the best available identity for an audit line.
def resolve_principal(fallback: str) -> str:
    """Return the per-request principal if one is set, else the given fallback."""
    return current_principal.get() or fallback


# Use record to emit one structured audit line for a mutating call.
def record(
    *,
    action: str,
    resource: str,
    principal: str,
    outcome: str,
    duration_ms: int,
    obj_id: object | None = None,
    status_code: int | None = None,
    correlation_id: str | None = None,
) -> None:
    """Emit a single key=value audit line. Success at INFO, failure at WARNING."""
    parts = [
        "audit",
        f"action={action}",
        f"resource={resource}",
    ]
    if obj_id is not None:
        parts.append(f"id={obj_id}")
    parts.append(f"outcome={outcome}")
    if status_code is not None:
        parts.append(f"status={status_code}")
    parts.append(f"duration_ms={duration_ms}")
    parts.append(f"principal={principal}")
    if correlation_id is not None:
        parts.append(f"ref={correlation_id}")
    line = " ".join(parts)
    if outcome == "ok":
        audit_logger.info(line)
    else:
        audit_logger.warning(line)
