"""OIDC bearer-token validation for the --http transport (downstream auth).

This is the *optional* second rung of the client -> MCP-server auth ladder. The
default rung is a static bearer token (PEXIP_MCP_TOKEN). When
`PEXIP_MCP_AUTH_MODE=oauth`, HTTP clients instead present an OIDC access token
(a JWT) issued by an identity provider the operator already runs — Microsoft
Entra, Google, Okta, or an on-prem OIDC server. We validate that token here.

What we check, using the operator's own IdP (no third-party in the path):
  - signature, against the IdP's published JWKS (public keys);
  - issuer (`iss`) matches the configured issuer;
  - audience (`aud`) matches the configured audience (so a token minted for a
    different app is rejected — this is the anti-"confused deputy" control);
  - expiry (`exp`), with a small clock-skew leeway;
  - required scopes, if the operator configured any.

Validation is local: we fetch the IdP's signing keys once (cached by PyJWKClient)
and verify JWTs offline against them. The only network dependency is reaching the
IdP's JWKS endpoint — which is the operator's own system.

We deliberately reuse `pyjwt` (already a dependency via `pyjwt[crypto]`) rather
than adding an OAuth library, so this introduces no new supply-chain surface.
"""
from __future__ import annotations

from typing import Any, Protocol

import jwt


# Algorithms we accept. Asymmetric only — an OIDC access token is signed by the
# IdP's private key and verified with its public key. HS256 (shared secret) is
# excluded on purpose to avoid the classic algorithm-confusion pitfall.
_ALLOWED_ALGS = ("RS256", "RS384", "RS512", "ES256", "ES384", "ES512")


# Use OIDCValidationError to signal any rejected token; callers turn it into a 401.
class OIDCValidationError(Exception):
    """Raised when a bearer token is missing, malformed, or fails validation."""


# Use SigningKeyResolver as the seam that lets tests inject keys without network.
class SigningKeyResolver(Protocol):
    """Resolves the signing key for a JWT. Production uses jwt.PyJWKClient."""

    def get_signing_key_from_jwt(self, token: str) -> Any:  # pragma: no cover - protocol
        """Return an object with a `.key` attribute usable by jwt.decode."""
        ...


# Use OIDCValidator to verify OIDC access tokens against an operator-run IdP.
class OIDCValidator:
    """Validate OIDC bearer JWTs against a configured issuer/audience/scopes.

    The key resolver is injected so unit tests can supply a local key instead of
    reaching a real JWKS endpoint. `from_settings` wires the production resolver
    (a network-backed, caching `PyJWKClient`).
    """

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        required_scopes: list[str] | None = None,
        key_resolver: SigningKeyResolver,
        leeway: float = 30.0,
    ) -> None:
        self._issuer = issuer
        self._audience = audience
        self._required_scopes = set(required_scopes or [])
        self._key_resolver = key_resolver
        self._leeway = leeway

    # Use from_settings to build a production validator with a JWKS-backed resolver.
    @classmethod
    def from_settings(cls, settings: Any) -> OIDCValidator:
        """Build an OIDCValidator from PexipSettings, discovering the JWKS URL if needed."""
        _require_https(settings.oidc_issuer, "OIDC issuer")
        jwks_uri = settings.oidc_jwks_uri or _discover_jwks_uri(settings.oidc_issuer)
        _require_https(jwks_uri, "OIDC JWKS URI")
        # PyJWKClient caches keys and refreshes on unknown kid; safe to construct once.
        resolver = jwt.PyJWKClient(jwks_uri)
        return cls(
            issuer=settings.oidc_issuer,
            audience=settings.oidc_audience,
            required_scopes=settings.oidc_required_scopes_list,
            key_resolver=resolver,
        )

    # Use verify to validate a raw Bearer header value; returns the token's claims.
    def verify(self, authorization_header: str) -> dict[str, Any]:
        """Validate the `Authorization: Bearer <jwt>` header and return its claims.

        Raises OIDCValidationError on any problem (missing/malformed header,
        bad signature, wrong issuer/audience, expiry, or missing scopes).
        """
        token = _extract_bearer(authorization_header)
        try:
            signing_key = self._key_resolver.get_signing_key_from_jwt(token)
        except Exception as e:  # pyjwt raises various subclasses; treat all as auth failure
            raise OIDCValidationError(f"cannot resolve signing key: {e}") from e

        key = getattr(signing_key, "key", signing_key)
        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                key,
                algorithms=list(_ALLOWED_ALGS),
                audience=self._audience,
                issuer=self._issuer,
                leeway=self._leeway,
                options={"require": ["exp", "iss", "aud"]},
            )
        except jwt.InvalidTokenError as e:
            raise OIDCValidationError(str(e)) from e

        self._check_scopes(claims)
        return claims

    # Use _check_scopes to enforce that the token carries every required scope.
    def _check_scopes(self, claims: dict[str, Any]) -> None:
        """Raise OIDCValidationError unless all required scopes are present."""
        if not self._required_scopes:
            return
        token_scopes = _extract_scopes(claims)
        missing = self._required_scopes - token_scopes
        if missing:
            raise OIDCValidationError(
                f"token missing required scope(s): {' '.join(sorted(missing))}"
            )


# Use principal_of to derive a stable human identifier for logging/audit.
def principal_of(claims: dict[str, Any]) -> str:
    """Best-effort principal for audit lines: email/preferred_username, else sub."""
    for field in ("email", "preferred_username", "upn", "sub"):
        value = claims.get(field)
        if value:
            return str(value)
    return "unknown"


def _extract_bearer(header: str) -> str:
    """Pull the token out of an `Authorization: Bearer <token>` header value."""
    if not header:
        raise OIDCValidationError("missing Authorization header")
    parts = header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise OIDCValidationError("Authorization header is not a Bearer token")
    return parts[1].strip()


def _extract_scopes(claims: dict[str, Any]) -> set[str]:
    """Normalize scopes from either OAuth 'scope' (space string) or 'scp' (str/list)."""
    # Prefer OAuth 'scope'; fall back to 'scp' when scope is absent or null.
    raw = claims.get("scope") or claims.get("scp")
    if raw is None:
        return set()
    if isinstance(raw, str):
        return set(raw.split())
    if isinstance(raw, (list, tuple)):
        return {str(s) for s in raw}
    return set()


def _require_https(url: str, what: str) -> None:
    """Reject a non-HTTPS IdP URL — signing keys must never be fetched over plaintext."""
    if not str(url).lower().startswith("https://"):
        raise OIDCValidationError(f"{what} must use https://, got {url!r}")


def _discover_jwks_uri(issuer: str) -> str:
    """Fetch the IdP's OIDC discovery document and return its jwks_uri.

    Reaches only the operator's configured issuer. Kept import-local so the
    default (token) auth mode never pays for httpx on this path.
    """
    import httpx

    well_known = issuer.rstrip("/") + "/.well-known/openid-configuration"
    resp = httpx.get(well_known, timeout=10.0)
    resp.raise_for_status()
    jwks_uri = resp.json().get("jwks_uri")
    if not jwks_uri:
        raise OIDCValidationError(
            f"OIDC discovery at {well_known} did not contain a jwks_uri"
        )
    return str(jwks_uri)
