"""Helpers and annotation presets shared by every tool module.

If you're new to this codebase, read this file second (after `client.py`) — it's
the glue between the raw HTTP client and the per-resource tool modules.

Two groups of utilities live here:

1. Plumbing for talking to Pexip
   ---------------------------------
   - `get_client(ctx)`      — pulls the shared PexipClient off the MCP request context.
   - `resolve_id_by_field`  — lets a tool accept "42" or "staff-room" and figure out
                              the integer id on its own (LLM-friendly).
   - `fk_uri`               — builds the URI string Pexip wants when one resource
                              points at another (Pexip foreign keys are URIs, not ids).
   - `paginate_all`         — walks every page of a list endpoint and returns one
                              combined response.

2. MCP "annotation" presets
   ---------------------------------
   Every `@mcp.tool(...)` call can attach a `ToolAnnotations` object with four
   boolean hints — readOnlyHint, destructiveHint, idempotentHint, openWorldHint.
   The MCP client (Claude Desktop, etc.) reads those hints to decide things like
   "auto-approve this call?", "warn the user?", "safe to retry on network blip?".
   They are *hints*, not enforcement — Pexip won't refuse a delete because we
   forgot a flag. They're for the LLM client to be a good citizen.

   Every tool in this project falls into one of five buckets that have the same
   hint combination. The presets (`read`, `create`, `update`, `delete`, `control`)
   are just named shortcuts for those buckets so tool modules can write
   `annotations=read("List VMRs")` instead of constructing the full object.
"""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from pexip_mcp.client import PexipClient, PexipError, extract_id_from_uri


# Use get_client to pull the shared PexipClient out of the MCP request context.
def get_client(ctx: Context) -> PexipClient:
    """Return the shared PexipClient for this request.

    Where it came from: `lifespan()` in `mcp_app.py` builds one PexipClient at
    server startup and yields an `AppContext(pexip=client)`. FastMCP exposes
    that AppContext on every tool call as
    `ctx.request_context.lifespan_context`. So this one-liner just hops through
    that chain to get our HTTP client back. Use this at the top of every tool.
    """
    return ctx.request_context.lifespan_context.pexip


# Use security_resources_allowed to check whether generic CRUD may mutate
# security-critical resources (SSH keys, roles, auth, certs) for this server.
def security_resources_allowed(ctx: Context) -> bool:
    """True only when PEXIP_ALLOW_SECURITY_RESOURCES was set at startup.

    Defaults to False when the flag is absent from the lifespan context (e.g.
    older test harnesses), so security-critical resources fail closed.
    """
    lifespan = ctx.request_context.lifespan_context
    return bool(getattr(lifespan, "allow_security_resources", False))


# Keys whose values are secrets and must never be echoed back into the LLM
# context on read paths. Matched case-insensitively as whole-word suffixes.
_SECRET_KEY_SUFFIXES = (
    "password",
    "secret",
    "private_key",
    "passphrase",
    "client_secret",
)
_SECRET_KEY_EXACT = frozenset(
    {"token", "access_token", "gateway_token", "key_data", "pin", "guest_pin"}
)
_REDACTED = "***REDACTED***"


# Use redact_secrets to mask secret-bearing fields before returning a record to the LLM.
def redact_secrets(data: Any) -> Any:
    """Recursively replace secret-valued fields with a redaction marker.

    Defense-in-depth for read tools: Pexip usually treats credential fields as
    write-only (returning null/masked), but we never rely on that — any non-empty
    string under a secret-looking key is masked before it reaches the MCP client
    (and thus the model context / provider logs). Non-secret data passes through
    unchanged, as do null/empty values (so "field is unset" stays visible).
    """
    if isinstance(data, dict):
        out: dict[str, Any] = {}
        for key, value in data.items():
            lowered = key.lower()
            is_secret = lowered in _SECRET_KEY_EXACT or lowered.endswith(_SECRET_KEY_SUFFIXES)
            if is_secret and isinstance(value, str) and value:
                out[key] = _REDACTED
            else:
                out[key] = redact_secrets(value)
        return out
    if isinstance(data, list):
        return [redact_secrets(item) for item in data]
    return data


# Use resolve_id_by_field so LLMs (and humans) can pass a friendly name and we
# do the integer-id lookup ourselves.
async def resolve_id_by_field(
    client: PexipClient,
    resource: str,
    value: int | str,
    field: str = "name",
    **extra_filters: Any,
) -> int:
    """Accept an int id, a numeric string id, or a field-value lookup; return the int id.

    Why this exists: Pexip's API addresses every object by an opaque integer id
    (e.g. /configuration/v1/conference/42/), but LLMs naturally pass names
    ("staff-room"). This helper bridges the two — tools take `int | str`, we
    figure out the id.

    The `**extra_filters` kwargs are forwarded as additional query-string filters
    to narrow the lookup. The canonical use case: the `conference` table in
    Pexip holds VMRs, gateway calls, AND lectures, all distinguished by a
    `service_type` field. So when looking up a VMR by name, callers pass
    `service_type="conference"` to make sure we don't accidentally match a
    gateway call that happens to share the name.

    Raises PexipError(404) on no match, PexipError(409) on multiple matches.
    """
    if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
        return int(value)
    # limit=2 is enough to detect ambiguity without paying to fetch more.
    filters: dict[str, Any] = {field: value, "limit": 2, **extra_filters}
    result = await client.list(resource, **filters)
    objects = result.get("objects", [])
    if not objects:
        raise PexipError(404, {field: [f"No {resource} with {field}={value!r}"]})
    if len(objects) > 1:
        raise PexipError(409, {field: [f"Multiple {resource} matches for {field}={value!r}"]})
    return extract_id_from_uri(objects[0]["resource_uri"])


