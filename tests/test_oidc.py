"""Tests for OIDC bearer-token validation (PEXIP_MCP_AUTH_MODE=oauth).

We sign tokens with a local RSA keypair and inject a fake signing-key resolver,
so nothing here touches a real IdP or the network. This mirrors what a real
Entra/Google/Okta token would look like to the validator.
"""
from __future__ import annotations

import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from pexip_mcp.oidc import (
    OIDCValidationError,
    OIDCValidator,
    principal_of,
)

ISSUER = "https://issuer.example.com"
AUDIENCE = "https://mcp.example.com"


@pytest.fixture(scope="module")
def keys():
    """A local RSA keypair as PEM (private for signing, public for verifying)."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_pem = (
        key.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


class _FakeResolver:
    """Stands in for jwt.PyJWKClient — returns a fixed key, no network."""

    def __init__(self, public_pem: str):
        self._key = public_pem

    def get_signing_key_from_jwt(self, token):  # noqa: ARG002 - signature parity
        return type("K", (), {"key": self._key})()


def _make_token(private_pem, **overrides):
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": "user-123",
        "email": "josh@example.com",
        "iat": now,
        "exp": now + 3600,
        "scope": "pexip.read pexip.write",
    }
    claims.update(overrides)
    return jwt.encode(claims, private_pem, algorithm="RS256")


def _validator(public_pem, required_scopes=None):
    return OIDCValidator(
        issuer=ISSUER,
        audience=AUDIENCE,
        required_scopes=required_scopes,
        key_resolver=_FakeResolver(public_pem),
    )


# ── happy path ───────────────────────────────────────────────────────────────


def test_valid_token_accepted(keys):
    private_pem, public_pem = keys
    token = _make_token(private_pem)
    claims = _validator(public_pem).verify(f"Bearer {token}")
    assert claims["sub"] == "user-123"
    assert principal_of(claims) == "josh@example.com"


def test_required_scopes_present(keys):
    private_pem, public_pem = keys
    token = _make_token(private_pem, scope="pexip.read pexip.write extra")
    claims = _validator(public_pem, required_scopes=["pexip.write"]).verify(f"Bearer {token}")
    assert "pexip.write" in claims["scope"]


def test_scp_list_claim_supported(keys):
    # Entra uses "scp" (space string); some IdPs use a list. Both must work.
    private_pem, public_pem = keys
    token = _make_token(private_pem, scope=None, scp=["pexip.read"])
    _validator(public_pem, required_scopes=["pexip.read"]).verify(f"Bearer {token}")


# ── rejection paths ──────────────────────────────────────────────────────────


def test_wrong_audience_rejected(keys):
    private_pem, public_pem = keys
    token = _make_token(private_pem, aud="https://someone-else.example.com")
    with pytest.raises(OIDCValidationError):
        _validator(public_pem).verify(f"Bearer {token}")


def test_wrong_issuer_rejected(keys):
    private_pem, public_pem = keys
    token = _make_token(private_pem, iss="https://evil.example.com")
    with pytest.raises(OIDCValidationError):
        _validator(public_pem).verify(f"Bearer {token}")


def test_expired_token_rejected(keys):
    private_pem, public_pem = keys
    now = int(time.time())
    token = _make_token(private_pem, iat=now - 7200, exp=now - 3600)
    with pytest.raises(OIDCValidationError):
        _validator(public_pem).verify(f"Bearer {token}")


def test_missing_scope_rejected(keys):
    private_pem, public_pem = keys
    token = _make_token(private_pem, scope="pexip.read")
    with pytest.raises(OIDCValidationError) as exc:
        _validator(public_pem, required_scopes=["pexip.write"]).verify(f"Bearer {token}")
    assert "pexip.write" in str(exc.value)


def test_bad_signature_rejected(keys):
    # Sign with a DIFFERENT key than the resolver returns → signature fails.
    _, public_pem = keys
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other_pem = other.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    token = _make_token(other_pem)
    with pytest.raises(OIDCValidationError):
        _validator(public_pem).verify(f"Bearer {token}")


def test_malformed_authorization_header_rejected(keys):
    _, public_pem = keys
    v = _validator(public_pem)
    for header in ("", "Basic abc", "Bearer", "Bearer   "):
        with pytest.raises(OIDCValidationError):
            v.verify(header)


# ── principal derivation ─────────────────────────────────────────────────────


def test_principal_falls_back_to_sub():
    assert principal_of({"sub": "abc"}) == "abc"
    assert principal_of({"preferred_username": "josh"}) == "josh"
    assert principal_of({}) == "unknown"
