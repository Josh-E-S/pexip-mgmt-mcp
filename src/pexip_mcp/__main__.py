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
import json
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
    identity = (
        settings.username
        if settings.auth_mode == "basic"
        else (f"oauth2 client {settings.oauth2_client_id}")
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
    if token and not token.isascii():
        return (
            "REFUSING TO START: PEXIP_MCP_TOKEN contains non-ASCII characters, which "
            "cannot be sent in an HTTP Authorization header.\n"
            "  Generate a safe one:  pexip-mgmt-mcp --generate-token\n"
        )
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


# RFC 9728 Protected Resource Metadata path — where MCP clients discover our IdP.
_PRM_PATH = "/.well-known/oauth-protected-resource"


def _header(scope: dict, name: bytes) -> str:
    """Return a request header decoded as latin-1 (never raises), or ''.

    ASGI delivers headers as raw bytes. latin-1 maps every byte to one code point,
    so a malformed or non-ASCII header value becomes a harmless string instead of
    a decode error that would turn a 401 into a 500.
    """
    for key, value in scope.get("headers") or ():
        if key == name:
            return value.decode("latin-1")
    return ""


async def _send_json(send, status: int, body: dict, extra_headers: dict[str, str] | None = None):
    """Write a small JSON response straight to the ASGI send channel."""
    payload = json.dumps(body).encode()
    headers = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(payload)).encode()),
    ]
    for k, v in (extra_headers or {}).items():
        headers.append((k.lower().encode("latin-1"), v.encode("latin-1")))
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": payload})


class _StaticTokenGate:
    """Pure-ASGI gate: every HTTP request must carry `Authorization: Bearer <token>`.

    Pure ASGI (not Starlette's BaseHTTPMiddleware) so the streamable-HTTP app's
    SSE responses pass through untouched and no cross-task context bridge is
    introduced. The comparison is constant-time over bytes, so a non-ASCII or
    malformed header is simply a mismatch (401), never a TypeError (500).
    """

    def __init__(self, app, token: str) -> None:
        self.app = app
        # Compared as raw bytes against the raw header bytes: no decoding step
        # can fail, whatever the client sends. _check_safe_to_bind has already
        # refused non-ASCII tokens, so utf-8 here equals the bytes on the wire.
        self._expected = f"Bearer {token}".encode("utf-8")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        provided = b""
        for key, value in scope.get("headers") or ():
            if key == b"authorization":
                provided = value
                break
        if not hmac.compare_digest(provided, self._expected):
            await _send_json(send, 401, {"error": "unauthorized"})
            return
        await self.app(scope, receive, send)


class _OIDCGate:
    """Pure-ASGI gate validating OIDC bearer JWTs for the streamable-HTTP transport.

    On success it attaches the caller to the ASGI scope the way the MCP SDK's own
    auth middleware does (`scope["user"]` as an `AuthenticatedUser`, `scope["auth"]`
    with the token's scopes). That is what makes the SDK's session manager bind
    each `mcp-session-id` to the credential that created it and answer any other
    principal's request on that session with 404 "Session not found", exactly as
    if the session did not exist. The binding lives and dies with the session
    (terminate / idle timeout), with no table of our own to keep consistent.

    On failure it answers 401 with an RFC 9728 `WWW-Authenticate` challenge that
    points at the PRM document, which is served without a token so clients can
    discover the IdP.

    The principal is also exposed as `scope["pexip_principal"]` and set in the
    audit contextvar for the duration of the request, for log attribution.
    """

    def __init__(self, app, validator, prm_url: str) -> None:
        # Bound once here rather than imported per request on the hot path.
        from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
        from mcp.server.auth.provider import AccessToken
        from starlette.authentication import AuthCredentials

        from pexip_mcp import audit
        from pexip_mcp.oidc import OIDCValidationError, _extract_scopes, principal_of

        self.app = app
        self._validator = validator
        self._prm_url = prm_url
        self._audit = audit
        self._AuthenticatedUser = AuthenticatedUser
        self._AccessToken = AccessToken
        self._AuthCredentials = AuthCredentials
        self._OIDCValidationError = OIDCValidationError
        self._extract_scopes = _extract_scopes
        self._principal_of = principal_of

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if scope.get("path") == _PRM_PATH:
            await self.app(scope, receive, send)
            return

        header = _header(scope, b"authorization")
        try:
            claims = self._validator.verify(header)
        except self._OIDCValidationError:
            await _send_json(
                send,
                401,
                {"error": "unauthorized"},
                {"WWW-Authenticate": f'Bearer realm="mcp", resource_metadata="{self._prm_url}"'},
            )
            return

        principal = self._principal_of(claims)
        scopes = sorted(self._extract_scopes(claims))
        exp = claims.get("exp")
        access_token = self._AccessToken(
            token=header.split(" ", 1)[1].strip() if " " in header else header,
            client_id=principal,
            scopes=scopes,
            expires_at=int(exp) if isinstance(exp, (int, float)) else None,
            subject=str(claims["sub"]) if claims.get("sub") is not None else None,
            claims=dict(claims),
        )
        scope["user"] = self._AuthenticatedUser(access_token)
        scope["auth"] = self._AuthCredentials(scopes)
        scope["pexip_principal"] = principal

        token = self._audit.current_principal.set(principal)
        try:
            await self.app(scope, receive, send)
        finally:
            self._audit.current_principal.reset(token)


