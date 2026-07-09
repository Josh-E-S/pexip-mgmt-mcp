"""CLI entry point for `pexip-mgmt-mcp`.

What you run from the shell. Three modes, picked by argparse flags:

  - (default)        Run the MCP server over stdio. This is what Claude Desktop
                     and other MCP clients launch — they speak JSON-RPC over
                     the child process's stdin/stdout. No port, no network.

  - --http           Run over MCP's "streamable HTTP" transport instead, served
                     by uvicorn. Use this when the MCP client is remote (e.g.
                     behind Cloudflare Tunnel, Cloud Run, Fly.io).

  - --healthcheck    Don't start anything; just probe the Pexip Management Node
                     using PEXIP_* env vars and exit 0/1. Handy for container
                     health probes and CI.

Safe-by-default bind: --http defaults to 127.0.0.1 so the listener is loopback
only. Binding to anything else without setting PEXIP_MCP_TOKEN is *refused* —
MCP-over-HTTP has no built-in auth, so we won't accidentally expose an
unauthenticated tool surface to the open internet. See `_check_safe_to_bind`.
"""
from __future__ import annotations

import argparse
import asyncio
import hmac
import os
import sys


_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}

# Minimum length for PEXIP_MCP_TOKEN. The bind guard accepts any non-empty
# token, but a short/guessable one on a public bind defeats the whole point,
# so we refuse to start with a weak one.
_MIN_TOKEN_LEN = 32

