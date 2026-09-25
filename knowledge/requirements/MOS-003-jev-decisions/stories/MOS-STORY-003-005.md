# MOS-STORY-003-005: Jev tag in the summary panel

## Description

As a viewer, I want to see when Jev refined a value, so that the model's contribution is visible without cluttering the panel.

## Acceptance criteria

1. A `source-tag--jev` "Jev" tag appears next to the existing "LLM generated" tag in the Structured Summary panel via a right-aligned `.source-tag-group`, with panel heading padding adjusted so tags do not overlap it; text label plus `title`/`aria-label` (e.g. "Some values refined by Jev decision model"); tag text contrast is checked against the light theme.
2. The tag shows only after at least one field has `sources[field] === "jev"` in the current call and hides on caller/call reset; when Jev is unavailable or agrees with the rules the panel is pixel-identical to today.
3. `renderExtraction` reads `fields.sources`; rows whose value changed since the previous render get a one-time ~600 ms background fade and a small dot with `title="Refined by Jev"` on overridden rows; no layout shift; the fade respects `prefers-reduced-motion`.
4. Value changes are announced politely without making the whole list live (e.g. a visually hidden status such as "Weapons updated to Yes by Jev").
5. Colours come from existing tokens/variables (a lavender tag variant), no hardcoded palette outside existing patterns.
6. Playwright E2E with the stub app covers: no tag before any override, tag after an override update, per-row change cue only on changed rows, tag reset on caller change, no tag when `sources` is empty, and accessible names.

## Requirements implemented

- User flows step 3
- Key decisions (attribution)

## Depends on

- MOS-STORY-003-004

## Agents likely needed

- [x] frontend
- [ ] backend
- [ ] infrastructure

## Status

- [ ] Implemented
- [ ] Tested
- [ ] Committed
