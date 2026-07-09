"""Async HTTP client for the Pexip Infinity Management API.

The Management Node exposes its admin REST API at https://<host>/api/admin/. It
has four sibling sub-APIs we care about, all reached by changing one path segment:

  - configuration/v1/<resource>/   — long-lived config (VMRs, aliases, users, ...)
  - status/v1/<resource>/          — live snapshots (active conferences, nodes)
  - history/v1/<resource>/         — post-call records (CDR-style)
  - command/v1/<scope>/<action>/   — control actions (mute, lock, disconnect)

This module is just transport: auth, JSON in/out, 429 retry. The tool layer in
`pexip_mcp.tools.*` decides which sub-API and resource to call.
"""
from __future__ import annotations

import asyncio
import logging
import re
import secrets
import time
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

import httpx
import jwt

from pexip_mcp import audit

if TYPE_CHECKING:
    from pexip_mcp.config import PexipSettings

logger = logging.getLogger(__name__)


# A single Pexip API path segment: resource names (lowercase + underscore),
# integer ids, UUIDs, and command scopes/actions all fit this. Deliberately
# excludes "/", "\", "..", whitespace, and control chars so a caller-controlled
# value cannot traverse to a different endpoint than the tool intended.
_SAFE_SEGMENT_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


# Use _safe_segment to validate a caller-controlled value before it becomes an API path segment.
def _safe_segment(value: Any, *, kind: str) -> str:
    """Return str(value) if it is a single safe path segment, else raise PexipError(400).

    Guards f-string path construction against traversal / allowlist bypass: an
    id or resource name containing "/" or ".." would otherwise reach a different
    Management-API endpoint than the tool scoped itself to.
    """
    text = str(value)
    if not _SAFE_SEGMENT_RE.match(text) or ".." in text:
        raise PexipError(
            400,
            {kind: [f"Invalid {kind} {text!r}: must not contain path separators."]},
        )
    return text


# Use _safe_resource_path to validate a resource that may legitimately be multi-segment.
def _safe_resource_path(resource: str) -> str:
    """Validate each "/"-separated segment of a resource path (e.g. backplane/<id>/media_stream).

    Some status/history resources are addressed by a nested path. Each segment
    must still be a safe segment, so a value like "backplane/../global" is
    rejected while "worker_vm/12/statistics" passes.
    """
    for segment in resource.split("/"):
        if segment:
            _safe_segment(segment, kind="resource")
    return resource