# Use _healthcheck to validate connectivity to the Management Node from CLI (--healthcheck).
async def _healthcheck() -> int:
    """Probe the Pexip Management Node using PEXIP_* env vars. Return 0 on success, 1 on failure.

    "Success" means we authenticated and Pexip returned the conference schema —
    enough to prove host, TLS, and creds all work. Used as a container/CI probe.
    """
    # Lazy imports: the healthcheck path doesn't need httpx/pydantic startup cost
    # to be paid eagerly when this module is imported for `mcp.run()`.
    from pexip_mcp.client import PexipClient, PexipError
    from pexip_mcp.config import PexipSettings

    try:
        settings = PexipSettings()
    except Exception as e:
        print(f"FAIL: invalid configuration: {e}", file=sys.stderr)
        return 1

    client = PexipClient.from_settings(settings)
    identity = settings.username if settings.auth_mode == "basic" else (
        f"oauth2 client {settings.oauth2_client_id}"
    )
    try:
        await client.schema("conference")
        print(f"OK: connected to {settings.host} as {identity}, schema fetched")
        return 0
    except PexipError as e:
        print(f"FAIL: Pexip API error {e.status_code} (ref {e.correlation_id})", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"FAIL: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    finally:
        await client.aclose()


# Use _check_safe_to_bind to refuse non-loopback binds that have no bearer token in front of them.
def _check_safe_to_bind(host: str, token: str | None, oauth: bool = False) -> str | None:
    """Return None if safe to start, otherwise an error message string.

    Rules: (1) any bearer token that is set must be at least _MIN_TOKEN_LEN
    chars — a weak token gives a false sense of security on a public bind;
    (2) a non-loopback bind requires downstream auth, which is satisfied by
    either a bearer token OR OIDC (oauth) mode, so we never expose an
    unauthenticated MCP server on a public-routable host.
    """
    if token and len(token) < _MIN_TOKEN_LEN:
        return (
            f"REFUSING TO START: PEXIP_MCP_TOKEN is too short "
            f"({len(token)} chars); require at least {_MIN_TOKEN_LEN}.\n"
            f"  Generate a strong one:  pexip-mgmt-mcp --generate-token\n"
        )
    if host in _LOOPBACK_HOSTS:
        return None
    if token or oauth:
        return None
    return (
        f"REFUSING TO START: --host={host!r} is not a loopback address and no "
        f"downstream auth is configured.\n\n"
        f"  Choose one:\n"
        f"    - bind to 127.0.0.1 (the default) and reach it over a private network, or\n"
        f"    - set PEXIP_MCP_TOKEN (see: pexip-mgmt-mcp --generate-token) for a\n"
        f"      static bearer token, or\n"
        f"    - set PEXIP_MCP_AUTH_MODE=oauth with PEXIP_OIDC_ISSUER / "
        f"PEXIP_OIDC_AUDIENCE to validate OIDC tokens from your own IdP.\n"
    )


# Use _generate_token to print a strong bearer token for PEXIP_MCP_TOKEN.
def _generate_token() -> None:
    """Print a fresh strong token and the env line to paste. Not stored anywhere."""
    import secrets

    token = secrets.token_urlsafe(32)  # ~43 chars, comfortably past the minimum
    print(f"\n  PEXIP_MCP_TOKEN={token}\n")
    print(
        "  Save this now — it is not stored anywhere. Set it in the server's env,\n"
        "  and send the SAME value from your MCP client as:\n"
        "      Authorization: Bearer <token>\n",
        file=sys.stderr,
    )


# Use _build_http_app to wrap the FastMCP streamable-http app with the chosen downstream auth.
def _build_http_app(token: str | None, oidc_validator: object | None = None, settings=None):
    """Return a Starlette app mounting the FastMCP streamable-http app at /.

    FastMCP gives us the MCP protocol as a Starlette/ASGI app; we mount that
    inside a thin Starlette wrapper so we can layer downstream auth on top:
      - if `oidc_validator` is given, every request must carry a valid OIDC
        bearer JWT (validated against the operator's IdP); a PRM discovery
        document is also published so spec-aware MCP clients can find the IdP;
      - else if `token` is set, a constant-time static bearer-token check runs;
      - else no auth (only reached on a loopback bind).

    Starlette does NOT run a mounted sub-app's lifespan, so we explicitly drive
    the inner app's lifespan from the wrapper. That inner lifespan is what builds
    the shared PexipClient and applies read-only / security-resource enforcement
    (see mcp_app.lifespan); without this delegation the transport would 500 on
    the first real call and the read-only gate would never run.
    """
    from contextlib import asynccontextmanager

    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse
    from starlette.routing import Mount, Route

    from pexip_mcp.server import mcp

    inner = mcp.streamable_http_app()

    @asynccontextmanager
    async def lifespan(_app):
        # Enter the mounted app's own lifespan so its startup/shutdown actually run.
        async with inner.router.lifespan_context(inner):
            yield

    middleware = []
    # PRM route (if any) must precede the catch-all Mount("/") so it isn't shadowed.
    routes: list = []

    if oidc_validator is not None:
        from pexip_mcp import audit
        from pexip_mcp.oidc import OIDCValidationError, principal_of

        class OIDCAuth(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                # Let unauthenticated clients discover how to authenticate.
                if request.url.path == _PRM_PATH:
                    return await call_next(request)
                header = request.headers.get("authorization", "")
                try:
                    claims = oidc_validator.verify(header)
                except OIDCValidationError:
                    # Point clients at the PRM document per RFC 9728.
                    return JSONResponse(
                        {"error": "unauthorized"},
                        status_code=401,
                        headers={
                            "WWW-Authenticate": (
                                'Bearer realm="mcp", '
                                f'resource_metadata="{_prm_url(settings)}"'
                            )
                        },
                    )
                # Attribute the call: expose the principal on the scope and set the
                # audit contextvar so PexipClient's audit lines carry the identity.
                principal = principal_of(claims)
                request.scope["pexip_principal"] = principal
                token = audit.current_principal.set(principal)
                try:
                    return await call_next(request)
                finally:
                    audit.current_principal.reset(token)

        middleware.append(Middleware(OIDCAuth))
        routes.append(Route(_PRM_PATH, _prm_endpoint(settings), methods=["GET"]))

    routes.append(Mount("/", inner))

    if token and oidc_validator is None:
        expected = f"Bearer {token}"

        class BearerAuth(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                provided = request.headers.get("authorization", "")
                # hmac.compare_digest, not ==, so token comparison is constant-time
                # (defends against timing-based token-recovery attacks).
                if not hmac.compare_digest(provided, expected):
                    return JSONResponse({"error": "unauthorized"}, status_code=401)
                return await call_next(request)

        middleware.append(Middleware(BearerAuth))

    return Starlette(middleware=middleware, routes=routes, lifespan=lifespan)


# RFC 9728 Protected Resource Metadata path — where MCP clients discover our IdP.
_PRM_PATH = "/.well-known/oauth-protected-resource"


def _prm_url(settings) -> str:
    """Best-effort absolute URL of the PRM document (used in WWW-Authenticate)."""
    base = getattr(settings, "oidc_audience", None) or ""
    return base.rstrip("/") + _PRM_PATH if base else _PRM_PATH


def _prm_endpoint(settings):
    """Build the Starlette endpoint that serves the RFC 9728 PRM document."""
    from starlette.responses import JSONResponse

    async def endpoint(_request):
        body = {
            "resource": settings.oidc_audience,
            "authorization_servers": [settings.oidc_issuer],
            "scopes_supported": settings.oidc_required_scopes_list,
        }
        return JSONResponse(body)

    return endpoint


# Use _run_http to start the server over streamable HTTP (instead of stdio) under uvicorn.
def _run_http(host: str, port: int) -> None:
    """Boot the HTTP transport. Refuses to start on a non-loopback bind without PEXIP_MCP_TOKEN."""
    import uvicorn

    # Load config first: it decides the downstream auth mode. Fail closed on a
    # bad config rather than serving with an unknown policy.
    from pexip_mcp.config import PexipSettings
    from pexip_mcp.mcp_app import apply_startup_policy
    from pexip_mcp.server import mcp as _mcp

    try:
        _settings = PexipSettings()
    except Exception as e:  # noqa: BLE001 - surface config errors and refuse to start
        print(f"REFUSING TO START: invalid configuration: {e}", file=sys.stderr)
        sys.exit(2)

    oauth_mode = _settings.mcp_auth_mode == "oauth"
    token = None if oauth_mode else os.environ.get("PEXIP_MCP_TOKEN")

    err = _check_safe_to_bind(host, token, oauth=oauth_mode)
    if err:
        print(err, file=sys.stderr)
        sys.exit(2)

    # Build the OIDC validator up front in oauth mode so a misconfig (e.g. an
    # unreachable issuer for JWKS discovery) fails at startup, not per-request.
    oidc_validator = None
    if oauth_mode:
        from pexip_mcp.oidc import OIDCValidator

        try:
            oidc_validator = OIDCValidator.from_settings(_settings)
        except Exception as e:  # noqa: BLE001 - surface IdP/discovery errors at startup
            print(f"REFUSING TO START: OIDC setup failed: {e}", file=sys.stderr)
            sys.exit(2)

    # Apply the read-only / write policy EAGERLY: the streamable-HTTP app
    # hard-codes its own lifespan and never runs ours, so the read-only gate
    # would otherwise not be enforced on this transport.
    apply_startup_policy(_mcp, _settings)

    is_loopback = host in _LOOPBACK_HOSTS
    if oauth_mode:
        auth_desc = f"OIDC (issuer {_settings.oidc_issuer})"
    elif token:
        auth_desc = "static bearer token"
    else:
        auth_desc = "disabled (relying on network layer)"
    print(f"pexip-mgmt-mcp HTTP transport starting on http://{host}:{port}", file=sys.stderr)
    print(f"  Bind: {host}{' (loopback only)' if is_loopback else ' (non-loopback)'}", file=sys.stderr)
    print(f"  Downstream auth: {auth_desc}", file=sys.stderr)

    uvicorn.run(
        _build_http_app(token, oidc_validator, _settings),
        host=host,
        port=port,
        log_level="info",
    )


# Use main as the CLI entry point: parses args and dispatches to healthcheck, HTTP, or stdio.
def main() -> None:
    """Entry point for the `pexip-mgmt-mcp` console script."""
    parser = argparse.ArgumentParser(
        prog="pexip-mgmt-mcp",
        description="MCP server wrapping the Pexip Infinity Management API.",
    )
    parser.add_argument(
        "--healthcheck",
        action="store_true",
        help="Validate connectivity to the Management Node (using PEXIP_* env vars) "
        "and exit. 0 = ok, 1 = fail.",
    )
    parser.add_argument(
        "--generate-token",
        action="store_true",
        help="Print a strong random value for PEXIP_MCP_TOKEN and exit. Set the same "
        "value in the server env and send it from your client as a Bearer token.",
    )
    parser.add_argument(
        "--http",
        action="store_true",
        help="Run the MCP server over streamable HTTP instead of stdio. "
        "Default bind is 127.0.0.1 (loopback only) — point a reverse proxy "
        "(e.g. Cloudflare Tunnel) at it.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="HTTP bind host (default 127.0.0.1). Non-loopback values require "
        "PEXIP_MCP_TOKEN to be set or the server refuses to start.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", "8000")),
        help="HTTP bind port. Defaults to $PORT if set (Cloud Run / Fly), else 8000.",
    )
    args = parser.parse_args()

    if args.generate_token:
        _generate_token()
        return

    if args.healthcheck:
        sys.exit(asyncio.run(_healthcheck()))

    if args.http:
        _run_http(args.host, args.port)
        return

    from pexip_mcp.server import mcp

    mcp.run()


if __name__ == "__main__":
    main()
