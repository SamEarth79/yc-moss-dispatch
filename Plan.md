# Dispatch Copilot — Architecture Plan

**Hackathon:** YC Fall 2026 x Moss — The Zero Latency Builder Sprint
**Core idea doc:** [dispatch-copilot-idea.md](dispatch-copilot-idea.md)

## One-line pitch

A live side panel for 911/emergency dispatch operators that continuously surfaces relevant protocol instructions, triage priority, past-incident context, and nearest-facility routing *as the caller is still speaking* — powered by Moss's sub-10ms local semantic search, never interrupting the call.

---

## 1. Panel features (what the dispatcher sees)

| # | Feature | Uses Moss? | Notes |
|---|---|---|---|
| 1+6+8 | **Live protocol panel** — matched guidance shown as an actionable step-by-step instruction (with a priority/triage badge) | ✅ Yes | One Moss query per partial transcript tick against the **protocol index**. Priority badge and instruction formatting are both read off the same match's metadata — not a second call. |
| 2 | Next-task / one-click actions (dispatch PD, FD, etc.) | ❌ No | Button just fires an action/webhook. Which action to *suggest* is read from a `suggestedAction` metadata tag baked into the protocol index at build time (see §3). |
| 3 | Past incidents | ✅ Yes | Query against the **live data index**, filtered to `type: incident`. Static/seeded for the demo — see §5 open decisions. |
| 4 | Caller/location context (address, jurisdiction) | ❌ No | Geocoding API (address → lat/lon) + jurisdiction lookup. Feeds #10. |
| 5 | Structured field extraction from transcript (what/where/injuries) | ❌ No | LLM call parsing the partial transcript into fields. Upstream of Moss — its output becomes the query text fired at the protocol index. |
| 9 | Unit/resource status + ETA (live PD/FD status) | ❌ No | Live/mocked state feed. Ranking among available units by real ETA uses the traffic-aware rerank described below, same pattern as #10. |
| 10 | Nearest facility routing | ✅ Yes (+ rerank) | Moss does candidate generation: `$near` (lat/lon) + metadata filter (trauma level) against the **live data index** (`type: facility`) returns a small candidate set fast. A traffic/routing API (Google Maps/Mapbox Directions) then **reranks** that candidate set by real ETA instead of straight-line distance — see §8. Fires once location resolves, not on every transcript tick. |

**Net: 2 Moss indexes** power the demo — a **static protocol index** and a **dynamic live data index** (facilities + past incidents). Everything else (2, 4, 5, 9) is supporting plumbing around them.

---

## 2. System architecture

```
Caller audio (mic / recorded call)
        │
        ▼
Streaming ASR (Deepgram / AssemblyAI / Whisper streaming)
        │  emits partial transcripts every ~100-300ms
        ▼
┌───────────────────────────────────────────────┐
│ Runtime (in-process, no network hop per query) │
│                                                 │
│  Partial transcript ──► Moss: protocol index   │──► Live instruction panel (1+6+8)
│                          (embed + ANN + filter) │──► Priority badge (from match metadata)
│                                                 │──► Suggested action (from match metadata) → feeds #2
│                                                 │
│  Structured fields (LLM, non-Moss) ──► Moss:    │
│                    live data index (type=incident)│──► Past incidents panel (#3)
│                                                 │
│  Geocoded lat/lon (non-Moss, #4) ──► Moss:      │
│                    live data index (type=facility)│──► candidate set (fast)
│                          ($near + trauma filter)│         │
└───────────────────────────────────────────────┘         ▼
                                            Traffic/routing API (non-Moss)
                                            reranks candidates by real ETA
                                                            │
                                                            ▼
                                            Nearest facility card (#10)
        │
        ▼
Human dispatcher (never interrupted, always in control)
```

Two Moss index artifacts are pulled once over HTTPS at app startup and held in memory; every query after that is local, in-process, no network round trip.

- **Protocol index** — static. Sourced from `data/docs/`. Any update requires SME (subject-matter expert / medical director) review and approval before a new index is published — infrequent, manual, versioned releases.
- **Live data index** — dynamic. Combines facility records and past-incident notes, distinguished at query time by a `type` metadata filter (`facility` vs `incident`). Updated on a much faster, automated cadence (facility status changes, new incidents logged) via a separate pipeline with no SME gate — see §7.

---

## 3. One-time index build (push work here, not into the runtime hot loop)

Since the only network call is the one-time HTTPS pull of the index artifact, as much logic as possible should be precomputed at **build time**, so the runtime query is just "embed + look up + render metadata":

| Precomputed at index build | Purpose |
|---|---|
| Chunking + embeddings of all `data/docs/` sources | Base requirement for any Moss index |
| `priority` tag per protocol chunk (e.g. `P1-critical`) | Powers #6 badge for free off the same query |
| `suggestedAction` tag per chunk/incident type | Powers #2's button without extra runtime logic |
| Escalation ordering + next-chunk-ID links within a protocol | Optional: lets the UI jump to the next step directly, even faster than re-querying |
| Age/context variants split into separate tagged chunks (adult vs. infant, conscious vs. unconscious) | Avoids runtime branching logic to pick the right variant |
| Facility metadata: `type: facility`, trauma level, ER capabilities, lat/lon | Powers #10's `$near` + filter query directly, no join needed |
| Past-incident note embeddings, tagged `type: incident` | Powers #3 |

Runtime stays minimal: embed the live query text locally, run the ANN/filter lookup, render whatever metadata comes back. No extra API calls, no extra classifiers, no joins.

---

## 4. Data sources

