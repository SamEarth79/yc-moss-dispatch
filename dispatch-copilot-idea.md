# Dispatch Copilot — Real-Time Retrieval Assistant for Emergency Dispatchers

**Hackathon:** YC Fall 2026 x Moss — The Zero Latency Builder Sprint
**Track:** Real Time Voice and Conversational AI
**Team size:** Individual or pair

---

## One-line pitch

A live side panel for 911/emergency dispatch operators that continuously surfaces relevant protocol snippets, past-incident context, and resources (nearest hospital, hazmat procedure, etc.) *as the caller is still speaking* — so the human dispatcher never has to pause the conversation to search manually.

## The problem

Emergency dispatchers have to listen to a caller in crisis, extract what's happening, and simultaneously recall or look up the correct protocol (CPR steps, choking response, hazmat handling, nearest hospital routing) — all in real time, under stress, without ever putting the caller on hold. Today that lookup is manual (memory, binders, slow internal search tools) and it happens *after* the dispatcher has already processed what was said, not while it's still unfolding.

## The idea

As the caller talks, a streaming speech-to-text engine emits **partial transcripts** continuously (every ~100–300ms), well before the caller finishes their sentence. On every partial-transcript update, the system fires a semantic retrieval call against a protocol/resource knowledge base and updates a live-updating side panel for the human dispatcher — showing the most relevant guidance before the caller has even finished speaking.

The AI never talks to the caller and never interrupts anyone. It's a copilot for the *human on the call*, not a replacement voice agent. This removes the need for real-time barge-in TTS (having an AI voice interrupt/talk over a live caller), which is both the riskiest thing to build in two weeks and the scariest thing to put in front of a real dispatcher.

## Why Moss (not a vector DB) is what makes this work

This is the part that has to be demonstrably true, not just claimed — it's 20% of the judging score.

- Streaming ASR produces a new partial transcript roughly every 100–300ms while the caller is mid-sentence.
- Firing a semantic lookup on *every single partial update* means potentially several retrieval calls per second, continuously, for the whole call.
- **At <10ms per lookup (Moss)**, the system can keep pace with every partial-transcript tick — the dispatcher's panel updates smoothly and continuously as the sentence unfolds.
- **At typical vector-DB latency (50–200ms with network round trip)**, the system cannot keep up with that update frequency — it would have to throttle, debounce, or skip updates, and the panel would visibly lag or jump instead of flowing live.

In other words: the *frequency* of retrieval calls (driven by streaming partial transcripts) is what turns "search speed" into a load-bearing product requirement instead of a nice-to-have. This is the fix to the original weaker version of this idea (where an AI needed to interrupt the caller mid-utterance) — in that version, retrieval speed didn't matter as much because a spoken sentence provides hundreds of ms of natural runway. In this version, retrieval speed directly determines whether the UI can track the conversation live or falls behind it.

## Architecture

```
Caller audio (mic / recorded call)
        │
        ▼
Streaming ASR (e.g. Deepgram / AssemblyAI / Whisper streaming)
        │  emits partial transcripts every ~100-300ms
        ▼
Partial transcript stream
        │
        ▼
Moss semantic retrieval (sub-10ms, no vector DB)
   ── queries a protocol/resource knowledge base:
      - emergency response protocols (CPR, choking, hazmat, etc.)
      - nearest facility / resource data
      - relevant past-incident notes (optional, for realism)
        │
        ▼
Dispatcher UI (live side panel)
   - resource/protocol cards populate and update in real time
   - visible latency / update-rate counter (proves the Moss story on screen)
        │
        ▼
Human dispatcher (never interrupted, always in control of the call)
```

Optional demo enhancement: run the same partial-transcript stream through a deliberately slower/naive retrieval backend (basic vector DB, or artificially throttled) side-by-side, so judges can visually compare a smooth, live-updating panel (Moss) against a laggy/jumpy one (naive baseline) on the same input.

## Demo script (2-minute video)

1. **Open with the problem** (10-15s): a dispatcher has to listen and search at the same time, today that's manual and slow.
2. **Show the live demo** (60-70s): play/speak a caller scenario (e.g. someone describing a choking incident). Screen shows:
   - live partial transcript scrolling
   - resource/protocol cards populating *before the caller finishes the sentence*
   - an on-screen latency counter showing sub-10ms retrieval firing on every transcript update
3. **Prove Moss is load-bearing** (20-30s): side-by-side comparison — same audio run through a slower backend, panel visibly lags/jumps vs. the smooth Moss-powered version.
4. **Close on impact** (10s): this is a tool that could sit next to any real dispatcher today — a drop-in copilot, not a replacement for human judgment.

## Judging criteria fit

| Criterion | Weight | Fit |
|---|---|---|
| Product & UX | 35% | Real, nameable problem (dispatcher cognitive load under time pressure); clear social impact; human stays in control (no AI-talks-over-caller risk) |
| Technical Execution | 30% | Streaming ASR → continuous retrieval → live UI pipeline is a real, coherent AI pipeline; buildable in ~2 weeks without the hardest voice-stack risk (barge-in TTS) |
| Speed & Latency | 20% | Retrieval frequency (driven by partial-transcript rate) makes sub-10ms latency directly visible and provably necessary — not just fast, but *structurally required* to keep the UI live |
| Demo & Presentation | 15% | Concrete, visual, unfakeable: live transcript + live-updating cards + on-screen latency counter + optional slow-vs-fast side-by-side |

## Build scope / risk notes

- **Removed risk vs. original concept:** no barge-in TTS, no AI voice interrupting a live caller — this was the highest-risk, hardest-to-demo-live element of the original pitch and is now gone entirely.
- **Remaining build surface:**
  - Streaming ASR integration (well-documented APIs — Deepgram/AssemblyAI/Whisper streaming all support partial transcripts out of the box)
  - A protocol/resource knowledge base to index into Moss (can start narrow: a handful of well-known emergency protocols + a small facility-lookup dataset — do not try to cover every possible emergency type for the demo)
  - A live-updating UI panel (React/simple web app is sufficient)
  - The on-screen latency/update-rate instrumentation (important — don't treat this as an afterthought, it's what makes the Speed/Latency score legible to judges)
- **Scope discipline for 2 weeks:** pick one or two demo-able emergency scenarios (e.g. choking, cardiac arrest) rather than building broad protocol coverage. Depth of a convincing live demo beats breadth of coverage.

## Architecture diagram note (for design pass)

The diagram should visually emphasize:
1. The **continuous, high-frequency loop** between partial transcripts and retrieval calls (not a single request/response) — this is the core mechanic that makes Moss load-bearing.
2. A clear contrast box: "typical approach" (ASR → wait for full sentence → single slower lookup → response) crossed out or grayed, next to "this approach" (ASR partial stream → continuous sub-10ms lookups → live UI) — makes the differentiator legible at a glance.
3. The human dispatcher explicitly shown as staying in the loop / in control — reinforces the "copilot, not replacement" framing that's part of the product pitch.
