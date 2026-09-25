# API Reference

Source: `backend/server.py`. All routes are served by FastAPI; static files are mounted at `/` (`backend/static`).

**Auth:** if the `DEMO_PASSWORD` env var is set, every HTTP request and WebSocket handshake needs HTTP Basic auth with that password (any username); otherwise all routes are open. No per-user authorization exists.

## Index management (MOS-001)

### GET /api/indexes
List Moss indexes. 200: `[{ name, docCount, status, model, updatedAt }]`. 500 `{"detail":"Failed to list indexes"}`.

### GET /api/indexes/{name}/docs
List all documents of an index. 200: `[{ id, text, metadata }]`. 404 `Index '<name>' not found`. 500 `Failed to look up index` or `Failed to retrieve index documents`.

### POST /api/indexes/{name}/docs
Body: `{ id: string, text: string, metadata?: {string: string} }` (`id` and `text` non-empty). 200: `{ id }`. 422 on validation failure. 500 `Failed to add document`. Reloads the index if it is live-loaded (`protocol-index`, `live-data-index`, `deviation-index`); a reload failure is logged and not surfaced.

### PUT /api/indexes/{name}/docs/{doc_id}
Body: `{ text: string, metadata?: {string: string} }` (`text` non-empty). Upserts via `add_docs`. 200: `{ id }`. 422 on validation failure. 500 `Failed to update document`. Same reload behavior.

### DELETE /api/indexes/{name}/docs/{doc_id}
204 no body. 500 `Failed to delete document`. Same reload behavior.

## Deviations (MOS-002)

### POST /api/deviations/judge
Judges a dispatcher reply against a protocol chunk with one LLM call.

Request body:
| Field | Type | Rules |
|---|---|---|
| `dispatcherText` | string | required, non-blank, max 2000 |
| `reason` | string or null | optional, max 500 |
| `protocolChunkId` | string | required, non-blank, max 200 |
| `protocolChunkText` | string | required, non-blank, max 4000 |
| `callerTranscript` | string | required, non-blank, max 10000 |
| `callerSummary` | object or null | optional; `whatHappened?: string`, other keys allowed |

Responses:
- 200 `{ "verdict": "followed" }`: nothing stored.
- 200 `{ "verdict": "deviated", "deviationSummary": string, "id": "dev-<32 hex>", "retrievable": boolean }`: document saved to `deviation-index`; `retrievable` is false if the reload after saving failed.
- 422: validation failure.
- 502 `{"detail":"Could not judge response"}`: LLM call raised or returned malformed output; nothing written.
- 503 `{"detail":"LLM not configured"}`: no DeepSeek API key; nothing written.
- 500 `{"detail":"Failed to save deviation"}`: Moss write failed.

Stored document: `id`, `text` = `"<caller situation>\n<deviationSummary>"`, metadata (all strings): `type` = `"deviation"`, `callerTranscript`, `callerSummary` (JSON string), `protocolChunkId`, `protocolChunkText`, `dispatcherTranscript`, `deviationSummary`, `reason` (empty string if none), `timestamp` (UTC, `YYYY-MM-DDTHH:MM:SSZ`), `seed` = `"false"` (seeded records use `"true"`).

### GET /api/deviations
200: array sorted by `timestamp` descending of
`{ id, timestamp, callerTranscript, callerSummary (object; {} if missing or malformed), protocolChunkId, protocolChunkText, dispatcherTranscript, deviationSummary, reason, seed (boolean, true only for metadata "true") }`.
Returns `[]` if the index does not exist (index lookup raises `RuntimeError`) or is empty. 500 `{"detail":"Failed to retrieve deviations"}` on other lookup or fetch failures.

## Static pages
`/` (live dispatcher UI, `index.html`), `/manage.html`, `/deviations.html`.

## WebSocket /ws

One session per connection. On connect the server sends `unit_status` and then one every ~3 s.

### Client -> server (JSON text frames)
| type | Fields | Effect |
|---|---|---|
| `set_caller` | `address` (a seeded demo address) | Replies `dev_log` (incident-lookup), `dev_log` (facility-lookup), then `caller_context` |
| `transcript` | `text` | Sets the latest transcript for the worker (latest-wins) |
| `dispatch` | `action?` | Claims an available unit of the matching type; replies `unit_status` with `assignedUnit` (id or null) |
| `voice_start` | `channel?`: `"caller"` (default) or `"dispatcher"` | Opens a Deepgram stream for that channel; replies `voice_status` |
| `voice_stop` | `channel?` (same) | Closes that channel's stream; replies `voice_status` `stopped` |

Binary frames are PCM audio: sent to the dispatcher stream if open, otherwise the caller stream.

### Server -> client
- `unit_status`: `{ units: [{ id, type, status, eta }], assignedUnit? }`
- `caller_context`: `{ address, county, incidents: [{ date, incidentType, outcome, hazardFlag }], nearestFacilities: [{ name, address, city, distanceLabel, occupancyPct }] }`
- `protocol_update`: `{ transcript, latencyMs, matchId, matchText, priority, suggestedAction }`
- `deviation_update` (new): `{ deviations: [{ id, summary, dispatcherTranscript, reason, timestamp, score, protocolChunkText }] }`. Sent after each `protocol_update`; 0 to 2 items with `score >= 0.3`; empty if the deviation query failed or nothing matched.
- `extraction_update`: `{ fields }` (rule fields merged with LLM fields)
- `dev_log`: `{ service, callType, latencyMs|null, summary }`. New call type: `moss` / `deviation-query`.
- `voice_transcript` (caller): `{ text }`
- `dispatcher_voice_transcript` (new): `{ text, isFinal }`
- `voice_status`: `{ state: "listening" | "stopped" | "unavailable" | "error", reason?, channel? }`. `channel: "dispatcher"` is present only for the dispatcher channel. Unknown channel gives `state: "error"`, `reason: "unknown voice channel"`.