Collected corpus at [data/docs/](data/docs/) ([manifest](data/docs/manifest.md)) — 41 real documents, ~30MB:

- `medical/` (20) — CPR, choking, stroke, bleeding, seizures, anaphylaxis, childbirth, drowning, shock, heart attack, hypothermia, poisoning
- `hazmat/` (8) — DOT Emergency Response Guidebook, OSHA HAZWOPER, gas leak/pipeline response, CO poisoning, chemical burns
- `dispatch-protocols/` (6) — NASEMSO national EMS clinical guidelines, Denver Health field protocols, EMD program standards, pre-arrival instructions, naloxone protocol
- `facilities/` (7) — NY hospital directory (CSV, 220 hospitals w/ lat/lon), TX/AR trauma center lists, CDC field-triage guidelines, poison control references

Past-incidents corpus: not yet collected — needs a synthetic/seeded dataset (no real incident data available), see §5.

---

## 5. Demo scope discipline

Per the original idea doc's scope guidance: pick 1-2 demo-able scenarios rather than broad coverage. Recommended: **choking** and **cardiac arrest** — both fully covered in the existing corpus, both have a clear escalation arc (conscious → unconscious) that shows the live-updating panel well.

**Open decisions to make before building:**
1. **Past-incidents data** — no real data available; decide whether to hand-write a small synthetic seed set (5-10 fake past calls) for the demo, or drop #3 from the MVP and treat it as stretch.
2. **Live PD/FD status (#9)** — will need to be mocked (static or randomized status feed) since there's no real CAD integration. Confirm this is acceptable for the demo narrative.
3. **Index resync strategy** — out of scope for the hackathon, but worth a one-line mention in the pitch: a real deployment would periodically re-pull an updated index artifact (protocols/facilities rarely change; incidents would need more frequent resync).
4. **Slow-backend comparison** — the idea doc's optional demo enhancement (naive vector DB side-by-side vs. Moss) — decide whether to build this or just show the on-screen latency counter alone.

---

## 6. Build order (proposed)

1. Build the **protocol index** in Moss from `data/docs/medical/` + `data/docs/dispatch-protocols/` (choking + cardiac arrest chunks only, tagged with priority/action metadata).
2. Wire streaming ASR → partial transcript → Moss query → live instruction panel (#1+6+8). This is the core "prove Moss is load-bearing" loop — get this working and visibly live-updating first.
3. Add the on-screen latency/update-rate counter (this is what makes the Speed/Latency judging score legible).
4. Build the **live data index** starting with `type: facility` records from `data/docs/facilities/`, wire geocoding (#4) → `$near` query → nearest-facility card (#10).
5. Add structured field extraction (#5) and mocked unit status + action buttons (#2, #9).
6. Add traffic-aware reranking (§8) on top of #10's candidate set — call a routing API for real ETA and reorder the Moss results before rendering.
7. If time remains: add `type: incident` records to the live data index with seeded synthetic past-incident data (#3), and the slow-vs-fast side-by-side comparison.

---

## 7. Index update pipelines

Two indexes, two very different release processes:

| | Protocol index (static) | Live data index (dynamic) |
|---|---|---|
| Content | Medical/hazmat/dispatch protocol docs | Facility records + past-incident notes |
| Change frequency | Rare (protocols change occasionally, e.g. new AHA guideline cycle) | Frequent (facility status changes, new incidents logged continuously) |
| Approval gate | **Requires SME sign-off** (medical director / protocol committee) before a new index build is published — correctness here is safety-critical | No SME gate — automated ingestion, validated for format/schema only |
| Update mechanism | Manual/versioned rebuild + review + publish to Moss Cloud | Automated pipeline re-embeds/re-publishes on a schedule or on write (e.g. new incident logged → append to source → rebuild) |
| Demo implication | Build once for choking + cardiac arrest, treat as fixed for the hackathon | Facility data can be static for the demo; incident data is where a "live update" demo moment could be shown if time allows (e.g. log an incident mid-demo, show it become searchable) |

For the hackathon, both indexes will likely be rebuilt manually via the same script/process — the distinction above is the target production design, not necessarily built out during the sprint. Worth deciding whether to actually demonstrate the live-update path (re-publish the live data index mid-demo) as a stretch goal, since it would visually reinforce the "dynamic vs. static" story.

---

## 8. Traffic-aware routing (retrieve-then-rerank)

Inspired by real AI-dispatch systems: two ideas evaluated, one adopted.

**Adopted — real-time traffic reranking (#9, #10).** Moss's speed is used to *afford* a rerank step, not replace it:
1. Moss generates a small **candidate set** fast — `$near` + metadata filter against the live data index (e.g. "all Level-II+ trauma hospitals within 10mi," or "all available units within 5mi").
2. A traffic/routing API (Google Maps / Mapbox Directions) **reranks** that candidate set by real ETA instead of straight-line distance.

This is a genuine strengthening of the Moss pitch, not a dilution of it: because candidate generation is sub-10ms, the system can afford to pull a *larger* candidate set to rerank than a slower backend could, while still returning a result fast overall. Applies to both nearest-facility routing (#10) and choosing which PD/FD unit to dispatch (#9).

**Not adopted — ML-predicted call hotspots (pre-positioning helpers before a call comes in).** This is a time-series/geospatial forecasting problem, not a retrieval problem — it doesn't touch Moss, needs real historical call-volume data (we only have synthetic incidents), and would dilute the "Moss is load-bearing" story the judging rubric scores on (Speed & Latency, 20%). Left out of the build; worth a single "future vision" bullet in the pitch deck at most.
