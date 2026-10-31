"""Response shaping: list envelopes, concise projections, and the byte cap.

Why this exists: Pexip returns every field of every record (a VMR has ~60), and
an agent reading a 20-row list pays for all of them on every turn. Anthropic's
tool-design guidance is to return high-signal fields by default, offer a
detailed mode, paginate with an explicit "more" signal, and, when truncating,
tell the agent how to narrow. This module is the one place that implements
those rules so every list tool behaves the same way.

Two layers:

1. `finalize_result` runs on EVERY tool result (wired in mcp_app.PexipMCP). It
   leaves non-list results alone. For a Pexip list envelope ({objects, meta}) it
   adds `meta.has_more` / `meta.next_offset`, folds a top-level `truncated` flag
   from paginate_all into `meta`, and enforces PEXIP_MAX_RESPONSE_BYTES by
   dropping trailing objects and setting `meta.truncated` plus a `meta.hint`
   that says how to ask for less.

2. `shape_list` is called explicitly by the high-traffic list tools that take
   `response_format` / `fields`. It projects each object to the resource's
   CONCISE_FIELDS (or the caller's `fields`) before the generic finalizer runs.

The envelope keeps Pexip's own `objects` / `meta` keys rather than inventing a
new one: the model and the existing eval cases already know that shape, and the
additions are purely additive.
"""

from __future__ import annotations

import json
import os
from typing import Any, Literal, TypedDict

ResponseFormat = Literal["concise", "detailed"]

# Upper bound on a serialized tool result. Claude Code caps tool results at
# ~25k tokens; 100 KB of JSON is comfortably under that for ASCII-heavy data.
DEFAULT_MAX_RESPONSE_BYTES = 100_000


def max_response_bytes() -> int:
    raw = os.environ.get("PEXIP_MAX_RESPONSE_BYTES", "")
    try:
        value = int(raw) if raw else DEFAULT_MAX_RESPONSE_BYTES
    except ValueError:
        value = DEFAULT_MAX_RESPONSE_BYTES
    return max(value, 1_000)


class ListMeta(TypedDict, total=False):
    """Every key a list envelope's `meta` may carry.

    Declared exhaustively on purpose: FastMCP validates structured output
    against this schema and DROPS keys it does not know, so a new meta field
    must be added here or it vanishes from the wire.
    """

    total_count: int | None
    limit: int | None
    offset: int | None
    next: str | None
    previous: str | None
    fetched: int | None
    has_more: bool
    next_offset: int | None
    truncated: bool
    hint: str | None
    response_format: str | None
    fields: list[str] | None


class ListResult(TypedDict):
    """A page (or paginate_all walk) of Pexip records plus pagination metadata."""

    objects: list[dict[str, Any]]
    meta: ListMeta


# Fields returned in `concise` mode, by Pexip resource. Identity fields come
# first so the model can always refer back to a record. Anything not listed is
# available with response_format="detailed" or an explicit `fields` list.
# `id` and `resource_uri` are always included when present.
CONCISE_FIELDS: dict[str, tuple[str, ...]] = {
    # configuration
    "conference": (
        "name",
        "service_type",
        "description",
        "tag",
        "aliases",
        "allow_guests",
        "guest_pin",
        "pin",
        "host_view",
        "guest_view",
        "ivr_theme",
        "primary_owner_email_address",
    ),
    "conference_alias": ("alias", "conference", "description"),
    "automatic_participant": (
        "alias",
        "conference",
        "protocol",
        "role",
        "call_type",
        "streaming",
        "keep_conference_alive",
        "remote_display_name",
        "description",
    ),
    "end_user": (
        "primary_email_address",
        "display_name",
        "first_name",
        "last_name",
        "department",
        "title",
        "telephone_number",
        "mobile_number",
        "sync_tag",
    ),
    "device": (
        "alias",
        "description",
        "username",
        "primary_owner_email_address",
        "enable_sip",
        "enable_h323",
        "enable_infinity_connect_non_sso",
        "enable_infinity_connect_sso",
        "tag",
    ),
    "gateway_routing_rule": (
        "name",
        "priority",
        "enable",
        "match_string",
        "replace_string",
        "called_device_type",
        "outgoing_protocol",
        "outgoing_location",
        "call_type",
        "description",
    ),
    "ldap_sync_source": ("name", "ldap_server", "ldap_base_dn", "description"),
    "system_location": ("name", "description", "mtu", "media_qos", "signalling_qos"),
    "worker_vm": (
        "name",
        "hostname",
        "address",
        "node_type",
        "system_location",
        "maintenance_mode",
        "transcoding",
        "description",
    ),
    "ivr_theme": ("name", "uuid", "last_updated"),
    # status
    "status/conference": (
        "name",
        "service_type",
        "tag",
        "start_time",
        "is_locked",
        "guests_muted",
        "is_started",
        "participant_count",
    ),
    "status/participant": (
        "display_name",
        "conference",
        "role",
        "protocol",
        "call_direction",
        "is_muted",
        "is_presenting",
        "connect_time",
        "remote_address",
        "call_quality",
        "system_location",
        "vendor",
    ),
    "status/worker_vm": (
        "name",
        "node_type",
        "system_location",
        "media_load",
        "max_media_load",
        "signaling_count",
        "media_count",
        "sync_status",
        "upgrade_status",
        "version",
        "boot_time",
    ),
    "status/alarm": ("name", "level", "node", "details", "time_raised", "instance"),
    "status/registration_alias": ("alias", "protocol", "remote_address", "node", "start_time"),
    "status/system_location": (
        "name",
        "media_load",
        "max_media_load",
        "signaling_count",
        "media_count",
    ),
    # history
    "history/conference": (
        "name",
        "service_type",
        "tag",
        "start_time",
        "end_time",
        "duration",
        "participant_count",
    ),
    "history/participant": (
        "display_name",
        "conference_name",
        "role",
        "protocol",
        "call_direction",
        "start_time",
        "end_time",
        "duration",
        "call_quality",
        "disconnect_reason",
        "remote_address",
        "system_location",
        "vendor",
    ),
}

