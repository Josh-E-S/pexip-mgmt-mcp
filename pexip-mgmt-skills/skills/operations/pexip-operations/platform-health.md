# Platform health

For "is the platform OK" / capacity / monitoring questions. Read-only — no destructive operations here.

## Three lenses

| Lens | Tool | When |
|---|---|---|
| **Active alarms** | `list_alarms` | "Anything broken right now?" |
| **Conferencing Node load** | `list_node_status`, `get_node_status` | Capacity, sync state, version drift, maintenance mode. |
| **Port usage vs entitlement** | `get_licensing_status` | "Are we about to run out of licenses?" |

## Recipe: triage the platform

```
list_alarms(level="error")            # most-severe first
list_alarms(level="warning")          # then warnings
get_licensing_status()                # any location near max?
list_node_status(fetch_all=False)     # any node OUT_OF_SYNC or in maintenance_mode?
```

Surface findings as a punch list — alarms by severity, then any nodes that aren't `SYNCED`, then any location whose `port_used` is close to `port_max`.

## Alarms

```
list_alarms(level="error" | "warning" | "info", node_name="<node>", fetch_all=True)
```

Fields per alarm:
- `name` (machine code, e.g. `LICENSE_EXPIRING`)
- `details` (human description)
- `level` (`error` / `warning` / `info`)
- `node` (FK to a Conferencing Node)
- `time_raised` (ISO timestamp)
- `instance` (subsystem the alarm belongs to)

Alarms self-clear when the underlying condition resolves — there is no "ack" or "delete alarm" tool, by design.

## Conferencing Node status

```
list_node_status(location="eu-west", name_contains="proxy", fetch_all=False)
get_node_status(node="cnf-eu-west-1")
```

Useful fields:
- `node_type` — `CONFERENCING` (mixes media) or `PROXYING` (signaling/edge proxy only).
- `system_location` — the location name.
- `version` — Pexip software version on that node. Mixed versions across a platform is a yellow flag.
- `sync_status` — `SYNCED` / `SYNCING` / `OUT_OF_SYNC`. Anything other than `SYNCED` for more than ~5 minutes is worth flagging.
- `maintenance_mode` — boolean. Nodes in maintenance don't take new calls.
- `media_load` — current load as a percentage / count.
- `signaling_count` — concurrent signalling connections.
- `max_audio_calls`, `max_full_hd_calls`, `max_hd_calls`, `max_sd_calls` — capacity ceiling.
- `cpu_count`, `total_ram` — hardware spec.
- `boot_time`, `last_reported` — uptime / staleness check.
- `cloud_bursting` — true if this is an overflow node spun up by cloud bursting.
- `upgrade_status` — non-null during an in-progress upgrade.

## Licensing

```
get_licensing_status()
```

Returns one record per `system_location` with concurrent-port counts:
- `audio_ports_used` / `audio_ports_max`
- `port_used` / `port_max` (video)
- `system_location` (FK to the location)

Rule of thumb for capacity alerts: warn at 75% of max, alert at 90%.

## Backplane (cross-node media stats)

Not currently exposed as an MCP tool — `pexip-mgmt-mcp` intentionally omits `/backplane/`. For backplane stats, hit the Status API directly or extend the server. See `pexip-status-api` skill for the underlying resource.

## Authoritative docs

- Status API: https://docs.pexip.com/api_manage/api_status.htm
- Alarm meanings: https://docs.pexip.com/admin/alarms.htm
- Cloud bursting: https://docs.pexip.com/admin/cloud_bursting.htm
