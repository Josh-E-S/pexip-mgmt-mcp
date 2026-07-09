"""Configuration loading for the MCP server.

Where settings come from: environment variables prefixed with `PEXIP_` (e.g.
PEXIP_HOST, PEXIP_USERNAME). For local dev, a `.env` file in the working
directory is also picked up. Anything not prefixed `PEXIP_` is ignored.

Why pydantic-settings: it reads env vars + .env into a typed dataclass-ish
object in one step, validates types (e.g. PEXIP_VERIFY_TLS="false" → bool
False), and raises a clear error on the missing required fields at startup
instead of crashing with a KeyError mid-request.

`PexipSettings()` with no args is the standard entry point — it loads env on
construction. `lifespan()` in mcp_app.py and the --healthcheck path in
__main__.py both do this once at startup.

Authentication is selectable via `PEXIP_AUTH_MODE`:

  - "basic"  (default) — local Management Node admin username + password.
               Works out of the box on every Infinity deployment.
  - "oauth2"           — OAuth2 client-credentials. Stronger, but NOT enabled
               by default on Infinity: an operator must first create an OAuth2
               client (Users & Devices > OAuth2 Clients) and enable Management
               API OAuth2. See client.py::PexipOAuth2Auth for the token flow.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Use PexipSettings to load PEXIP_* env vars (or .env entries) into one typed, reusable object.
class PexipSettings(BaseSettings):
    """Configuration for talking to the Pexip Management Node.

    Exactly one auth mode is active at a time (`auth_mode`). The validator
    enforces that the credentials for the chosen mode are present, so a
    misconfiguration fails loudly at startup rather than on the first request.
    """

    model_config = SettingsConfigDict(env_prefix="PEXIP_", env_file=".env", extra="ignore")

    host: str = Field(description="Pexip Management Node hostname or IP, no scheme.")

    auth_mode: Literal["basic", "oauth2"] = Field(
        default="basic",
        description="Authentication mode: 'basic' (local admin user/pass) or 'oauth2'.",
    )

    # --- basic auth (auth_mode="basic") ---
    username: str | None = Field(
        default=None, description="Local Pexip admin username (required when auth_mode=basic)."
    )
    password: str | None = Field(
        default=None, description="Local Pexip admin password (required when auth_mode=basic)."
    )

    # --- oauth2 client-credentials (auth_mode="oauth2") ---
    oauth2_client_id: str | None = Field(
        default=None, description="OAuth2 Client ID (required when auth_mode=oauth2)."
    )
    oauth2_private_key: str | None = Field(
        default=None,
        description="OAuth2 client 'Private key' / secret shown once on client creation "
        "(required when auth_mode=oauth2).",
    )
    oauth2_token_url: str | None = Field(
        default=None,
        description="Override the token endpoint. Defaults to https://<host>/oauth/token/.",
    )
    oauth2_scope: str = Field(
        default="is_admin use_api",
        description="OAuth2 scopes requested with the token. Pexip minimum: 'is_admin use_api'.",
    )

    verify_tls: bool = Field(default=True, description="Verify TLS certificate.")
    timeout: float = Field(default=30.0, description="HTTP timeout seconds.")
    max_retries: int = Field(
        default=3, description="Max retries on 429 rate-limit responses."
    )

    read_only: bool = Field(
        default=True,
        description="When true (the default), only read tools (list/get/schema) are "
        "exposed; every create/update/delete/control tool is removed from the catalog "
        "at startup. Set PEXIP_READ_ONLY=false to opt into the mutating admin surface.",
    )

    # --- downstream (client -> MCP server) auth for the --http transport ---
    mcp_auth_mode: Literal["token", "oauth"] = Field(
        default="token",
        description="How HTTP clients authenticate to THIS server: 'token' (a static "
        "bearer token in PEXIP_MCP_TOKEN, the default) or 'oauth' (validate OIDC "
        "bearer JWTs from your own IdP — Entra/Google/Okta/on-prem). Only affects the "
        "--http transport; stdio needs neither.",
    )
    oidc_issuer: str | None = Field(
        default=None,
        description="OIDC issuer URL (required when mcp_auth_mode=oauth). Tokens must "
        "carry this 'iss'. Example: https://login.microsoftonline.com/<tenant>/v2.0 "
        "or https://accounts.google.com.",
    )
    oidc_audience: str | None = Field(
        default=None,
        description="Expected token audience (required when mcp_auth_mode=oauth). The "
        "token's 'aud' must match — bind this to THIS server so tokens for other apps "
        "are rejected.",
    )
    oidc_jwks_uri: str | None = Field(
        default=None,
        description="Override the JWKS URL used to fetch the IdP's signing keys. If "
        "unset, it is discovered from <issuer>/.well-known/openid-configuration.",
    )
    oidc_required_scopes: str = Field(
        default="",
        description="Space-separated scopes a token must contain to be accepted "
        "(e.g. 'pexip.read pexip.write'). Empty means any validly-signed, "
        "correctly-audienced token is accepted.",
    )

    allow_security_resources: bool = Field(
        default=False,
        description="When false (the default), the generic create/update/delete_resource "
        "tools refuse to mutate security-critical resources (SSH keys, admin roles/"
        "permissions, authentication/SSO config, TLS/CA certificates). Set "
        "PEXIP_ALLOW_SECURITY_RESOURCES=true to lift that guard. Has no effect in "
        "read-only mode, where those tools are removed entirely.",
    )

    allow_platform_tools: bool = Field(
        default=False,
        description="When false (the default), the platform-lifecycle command tools "
        "(backup create/restore, certificate import, platform upgrade, software-bundle "
        "upload, cloud-node start, snapshot) are removed at startup even when writes are "
        "enabled — a single injected call to these can replace or compromise the whole "
        "platform. Set PEXIP_ALLOW_PLATFORM_TOOLS=true to expose them. No effect in "
        "read-only mode, where they are already removed.",
    )

    # Use _check_auth_credentials to fail fast when the chosen auth_mode is missing its creds.
    @model_validator(mode="after")
    def _check_auth_credentials(self) -> PexipSettings:
        """Require the credential fields that the selected auth_mode needs."""
        if self.auth_mode == "basic":
            missing = [
                f"PEXIP_{name.upper()}"
                for name, value in (("username", self.username), ("password", self.password))
                if not value
            ]
            if missing:
                raise ValueError(
                    f"auth_mode='basic' requires {' and '.join(missing)} to be set."
                )
        else:  # oauth2
            missing = [
                f"PEXIP_{name.upper()}"
                for name, value in (
                    ("oauth2_client_id", self.oauth2_client_id),
                    ("oauth2_private_key", self.oauth2_private_key),
                )
                if not value
            ]
            if missing:
                raise ValueError(
                    f"auth_mode='oauth2' requires {' and '.join(missing)} to be set."
                )
        return self

    # Use _check_oidc_config to require issuer+audience when downstream OAuth is selected.
    @model_validator(mode="after")
    def _check_oidc_config(self) -> PexipSettings:
        """Require oidc_issuer and oidc_audience when mcp_auth_mode='oauth'."""
        if self.mcp_auth_mode == "oauth":
            missing = [
                f"PEXIP_{name.upper()}"
                for name, value in (
                    ("oidc_issuer", self.oidc_issuer),
                    ("oidc_audience", self.oidc_audience),
                )
                if not value
            ]
            if missing:
                raise ValueError(
                    f"mcp_auth_mode='oauth' requires {' and '.join(missing)} to be set."
                )
        return self

    # Use token_url to resolve the OAuth2 token endpoint (explicit override or host-derived default).
    @property
    def token_url(self) -> str:
        """The OAuth2 token endpoint — explicit `oauth2_token_url` or https://<host>/oauth/token/."""
        return self.oauth2_token_url or f"https://{self.host}/oauth/token/"

    # Use oidc_required_scopes_list to get the required scopes as a parsed list.
    @property
    def oidc_required_scopes_list(self) -> list[str]:
        """Parse the space-separated required-scopes string into a list."""
        return self.oidc_required_scopes.split()