_ALWAYS = ("id", "resource_uri", "uuid")

NARROW_HINT = (
    "Result was cut to fit the response limit. Narrow it: add a filter (name_contains, "
    "a start_time/end_time window, conference_name, location), lower `limit`, request "
    'response_format="concise" or a `fields` list, or use pexip_summarize_calls for totals.'
)


def project(obj: Any, fields: tuple[str, ...] | list[str] | None) -> Any:
    """Keep only `fields` (plus id-like keys) of a record. Non-dicts pass through."""
    if not fields or not isinstance(obj, dict):
        return obj
    keep = set(fields) | set(_ALWAYS)
    return {k: v for k, v in obj.items() if k in keep}


def _byte_size(value: Any) -> int:
    return len(json.dumps(value, separators=(",", ":"), default=str).encode())


def finalize_result(result: Any, *, max_bytes: int | None = None) -> Any:
    """Normalize a list envelope and enforce the byte cap. Non-envelopes pass through.

    Idempotent, cheap for small results (one serialization only when the
    object count makes a cap plausible), and additive: nothing a tool already
    put in `meta` is removed.
    """
    if not isinstance(result, dict) or not isinstance(result.get("objects"), list):
        return result
    meta = result.get("meta")
    if not isinstance(meta, dict):
        meta = {}
        result["meta"] = meta

    # paginate_all puts `truncated` at the top level; the envelope keeps it in meta.
    if "truncated" in result:
        meta["truncated"] = bool(result.pop("truncated")) or bool(meta.get("truncated"))

    objects = result["objects"]
    total = meta.get("total_count")
    offset = meta.get("offset") or 0
    if "has_more" not in meta:
        if meta.get("next"):
            meta["has_more"] = True
        elif isinstance(total, int):
            meta["has_more"] = offset + len(objects) < total
        else:
            meta["has_more"] = False
    if meta.get("has_more") and "next_offset" not in meta:
        meta["next_offset"] = offset + len(objects)

    cap = max_bytes or max_response_bytes()
    if objects and _byte_size(result) > cap:
        # Drop from the tail until it fits; keep at least one record.
        lo, hi = 1, len(objects)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            trial = {**result, "objects": objects[:mid]}
            if _byte_size(trial) <= cap:
                lo = mid
            else:
                hi = mid - 1
        kept = objects[:lo]
        result["objects"] = kept
        meta["truncated"] = True
        meta["has_more"] = True
        meta["next_offset"] = offset + len(kept)
        meta["hint"] = NARROW_HINT
    return result


def shape_list(
    result: dict[str, Any],
    *,
    resource: str,
    response_format: ResponseFormat = "concise",
    fields: list[str] | None = None,
) -> ListResult:
    """Project a list envelope's objects for one resource and record the choice in meta.

    `fields` wins over `response_format`; "detailed" returns full records.
    Unknown resources have no concise set and fall back to detailed.
    """
    objects = result.get("objects", [])
    meta: dict[str, Any] = dict(result.get("meta") or {})
    if fields:
        projected = [project(o, fields) for o in objects]
        meta["fields"] = list(fields)
        meta["response_format"] = "fields"
    elif response_format == "detailed" or resource not in CONCISE_FIELDS:
        projected = objects
        meta["response_format"] = "detailed"
    else:
        projected = [project(o, CONCISE_FIELDS[resource]) for o in objects]
        meta["response_format"] = "concise"
    shaped: dict[str, Any] = {**result, "objects": projected, "meta": meta}
    return finalize_result(shaped)  # type: ignore[return-value]
