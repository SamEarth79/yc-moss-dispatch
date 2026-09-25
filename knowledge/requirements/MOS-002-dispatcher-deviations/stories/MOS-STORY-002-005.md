# MOS-STORY-002-005: Dispatcher voice channel

## Description

As a dispatcher, I want to speak my reply with a mic, so that I can dictate it instead of typing.

## Acceptance criteria

1. `voice_start` accepts `channel: "caller" | "dispatcher"` (default `caller`); the server keeps a separate `DeepgramStream` slot per channel and routes dispatcher results as `dispatcher_voice_transcript` without touching the caller transcript state.
2. The dispatcher panel has its own mic button with a distinct accessible name ("Start dispatcher mic") and `aria-pressed`, writing live ASR text into the dispatcher textarea.
3. The client voice state (`stopActiveVoice`, `voiceReadyResolver`) is channel-aware; existing caller mic and sample-call behaviour is unchanged.
4. The dispatcher mic is disabled while the caller mic or sample call is active, and vice versa, with the reason shown.
5. Mic denial or unavailability is reported in the dispatcher panel's own status line, not the caller's.
6. Mock buttons and Submit are disabled while the dispatcher mic is listening.

## Requirements implemented

- User flows step 2
- Technical constraints #1
- architecture.md Key decisions (voice channel)

## Depends on

- MOS-STORY-002-004

## Agents likely needed

- [x] frontend
- [x] backend
- [ ] infrastructure

## Status

- [x] Implemented
- [x] Tested
- [x] Committed
