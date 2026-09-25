# MOS-STORY-002-006: Related Deviations UI

## Description

As a dispatcher, I want related past deviations shown below the protocol steps, so that I can see how others handled a similar call while remembering the protocol is authoritative.

## Acceptance criteria

1. A "Related Deviations" subsection with a "Moss retrieved" tag and an "unreviewed" label sits in the instruction panel between the instruction steps and the dispatch action button.
2. It renders up to 2 cards from `deviation_update`, each showing the deviation summary, date, clamped "Protocol said" and "Dispatcher said" lines, and the reason when present, with neutral wording (no "wrong"/"violation") and a teal accent.
3. With no results it shows the placeholder "Related deviations appear as the call develops…"; it clears when the caller changes or the transcript is reset.
4. Long text is clamped with the full text in a `title`; unbroken strings wrap.
5. The subsection is not an `aria-live` region and has an accessible label.
6. The suggested protocol chunk is never re-ranked or altered by deviations.

## Requirements implemented

- User flows step 6
- Business rules #3
- Scope in-scope item 4

## Depends on

- MOS-STORY-002-003

## Agents likely needed

- [x] frontend
- [ ] backend
- [ ] infrastructure

## Status

- [x] Implemented
- [x] Tested
- [x] Committed