# Use fk_uri to build the URI string Pexip wants whenever one resource references another.
def fk_uri(resource: str, obj_id: int, api: str = "configuration") -> str:
    """Format the URI string Pexip uses for cross-resource references.

    Pexip's API is HATEOAS-ish: foreign keys are full API paths, not bare ids.
    For example, to set the `theme` field on a VMR, you POST the string
    `"/api/admin/configuration/v1/ivr_theme/3/"`, NOT the integer 3. Same for
    `system_location`, `conference`, etc. This helper builds that path so we
    don't have to hand-format it in every tool.
    """
    return f"/api/admin/{api}/v1/{resource}/{obj_id}/"


# Use paginate_all to walk every page of a list endpoint and return one combined response.
async def paginate_all(
    client: PexipClient,
    resource: str,
    *,
    api: str = "configuration",
    max_records: int = 5000,
    page_size: int = 1000,
    **params: Any,
) -> dict[str, Any]:
    """Walk paginated results until exhausted or max_records hit.

    Pexip list responses are shaped like:
        {
          "objects": [ ... ],
          "meta": {
            "total_count": 12345,    # total available
            "limit": 1000,           # page size
            "offset": 0,
            "next":     "/api/.../?limit=1000&offset=1000",   # null on last page
            "previous": null,
          }
        }
    This helper repeatedly bumps `offset` by `page_size` until `meta.next` is
    null (or we hit `max_records`), then returns a single dict shaped the same
    way the per-page response is shaped, plus a `truncated` boolean. The
    `meta.total_count` we return is what Pexip reported for the whole result
    set; `meta.fetched` is the count we actually returned.

    Stops on: max_records reached, server-reported `meta.next` is null, or
    a page returns zero objects.
    """
    # paginate_all owns limit/offset; drop any caller-provided values to avoid collision.
    params = {k: v for k, v in params.items() if k not in ("limit", "offset")}
    objects: list[Any] = []
    offset = 0
    server_total: int | None = None
    while True:
        page = await client.list(
            resource, api=api, limit=page_size, offset=offset, **params
        )
        page_objs = page.get("objects", [])
        page_meta = page.get("meta", {})
        if server_total is None:
            server_total = page_meta.get("total_count")
        objects.extend(page_objs)

        if len(objects) >= max_records:
            return {
                "objects": objects[:max_records],
                "meta": {
                    "total_count": server_total,
                    "fetched": max_records,
                    "limit": max_records,
                },
                "truncated": True,
            }
        if not page_objs or not page_meta.get("next"):
            return {
                "objects": objects,
                "meta": {"total_count": server_total, "fetched": len(objects)},
                "truncated": False,
            }
        offset += page_size


# ---------------------------------------------------------------------------
# MCP annotation presets
#
# Each preset returns a `ToolAnnotations` object describing one of the five
# behavior buckets every tool in this project fits into. See the module
# docstring for what the four hint fields mean and why these are presets.
#
# A quick reference of the combinations:
#
#                   readOnly  destructive  idempotent
#     read            ✅           ❌            ✅
#     create          ❌           ❌            ❌    (POSTing twice makes two)
#     update          ❌           ✅            ✅    (PATCH same body = same state)
#     delete          ❌           ✅            ✅    (deleting twice = same state)
#     control         ❌           ✅           configurable
#
# `openWorldHint=True` is set on every preset because every tool talks to the
# Pexip Management Node — an external system we don't fully control.
# ---------------------------------------------------------------------------


# Use read for tools that only fetch data — safe to auto-approve, safe to retry.
def read(title: str) -> ToolAnnotations:
    """Annotation preset for read-only tools (list / get / schema).

    Read-only and idempotent: clients can usually auto-approve these without
    bothering the user.
    """
    return ToolAnnotations(
        title=title,
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )


# Use create for tools that add a new resource. NOT idempotent.
def create(title: str) -> ToolAnnotations:
    """Annotation preset for tools that create new resources.

    Marked non-idempotent on purpose: POSTing the same payload twice produces
    two resources (or a 409 conflict). Marked non-destructive because nothing
    pre-existing is changed.
    """
    return ToolAnnotations(
        title=title,
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    )


# Use update for tools that mutate an existing resource. Destructive but idempotent.
def update(title: str) -> ToolAnnotations:
    """Annotation preset for tools that modify existing resources.

    "destructiveHint=True" here means "mutates server state", not "scary" —
    the client should give it more weight than a read. Idempotent because
    PATCHing the same body twice lands you in the same state.
    """
    return ToolAnnotations(
        title=title,
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=True,
        openWorldHint=True,
    )


# Use delete for tools that permanently remove a resource.
def delete(title: str) -> ToolAnnotations:
    """Annotation preset for tools that delete resources.

    Idempotent in the "same end state" sense: once gone, deleting again is a
    no-op (Pexip returns 404, which we may map to success in the tool).
    """
    return ToolAnnotations(
        title=title,
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=True,
        openWorldHint=True,
    )


# Use control for Command API tools that act on live calls (mute, lock, disconnect, ...).
def control(title: str, *, idempotent: bool = True) -> ToolAnnotations:
    """Annotation preset for Command API actions that change live call state.

    Defaults to idempotent — muting an already-muted participant is a no-op,
    locking a locked conference is a no-op. Pass `idempotent=False` for
    actions like `dial_participant` where each call places a new outbound
    leg (calling it twice dials twice).
    """
    return ToolAnnotations(
        title=title,
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=idempotent,
        openWorldHint=True,
    )