# Use PexipError to surface server-side failures with the HTTP status and parsed body attached.
class PexipError(Exception):
    """Pexip Management API error with the server's HTTP status and body attached.

    Raised by `_check` whenever Pexip returns a non-2xx. Tool modules often
    catch it to convert specific statuses into friendlier results (e.g.
    a 404 on disconnect_participant becomes `{"note": "already disconnected"}`),
    reading `.status_code` / `.body`. Otherwise it propagates to the MCP layer
    and becomes a tool-call error the client sees.

    `upstream=True` marks errors that came from the Management Node itself. For
    those, the *client-facing string* is deliberately generic — status code plus
    a correlation id — so a raw upstream body (which may carry internal detail)
    is never handed to the model/client. The full detail is logged internally
    under the same correlation id (see `_check`). Errors the tools raise
    themselves (validation, guards) keep `upstream=False`, so their helpful
    messages stay visible to the LLM.
    """

    def __init__(
        self,
        status_code: int,
        body: Any,
        message: str | None = None,
        *,
        upstream: bool = False,
        correlation_id: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.body = body
        self.upstream = upstream
        self.correlation_id = correlation_id or secrets.token_hex(4)
        if upstream:
            # Never expose the raw upstream body to the client; give a ref instead.
            text = f"Pexip API error {status_code} (ref {self.correlation_id})"
        else:
            text = message or f"Pexip API error {status_code}: {body}"
        super().__init__(text)

    # Use detail to get the full internal description (with body) for logging.
    def detail(self) -> str:
        """Full internal string including the body — for server-side logs only."""
        return f"Pexip API error {self.status_code} (ref {self.correlation_id}): {self.body}"


# Use PexipClient as the single async wrapper around the Management API.
class PexipClient:
    """Async wrapper for the Pexip Infinity Management API.

    The `api` keyword on each method selects which sub-API to hit ("configuration",
    "status", or "history"); control actions go through `command(scope, action, data)`.
    429 rate-limit responses are retried with backoff (honors Retry-After when set,
    otherwise exponential up to max_retries).
    """

    def __init__(
        self,
        host: str,
        username: str | None = None,
        password: str | None = None,
        verify_tls: bool = True,
        timeout: float = 30.0,
        max_retries: int = 3,
        *,
        auth: httpx.Auth | None = None,
        identity: str | None = None,
    ) -> None:
        """Build the underlying httpx client pinned to /api/admin/.

        Auth is either passed in explicitly (`auth=`, e.g. a PexipOAuth2Auth) or
        built from `username`/`password` as HTTP Basic. Most callers should use
        `PexipClient.from_settings(...)` which picks the right one from config;
        the username/password path is kept for tests and simple basic-auth use.

        `identity` labels this credential in audit logs; it falls back to the
        basic-auth username, or "credential" when nothing else is known.
        """
        if auth is None:
            if username is None or password is None:
                raise ValueError(
                    "PexipClient needs either auth= or both username and password."
                )
            auth = httpx.BasicAuth(username, password)
        self._identity = identity or (f"basic:{username}" if username else "credential")
        self._max_retries = max_retries
        self._client = httpx.AsyncClient(
            base_url=f"https://{host}/api/admin/",
            auth=auth,
            verify=verify_tls,
            timeout=timeout,
            headers={"Accept": "application/json"},
        )

    # Use from_settings to build the client with the auth mode chosen in configuration.
    @classmethod
    def from_settings(cls, settings: PexipSettings) -> PexipClient:
        """Construct a PexipClient honoring settings.auth_mode ('basic' or 'oauth2')."""
        if settings.auth_mode == "oauth2":
            auth: httpx.Auth = PexipOAuth2Auth(
                token_url=settings.token_url,
                client_id=settings.oauth2_client_id or "",
                private_key=settings.oauth2_private_key or "",
                scope=settings.oauth2_scope,
                verify_tls=settings.verify_tls,
                timeout=settings.timeout,
            )
            identity = f"oauth2:{settings.oauth2_client_id}"
        else:
            auth = httpx.BasicAuth(settings.username or "", settings.password or "")
            identity = f"basic:{settings.username}"
        return cls(
            host=settings.host,
            verify_tls=settings.verify_tls,
            timeout=settings.timeout,
            max_retries=settings.max_retries,
            auth=auth,
            identity=identity,
        )

    # Use aclose to shut down the underlying HTTP connections on server shutdown.
    async def aclose(self) -> None:
        """Close the httpx client and its connection pool."""
        await self._client.aclose()

    # Use list to fetch a paginated collection of resources (e.g. all VMRs).
    async def list(
        self, resource: str, *, api: str = "configuration", **params: Any
    ) -> dict[str, Any]:
        """GET /<api>/v1/<resource>/ with optional query params (limit, offset, filters)."""
        resource = _safe_resource_path(resource)
        return await self._request("GET", f"{api}/v1/{resource}/", params=params)

    # Use schema to ask the server what fields a resource has (great for discovery / vibe-debugging).
    async def schema(self, resource: str, *, api: str = "configuration") -> dict[str, Any]:
        """GET /<api>/v1/<resource>/schema/ — returns the live JSON schema for that resource."""
        resource = _safe_segment(resource, kind="resource")
        return await self._request(
            "GET", f"{api}/v1/{resource}/schema/", params={"format": "json"}
        )

    # Use get to fetch one resource by its numeric ID.
    async def get(
        self, resource: str, obj_id: int | str, *, api: str = "configuration"
    ) -> dict[str, Any]:
        """GET /<api>/v1/<resource>/<id>/."""
        resource = _safe_segment(resource, kind="resource")
        obj_id = _safe_segment(obj_id, kind="id")
        return await self._request("GET", f"{api}/v1/{resource}/{obj_id}/")

    # Use _audited to time a mutation, emit one audit line, and re-raise on failure.
    async def _audited(
        self, action: str, resource: str, obj_id: object | None, coro: Any
    ) -> Any:
        """Await `coro`, recording a structured audit line for this mutation.

        Success logs at INFO, failure at WARNING with the error's status and
        correlation id (so a client-reported ref maps straight to the audit
        trail). The principal is the per-request OIDC identity if present, else
        this client's credential identity.
        """
        principal = audit.resolve_principal(self._identity)
        start = time.monotonic()
        try:
            result = await coro
        except PexipError as e:
            audit.record(
                action=action,
                resource=resource,
                obj_id=obj_id,
                principal=principal,
                outcome="error",
                status_code=e.status_code,
                duration_ms=int((time.monotonic() - start) * 1000),
                correlation_id=e.correlation_id,
            )
            raise
        audit.record(
            action=action,
            resource=resource,
            obj_id=obj_id,
            principal=principal,
            outcome="ok",
            duration_ms=int((time.monotonic() - start) * 1000),
        )
        return result

    # Use create to POST a new resource; Pexip returns the new object's URI in the Location header.
    async def create(
        self, resource: str, data: dict[str, Any], *, api: str = "configuration"
    ) -> str:
        """POST /<api>/v1/<resource>/ and return the Location URI of the created object.

        The Location URI looks like `/api/admin/configuration/v1/conference/42/`;
        callers typically pass it to `extract_id_from_uri` to get the new integer id.
        """
        resource = _safe_segment(resource, kind="resource")

        async def _work() -> str:
            response = await self._raw("POST", f"{api}/v1/{resource}/", json=data)
            self._check(response)
            return response.headers.get("Location", "")

        return await self._audited("create", resource, None, _work())

    # Use update to PATCH an existing resource. Pexip uses PATCH (partial) not PUT (replace).
    async def update(
        self,
        resource: str,
        obj_id: int | str,
        data: dict[str, Any],
        *,
        api: str = "configuration",
    ) -> None:
        """PATCH /<api>/v1/<resource>/<id>/ with a partial body."""
        resource = _safe_segment(resource, kind="resource")
        obj_id = _safe_segment(obj_id, kind="id")

        async def _work() -> None:
            response = await self._raw("PATCH", f"{api}/v1/{resource}/{obj_id}/", json=data)
            self._check(response)

        await self._audited("update", resource, obj_id, _work())

    # Use delete to permanently remove a resource by id.
    async def delete(
        self, resource: str, obj_id: int | str, *, api: str = "configuration"
    ) -> None:
        """DELETE /<api>/v1/<resource>/<id>/."""
        resource = _safe_segment(resource, kind="resource")
        obj_id = _safe_segment(obj_id, kind="id")

        async def _work() -> None:
            response = await self._raw("DELETE", f"{api}/v1/{resource}/{obj_id}/")
            self._check(response)

        await self._audited("delete", resource, obj_id, _work())

    # Use command to drive live-call control actions (mute, lock, transfer, disconnect, ...).
    async def command(
        self, scope: str, action: str, data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """POST a Command API action and return the parsed JSON body.

        Path: /api/admin/command/v1/<scope>/<action>/. Typical scopes are
        "conference" and "participant". Pexip wraps successful results in
        {"status": "success", "data": {...}} — note that's just the *body*,
        actual HTTP errors (404 on unknown participant, etc.) still come
        through as PexipError via _check.
        """
        scope = _safe_segment(scope, kind="scope")
        action = _safe_segment(action, kind="action")

        async def _work() -> dict[str, Any]:
            response = await self._raw(
                "POST", f"command/v1/{scope}/{action}/", json=data or {}
            )
            self._check(response)
            if not response.content:
                return {}
            return response.json()

        return await self._audited("command", scope, action, _work())

    # Use _request as the internal JSON-in/JSON-out helper everything but create/update/delete uses.
    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        """Send a request, validate the response, and return the parsed JSON body (or {} if empty)."""
        response = await self._raw(method, path, **kwargs)
        self._check(response)
        if not response.content:
            return {}
        return response.json()

    # Use _raw as the lowest-level transport: actually sends bytes, handles 429 backoff.
    async def _raw(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """Send a request, retrying on 429 with backoff up to max_retries.

        Why 429 specifically: Pexip rate-limits aggressively on bursty admin
        traffic (e.g. LLM-driven bulk listings). Retrying transparently here
        keeps tool authors from having to deal with it everywhere. Other 4xx/5xx
        statuses are returned as-is for `_check` to raise.
        """
        response: httpx.Response | None = None
        for attempt in range(self._max_retries + 1):
            response = await self._client.request(method, path, **kwargs)
            if response.status_code != 429:
                return response
            if attempt == self._max_retries:
                return response
            delay = _compute_retry_delay(response, attempt)
            logger.warning(
                "Pexip API rate-limited (429) on %s %s; retrying in %.1fs "
                "(attempt %d/%d)",
                method,
                path,
                delay,
                attempt + 1,
                self._max_retries,
            )
            await asyncio.sleep(delay)
        assert response is not None  # loop runs at least once
        return response

    # Use _check to raise PexipError on any non-2xx response, preserving the server's body.
    @staticmethod
    def _check(response: httpx.Response) -> None:
        """Raise PexipError if the response isn't a 2xx; otherwise return None.

        Upstream errors are marked `upstream=True` so the client sees only a
        generic message + correlation id; the full body is logged here at DEBUG
        under that same id, so operators can correlate a client-reported ref to
        the real Management-Node response without leaking it to the model.
        """
        if response.is_success:
            return
        try:
            body: Any = response.json()
        except ValueError:
            body = response.text
        err = PexipError(response.status_code, body, upstream=True)
        logger.debug("Upstream Pexip error: %s", err.detail())
        raise err


# Use _compute_retry_delay to pick the next 429 backoff: prefer the server's Retry-After hint.
def _compute_retry_delay(response: httpx.Response, attempt: int) -> float:
    """Honor Retry-After (seconds) if present, otherwise exponential backoff. Cap at 30s."""
    retry_after = response.headers.get("Retry-After", "")
    try:
        return min(max(float(retry_after), 0.0), 30.0)
    except ValueError:
        # HTTP-date form not handled — fall back to exponential.
        return min(2.0**attempt, 30.0)


# Use extract_id_from_uri to pull the trailing integer id out of a Pexip resource URI.
def extract_id_from_uri(uri: str) -> int:
    """Pexip resource URIs end with /<id>/. Extract the integer id."""
    parts = [p for p in uri.split("/") if p]
    return int(parts[-1])


# Use PexipOAuth2Auth to attach (and lazily refresh) an OAuth2 bearer token on every request.
class PexipOAuth2Auth(httpx.Auth):
    """httpx auth flow implementing Pexip's OAuth2 management-API authentication.

    Pexip Infinity can issue Management API access tokens at `/oauth/token/` once
    an operator creates an OAuth2 client and enables Management API OAuth2 (it is
    OFF by default — see config.py). Authentication uses the **OAuth2 JWT
    bearer-assertion** profile (RFC 7523): the client signs a short-lived JWT
    with its ES256 private key and exchanges it for an access token, which is
    then sent as `Authorization: Bearer <token>` on subsequent requests.

    The token exchange (per Pexip's docs) is a form POST to the token endpoint:

        grant_type            = client_credentials
        client_assertion_type = urn:ietf:params:oauth:client-assertion-type:jwt-bearer
        client_assertion      = <ES256-signed JWT>
        scope                 = is_admin use_api   (minimum)

    where the JWT claims are sub=iss=client_id, aud=<token_url>, plus iat/exp/jti.

    This class caches the token and refreshes it lazily: when the cached token is
    within `leeway` seconds of expiry, or when the server returns 401 (token
    revoked / clock skew), it fetches a fresh one. A lock serializes concurrent
    refreshes so a burst of tool calls triggers at most one token request.
    """

    def __init__(
        self,
        token_url: str,
        client_id: str,
        private_key: str,
        *,
        scope: str = "is_admin use_api",
        verify_tls: bool = True,
        timeout: float = 30.0,
        token_lifetime: float = 3600.0,
        leeway: float = 60.0,
    ) -> None:
        self._token_url = token_url
        self._client_id = client_id
        self._private_key = private_key
        self._scope = scope
        self._verify_tls = verify_tls
        self._timeout = timeout
        self._token_lifetime = token_lifetime
        self._leeway = leeway
        self._token: str | None = None
        self._expires_at = 0.0  # time.monotonic() deadline
        self._lock = asyncio.Lock()

    # Use async_auth_flow to inject the bearer token and retry once on a 401 with a fresh token.
    async def async_auth_flow(
        self, request: httpx.Request
    ) -> AsyncIterator[httpx.Request]:
        """Attach the cached/fresh bearer token; on 401, refresh once and retry."""
        token = await self._get_token()
        request.headers["Authorization"] = f"Bearer {token}"
        response = yield request
        if response.status_code == 401:
            token = await self._get_token(force_refresh=True)
            request.headers["Authorization"] = f"Bearer {token}"
            yield request

    # Use _get_token to return a cached token or fetch a new one (task-safe via the lock).
    async def _get_token(self, *, force_refresh: bool = False) -> str:
        """Return a valid bearer token, fetching a new one if missing/expired/forced."""
        async with self._lock:
            now = time.monotonic()
            if not force_refresh and self._token is not None and now < self._expires_at:
                return self._token
            token, expires_in = await self._fetch_token()
            self._token = token
            self._expires_at = time.monotonic() + max(expires_in - self._leeway, 0.0)
            return token

    # Use _build_assertion to mint the ES256-signed JWT Pexip expects as the client_assertion.
    def _build_assertion(self) -> str:
        """Sign a short-lived JWT (ES256) with claims sub=iss=client_id, aud=token_url."""
        now = int(time.time())
        claims = {
            "sub": self._client_id,
            "iss": self._client_id,
            "aud": self._token_url,
            "iat": now,
            "exp": now + int(self._token_lifetime),
            "jti": secrets.token_hex(18),
        }
        return jwt.encode(claims, self._private_key, algorithm="ES256", headers={"typ": "JWT"})

    # Use _fetch_token to exchange the signed JWT assertion for a bearer access token.
    async def _fetch_token(self) -> tuple[str, float]:
        """POST the JWT bearer-assertion grant and return (access_token, expires_in_seconds)."""
        assertion = self._build_assertion()
        async with httpx.AsyncClient(verify=self._verify_tls, timeout=self._timeout) as http:
            response = await http.post(
                self._token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_assertion_type": (
                        "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
                    ),
                    "client_assertion": assertion,
                    "scope": self._scope,
                },
                headers={"Accept": "application/json"},
            )
        if not response.is_success:
            try:
                body: Any = response.json()
            except ValueError:
                body = response.text
            # Redact like every other upstream error (see _check): the token
            # endpoint's body can carry internal detail, so hand the caller a
            # correlation id and log the body only at DEBUG.
            err = PexipError(response.status_code, body, upstream=True)
            logger.debug("OAuth2 token request failed: %s", err.detail())
            raise err
        payload = response.json()
        # Pexip's token response may omit expires_in; fall back to the configured lifetime.
        return payload["access_token"], float(payload.get("expires_in", self._token_lifetime))
