"""Tests for settings validation and auth-mode client selection.

The `clean_env` fixture strips any ambient PEXIP_* vars (and points the .env
loader at an empty dir) so these assertions depend only on the kwargs each test
passes, not on the environment the suite happens to run in.
"""
from __future__ import annotations

import os

import httpx
import pytest

from pexip_mcp.client import PexipClient, PexipOAuth2Auth
from pexip_mcp.config import PexipSettings


@pytest.fixture
def clean_env(monkeypatch, tmp_path):
    for key in list(os.environ):
        if key.startswith("PEXIP_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)  # no .env here
    yield


def test_basic_mode_missing_password_raises(clean_env):
    with pytest.raises(ValueError, match="PEXIP_PASSWORD"):
        PexipSettings(host="h", username="u")


def test_oauth_mode_missing_client_id_raises(clean_env):
    with pytest.raises(ValueError, match="PEXIP_OAUTH2_CLIENT_ID"):
        PexipSettings(host="h", auth_mode="oauth2", oauth2_private_key="k")


def test_basic_mode_valid(clean_env):
    s = PexipSettings(host="h", username="u", password="p")
    assert s.auth_mode == "basic"


def test_token_url_default_and_override(clean_env):
    s = PexipSettings(host="h", auth_mode="oauth2", oauth2_client_id="c", oauth2_private_key="k")
    assert s.token_url == "https://h/oauth/token/"

    s2 = PexipSettings(
        host="h",
        auth_mode="oauth2",
        oauth2_client_id="c",
        oauth2_private_key="k",
        oauth2_token_url="https://proxy.example.com/token/",
    )
    assert s2.token_url == "https://proxy.example.com/token/"


async def test_from_settings_basic_builds_basic_auth(clean_env):
    s = PexipSettings(host="h", username="u", password="p")
    client = PexipClient.from_settings(s)
    try:
        assert isinstance(client._client.auth, httpx.BasicAuth)
    finally:
        await client.aclose()


async def test_from_settings_oauth_builds_oauth_auth(clean_env):
    s = PexipSettings(host="h", auth_mode="oauth2", oauth2_client_id="c", oauth2_private_key="k")
    client = PexipClient.from_settings(s)
    try:
        assert isinstance(client._client.auth, PexipOAuth2Auth)
        assert client._client.auth._token_url == "https://h/oauth/token/"
    finally:
        await client.aclose()
