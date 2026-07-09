---
name: pexip-event-sinks
description: Use when planning or setting up Pexip Infinity event sinks — the webhook mechanism where Pexip POSTs conference / participant / call lifecycle events to an HTTP endpoint you run — or when building the receiver side of that contract, or deciding between push (event sinks) and polling the History API. Covers how to configure a sink in Pexip directly and how to build a secure receiver. Triggers on `event_sink`, `/api/admin/configuration/v1/event_sink/`, `webhook`, "Pexip events", "push events", "real-time CDR", "event collector". Do NOT use for one-off live state reads (use `pexip-status-api` / `pexip-operations`) or post-call CDR pulls (use `pexip-history-api`).
license: MIT
---

# Pexip event sinks — webhook push events

Pexip Infinity can **push** real-time events for conferences, participants, and call milestones to an HTTP endpoint you control. This is the **push-based alternative** to polling the History API — for high-volume platforms or anything approaching real-time, event sinks beat polling on latency, completeness (no 10,000-instance retention cap), and rate-limit headroom.

> **Why the MCP server does NOT manage event sinks.** Creating or editing an event sink means telling Pexip *"POST all conference and participant data to this URL."* Exposing that as an LLM-callable tool is a data-exfiltration risk: a prompt-injected or confused agent could be steered into registering an attacker-controlled URL and quietly stream live meeting metadata off-platform. There is no operational reason for an agent to manage sinks — they're set up once by a human — so the server intentionally ships **no** `*_event_sink` tools, and `event_sink` is **not** in the generic-CRUD registry either. Configure sinks yourself (below); use the agent only for the *reporting* it enables downstream.

## When to use this skill

- "Move from polling the History API to push events"
- "Set up a webhook so we get notified when calls start/end"
- "Build a CDR collector that survives the 10,000-instance retention limit"
- "Stream Pexip events into our data warehouse / SIEM / dashboard"

## When NOT to use

- One-shot reads of live state → `pexip-status-api` / `pexip-operations/live-meeting-ops.md`
- Historical CDR queries / reports → `pexip-history-api` / `pexip-operations/reporting.md`

## Configuring the sink (done by a human, in Pexip)

Event sinks are configured **outside the MCP server**, by an operator with admin access — deliberately, for the security reason above. Two supported paths:

1. **Admin UI:** Pexip Management Node → **Platform → Event Sinks → Add Event Sink**. Set the URL, protocol version (v2 is current), bulk support, TLS verification, and optional Basic-auth username/password.
2. **Configuration API directly** (curl / a provisioning script run by an admin, not the agent):
   ```
   POST https://<mgmt-node>/api/admin/configuration/v1/event_sink/
   { "name": "cdr-collector", "url": "https://collector.internal/pexip",
     "version": 2, "bulk_support": true, "verify_tls": true,
     "username": "pexip", "password": "<secret>" }
   ```

Guidance for whoever sets it up:
- **`version=2`** is the current event protocol version.
- **`bulk_support=true`** lets Pexip batch events into one POST body (recommended; your receiver must handle arrays).
- **Keep `verify_tls=true` in production.** Events carry participant identifiers and call metadata; a self-signed-only lab node is the only reason to relax it, and never in prod.
- **Prefer an internal / private URL.** The sink should point at a host reachable from the Conferencing Nodes' data-plane network but not the public internet.

## Event categories Pexip pushes

| Category | Examples |
|---|---|
| Conference lifecycle | `conference_started`, `conference_ended`, `conference_updated` |
| Participant lifecycle | `participant_connected`, `participant_disconnected`, `participant_updated` |
| Call lifecycle | `participant_call_quality_low`, `participant_call_disconnected` |
| Layout / role changes | `participant_role_changed`, `layout_changed` |

Exact payload shape: https://docs.pexip.com/admin/event_sink.htm — the authoritative reference for field names (they change between Pexip versions).

## Receiver side (the service you run)

A separate HTTP listener at the URL you registered. Minimum requirements:

1. **Accept POST** with `Content-Type: application/json`.
2. **Return 2xx quickly** (Pexip retries on non-2xx and on timeout). Don't do heavy work in the handler — queue + ack.
3. **Authenticate the caller.** Validate the Basic-auth credentials you set on the sink; reject anything else. Don't accept anonymous POSTs.
4. **Serve HTTPS with a valid cert.** The events are sensitive; don't terminate as plain HTTP on a routable interface.
5. **Tolerate batches.** With `bulk_support=true` the body is an array of events, not a single event.
6. **Idempotency.** Pexip retries — dedupe by event `id` / `call_id`.

The recipe `recipes/webhook-collector-bootstrap.md` walks through a minimal secure receiver, an idempotent queue write, and a reconciliation job that fills gaps from the History API.

## Security notes

- **Lock the receiver down.** Basic auth over HTTPS at minimum; ideally also IP-allowlist the Conferencing/Management nodes. The receiver ingests live meeting metadata — treat it as sensitive.
- **Don't put secrets in the sink URL** — it's stored/returned in plain text. Use Basic auth (credentials are write-only: returned as null on GET) or signed paths.
- **The MCP agent never sees event payloads** and can't reconfigure the sink — receiving and querying events is entirely your downstream system.
- **`url` must be reachable from every Conferencing Node**, not just the Management Node — plan the data-plane network accordingly.
- **Pexip's retry budget is finite.** Falling behind for hours can lose events; pair with a reconcile job that backfills from the History API.

## Reference source

- **Authoritative Pexip docs:**
  - Event sink overview: https://docs.pexip.com/admin/event_sink.htm
  - Configuration API (event_sink resource): https://docs.pexip.com/api_manage/api_configuration.htm
- **MCP server:** intentionally exposes no event-sink tools (see the rationale above). Reporting on the events you collect is done with `pexip-history-api` / `pexip-operations/reporting.md`.
- **Related recipe:** `recipes/webhook-collector-bootstrap.md` — the secure receiver skeleton.
