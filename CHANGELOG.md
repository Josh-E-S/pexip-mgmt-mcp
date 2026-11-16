# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). Until 1.0, a minor
version may contain breaking changes; they are listed under "Changed".

## [Unreleased]

### Changed (breaking)

- Every tool name is prefixed `pexip_` (`list_vmrs` is now `pexip_list_vmrs`).
  Set `PEXIP_LEGACY_TOOL_NAMES=true` to also register the old names while
  migrating prompts and skills.
- The catalog went from 122 tools to 72. About 50 typed tools were folded into
  generic ones that take a `resource` name: `pexip_list_resources` /
  `pexip_get_resource` / `pexip_create_resource` / `pexip_update_resource` /
  `pexip_delete_resource` for configuration, `pexip_list_status` /
  `pexip_get_status`, and `pexip_list_history` / `pexip_get_history`.
  Platform lifecycle commands became `pexip_run_platform_command`, and the two
  provisioning-email tools became `pexip_send_provisioning_email`.
- Tools are grouped into toolsets. A default session exposes about 60 tools;
  `dialplan` and `platform` are opt-in through `PEXIP_TOOLSETS`.
- List tools return `{"objects": [...], "meta": {...}}` with concise fields by
  default (`response_format="detailed"` or `fields=[...]` for more) and a 50 KB
  response cap (`PEXIP_MAX_RESPONSE_BYTES`).
- `mcp` is pinned to `>=1.2.0,<2`; SDK 2.x removed the module this server imports.

### Added

- `pexip_describe_resources`, plus the `pexip://registry` and
  `pexip://schema/{resource}` MCP resources, for discovering resource names and
  their filters.
- `pexip_get_platform_health`, a single-call health summary.
- Live-control tools accept participant and conference names as well as UUIDs.
- Per-tool guidance (use when / do not use when / API reference) rendered into
  every description, enforced by catalog-quality tests.
- HTTP transport: `PEXIP_MCP_PUBLIC_URL`, `PEXIP_MCP_ALLOWED_HOSTS` and
  `PEXIP_MCP_ALLOWED_ORIGINS`; OIDC sessions are bound to the principal that
  opened them.
- OIDC discovery (RFC 9728): the `resource` is the MCP endpoint URL, the document
  is also served at the resource-suffixed path, scopes are qualified for
  Microsoft Entra issuers, and rejected tokens are explained in the server log.
- Static type checking (mypy), format checking, CodeQL and secret scanning in
  CI; pre-commit configuration; contributing guide and issue / PR templates.

### Fixed

- Import failure on Python 3.11 (`typing.TypedDict` in validated output).
- Tool descriptions differed by Python version because docstring indentation
  was kept before 3.13.
- The platform-tools gate compared unprefixed names and removed nothing.
- Unit tests no longer read a developer's local `.env`.

## [0.2.0]

- MCPB bundle for Claude Desktop, OAuth2 (JWT bearer) authentication to the
  Management Node, HTTP transport with static-token or OIDC client
  authentication, and the eval suite.

## [0.1.0]

- Initial release: MCP server for the Pexip Infinity Management API over stdio.
