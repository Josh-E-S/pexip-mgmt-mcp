"""Shared implementation of the generic list/get tools for the Status and History APIs.

status_generic.py and history_generic.py are thin wrappers that give each API its
own tool name, docstring and defaults; everything else lives here so a fix lands
in both. Behaviour is driven by the ResourceSpec in tools/_catalog.py:

  name_field   the field name_contains searches (None: the resource has no name,
               and name_contains is refused instead of silently ignored)
  time_field   the field start_time / end_time bound (None: no time window)
  "{id}" in the resource name marks a per-object sub-path (get-only)

Name resolution: resources rooted in worker_vm or system_location accept the
node's / location's configured name as the id, exactly as the typed tools did.
"""

from __future__ import annotations

from typing import Any

from pexip_mcp.client import PexipClient, PexipError
from pexip_mcp.tools._catalog import ResourceSpec
from pexip_mcp.tools._helpers import paginate_all, resolve_id_by_field
from pexip_mcp.tools._shaping import ListResult, ResponseFormat, shape_list
from pexip_mcp.tools.resource_crud import _validate_filters

# Status/history resources whose ids are configuration ids and may be given by name.
_NAME_RESOLVABLE = {"worker_vm", "system_location"}


class GenericApi:
    def __init__(self, api: str, registry: dict[str, ResourceSpec], *, max_records: int) -> None:
        self.api = api
        self.registry = registry
        self.max_records = max_records
        self.listable = {n: s for n, s in registry.items() if "{id}" not in n}
        self.subpath = {n: s for n, s in registry.items() if "{id}" in n}

    def spec(self, resource: str, *, listable: bool) -> ResourceSpec:
        table = self.listable if listable else self.registry
        spec = table.get(resource)
        if spec is None:
            valid = ", ".join(sorted(self.listable))
            if not listable:
                valid += ", " + ", ".join(sorted(self.subpath))
            raise PexipError(
                400,
                {
                    "resource": [
                        f"Unknown {self.api} resource {resource!r}. Valid: {valid}. Use "
                        f'pexip_describe_resources(api="{self.api}") to search.'
                    ]
                },
            )
        return spec

    async def list(
        self,
        client: PexipClient,
        resource: str,
        *,
        name_contains: str | None,
        start_time: str | None = None,
        end_time: str | None = None,
        filters: dict[str, Any] | None,
        limit: int,
        offset: int,
        fetch_all: bool,
        response_format: ResponseFormat,
        fields: list[str] | None,
    ) -> ListResult:
        spec = self.spec(resource, listable=True)
        params: dict[str, Any] = {}
        if name_contains:
            if not spec.name_field:
                raise PexipError(
                    400,
                    {
                        "name_contains": [
                            f"{resource!r} has no name field to search; use `filters` with one "
                            "of its own fields instead."
                        ]
                    },
                )
            params[f"{spec.name_field}__icontains"] = name_contains
        if start_time or end_time:
            if not spec.time_field:
                raise PexipError(
                    400,
                    {"start_time": [f"{resource!r} has no time field; omit start_time/end_time."]},
                )
            if start_time:
                params[f"{spec.time_field}__gte"] = start_time
            if end_time:
                params[f"{spec.time_field}__lt"] = end_time
        if filters:
            clean = _validate_filters(filters)
            clash = sorted(set(clean) & set(params))
            if clash:
                raise PexipError(
                    400,
                    {
                        "filters": [
                            f"Filter key(s) {clash} duplicate a parameter this tool already "
                            "sets (name_contains / start_time / end_time); drop one of them."
                        ]
                    },
                )
            params.update(clean)
        if fetch_all:
            result = await paginate_all(
                client, resource, api=self.api, max_records=self.max_records, **params
            )
        else:
            result = await client.list(resource, api=self.api, limit=limit, offset=offset, **params)
        return shape_list(
            result,
            resource=f"{self.api}/{resource}",
            response_format=response_format,
            fields=fields,
        )

    async def get(self, client: PexipClient, resource: str, obj_id: str | int) -> dict[str, Any]:
        self.spec(resource, listable=False)
        base = resource.split("/", 1)[0]
        if base in _NAME_RESOLVABLE:
            obj_id = await resolve_id_by_field(client, base, obj_id, field="name")
        if "{id}" in resource:
            return await client.list(resource.replace("{id}", str(obj_id)), api=self.api, limit=100)
        return await client.get(resource, obj_id, api=self.api)
