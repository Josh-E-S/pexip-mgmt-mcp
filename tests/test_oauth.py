"""Tests for Pexip's OAuth2 JWT-bearer auth flow (`PexipOAuth2Auth`).

These build a PexipClient with an OAuth2 auth object directly (no settings/env)
and use respx to mock both the token endpoint and a normal API endpoint, so we
can assert the signed assertion is sent and the bearer token is attached,
cached, and refreshed correctly. A real ES256 (P-256) key is generated per test
so the JWT signing path runs for real.
"""
from __future__ import annotations

import httpx
import jwt
import pytest
import respx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from pexip_mcp.client import PexipClient, PexipError, PexipOAuth2Auth

from .conftest import BASE_URL, PEXIP_HOST

TOKEN_URL = f"https://{PEXIP_HOST}/oauth/token/"


def _ec_private_key_pem() -> str:
    """Generate a throwaway ES256 (P-256) private key as a PKCS8 PEM string."""
    key = ec.generate_private_key(ec.SECP256R1())
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()


def _empty_list():
    return httpx.Response(
        200, json={"meta": {"total_count": 0, "limit": 20, "offset": 0}, "objects": []}
    )


def _token_form(request: httpx.Request) -> dict[str, str]:
    """Parse the urlencoded token-request body into a plain dict."""
    return dict(pair.split("=", 1) for pair in request.content.decode().split("&") if pair)


@respx.mock
async def test_oauth_sends_signed_jwt_assertion():
    token = respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "tok-1", "expires_in": 3600})
    )
    respx.get(f"{BASE_URL}/conference/").mock(return_value=_empty_list())

    auth = PexipOAuth2Auth(TOKEN_URL, "cid", _ec_private_key_pem())
    client = PexipClient(host=PEXIP_HOST, auth=auth)
    try:
        await client.list("conference")
    finally:
        await client.aclose()

    form = _token_form(token.calls.last.request)
    assert form["grant_type"] == "client_credentials"
    assert form["client_assertion_type"].endswith("jwt-bearer")
    # The assertion is a real JWT with the expected (URL-decoded) claims.
    import urllib.parse

    assertion = urllib.parse.unquote(form["client_assertion"])
    claims = jwt.decode(assertion, options={"verify_signature": False})
    assert claims["iss"] == "cid"
    assert claims["sub"] == "cid"
    assert claims["aud"] == TOKEN_URL


@respx.mock
async def test_oauth_attaches_bearer_and_caches():
    token = respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "tok-1", "expires_in": 3600})
    )
    api = respx.get(f"{BASE_URL}/conference/").mock(return_value=_empty_list())

    auth = PexipOAuth2Auth(TOKEN_URL, "cid", _ec_private_key_pem())
    client = PexipClient(host=PEXIP_HOST, auth=auth)
    try:
        await client.list("conference")
        await client.list("conference")
    finally:
        await client.aclose()

    # Token fetched once and reused for the second call.
    assert token.call_count == 1
    assert api.calls.last.request.headers["Authorization"] == "Bearer tok-1"


@respx.mock
async def test_oauth_refreshes_on_401():
    respx.post(TOKEN_URL).mock(
        side_effect=[
            httpx.Response(200, json={"access_token": "tok-1", "expires_in": 3600}),
            httpx.Response(200, json={"access_token": "tok-2", "expires_in": 3600}),
        ]
    )
    api = respx.get(f"{BASE_URL}/conference/").mock(
        side_effect=[httpx.Response(401), _empty_list()]
    )

    auth = PexipOAuth2Auth(TOKEN_URL, "cid", _ec_private_key_pem())
    client = PexipClient(host=PEXIP_HOST, auth=auth)
    try:
        result = await client.list("conference")
    finally:
        await client.aclose()

    assert result["objects"] == []
    # Second (successful) attempt carried the refreshed token.
    assert api.calls.last.request.headers["Authorization"] == "Bearer tok-2"
    assert api.call_count == 2


@respx.mock
async def test_oauth_refetches_after_expiry():
    token = respx.post(TOKEN_URL).mock(
        side_effect=[
            httpx.Response(200, json={"access_token": "tok-1", "expires_in": 3600}),
            httpx.Response(200, json={"access_token": "tok-2", "expires_in": 3600}),
        ]
    )
    respx.get(f"{BASE_URL}/conference/").mock(return_value=_empty_list())

    auth = PexipOAuth2Auth(TOKEN_URL, "cid", _ec_private_key_pem())
    client = PexipClient(host=PEXIP_HOST, auth=auth)
    try:
        await client.list("conference")
        auth._expires_at = 0.0  # simulate the cached token having expired
        await client.list("conference")
    finally:
        await client.aclose()

    assert token.call_count == 2


@respx.mock
async def test_oauth_token_failure_raises_pexiperror():
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(400, json={"error": "invalid_client"})
    )

    auth = PexipOAuth2Auth(TOKEN_URL, "cid", _ec_private_key_pem())
    client = PexipClient(host=PEXIP_HOST, auth=auth)
    try:
        with pytest.raises(PexipError) as exc:
            await client.list("conference")
    finally:
        await client.aclose()

    assert exc.value.status_code == 400