def _prm_url(settings) -> str:
    """Absolute URL of the PRM document for the WWW-Authenticate challenge.

    Prefers PEXIP_MCP_PUBLIC_URL. Falls back to the OIDC audience only when it is
    itself an http(s) URL; an `api://...` style audience is not fetchable, so in
    that case the path alone is returned and operators should set the public URL.
    """
    base = (getattr(settings, "mcp_public_url", None) or "").rstrip("/")
    if not base:
        aud = getattr(settings, "oidc_audience", None) or ""
        if aud.lower().startswith(("https://", "http://")):
            base = aud.rstrip("/")
    return base + _PRM_PATH if base else _PRM_PATH


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


def _transport_security(host: str, settings):
    """Host/Origin allow-list for the streamable-HTTP transport (DNS-rebinding protection).

    The FastMCP instance is created with the SDK default host (loopback), which
    makes the SDK enable protection keyed to loopback Host values only. That is
    right for a loopback bind. For any other bind the SDK default would reject
    every request (421) because the Host clients send is never loopback, so:

    - loopback bind: protection on; loopback hosts plus PEXIP_MCP_ALLOWED_HOSTS
      (a tunnel or proxy forwards its public hostname as Host, list it there);
    - non-loopback bind with PEXIP_MCP_ALLOWED_HOSTS: protection on; those hosts,
      loopback, and the bind address itself when it is a specific one;
    - non-loopback bind with nothing configured: protection explicitly OFF, with
      a warning. Reaching the server by IP (the Docker quick start) keeps
      working, and the operator is told how to turn protection on.
    """
    from mcp.server.transport_security import TransportSecuritySettings

    extra_hosts = settings.mcp_allowed_hosts_list if settings else []
    extra_origins = settings.mcp_allowed_origins_list if settings else []
    loopback_bind = host in _LOOPBACK_HOSTS
    if not loopback_bind and not extra_hosts:
        print(
            "  WARNING: non-loopback bind with no PEXIP_MCP_ALLOWED_HOSTS; Host-header "
            "(DNS-rebinding) protection is OFF. Set PEXIP_MCP_ALLOWED_HOSTS to the "
            "hostname(s) clients use to turn it on.",
            file=sys.stderr,
        )
        return TransportSecuritySettings(enable_dns_rebinding_protection=False)
    hosts = ["127.0.0.1", "127.0.0.1:*", "localhost", "localhost:*", "[::1]", "[::1]:*"]
    if not loopback_bind and host not in ("0.0.0.0", "::"):
        bind = f"[{host}]" if ":" in host else host
        hosts += [bind, f"{bind}:*"]
    origins = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=hosts + extra_hosts,
        allowed_origins=origins + extra_origins,
    )


# Use _build_http_app to wrap the FastMCP streamable-http app with the chosen downstream auth.
def _build_http_app(token: str | None, oidc_validator: object | None = None, settings=None):
    """Return the ASGI app for the --http transport: FastMCP mounted at / behind a gate.

    FastMCP gives us the MCP protocol as a Starlette/ASGI app; we mount that
    inside a thin Starlette wrapper and layer downstream auth on top:
      - if `oidc_validator` is given, every request must carry a valid OIDC
        bearer JWT (validated against the operator's IdP), sessions are bound to
        the principal that opened them, and a PRM discovery document is
        published so spec-aware MCP clients can find the IdP;
      - else if `token` is set, a constant-time static bearer-token check runs;
      - else no auth (only reached on a loopback bind).

    Both gates are pure ASGI callables (see _StaticTokenGate / _OIDCGate), not
    Starlette BaseHTTPMiddleware, so streamed responses are passed through
    natively and no cross-task context bridge sits between request and tool.

    Starlette does NOT run a mounted sub-app's lifespan, so we explicitly drive
    the inner app's lifespan from the wrapper. That inner lifespan is what builds
    the shared PexipClient and applies read-only / security-resource enforcement
    (see mcp_app.lifespan); without this delegation the transport would 500 on
    the first real call and the read-only gate would never run.
    """
    from contextlib import asynccontextmanager

    from starlette.applications import Starlette
    from starlette.routing import Mount, Route

    from pexip_mcp.server import mcp

    inner = mcp.streamable_http_app()

    @asynccontextmanager
    async def lifespan(_app):
        # Enter the mounted app's own lifespan so its startup/shutdown actually run.
        async with inner.router.lifespan_context(inner):
            yield

    # PRM route (if any) must precede the catch-all Mount("/") so it isn't shadowed.
    routes: list = []
    if oidc_validator is not None:
        routes.append(Route(_PRM_PATH, _prm_endpoint(settings), methods=["GET"]))
    routes.append(Mount("/", inner))

    app = Starlette(routes=routes, lifespan=lifespan)

    if oidc_validator is not None:
        return _OIDCGate(app, oidc_validator, _prm_url(settings))
    if token:
        return _StaticTokenGate(app, token)
    return app


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

    # Host/Origin allow-list must be set before streamable_http_app() builds the
    # session manager, which is what reads it.
    _mcp.settings.transport_security = _transport_security(host, _settings)

    is_loopback = host in _LOOPBACK_HOSTS
    if oauth_mode:
        auth_desc = f"OIDC (issuer {_settings.oidc_issuer})"
    elif token:
        auth_desc = "static bearer token"
    else:
        auth_desc = "disabled (relying on network layer)"
    print(f"pexip-mgmt-mcp HTTP transport starting on http://{host}:{port}", file=sys.stderr)
    print(
        f"  Bind: {host}{' (loopback only)' if is_loopback else ' (non-loopback)'}", file=sys.stderr
    )
    print(f"  Downstream auth: {auth_desc}", file=sys.stderr)
    if _settings.mcp_allowed_hosts_list:
        print(f"  Allowed hosts: {', '.join(_settings.mcp_allowed_hosts_list)}", file=sys.stderr)

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
