# MOS-STORY-003-003: Extraction merge rules

## Description

As a dispatcher, I want Jev's confident answers to correct the rule-based summary fields, so that weapons, consciousness, patient count and departments are more accurate.

## Acceptance criteria

1. A pure function `merge_jev_fields(rule_fields, jev_answers)` returns `(fields, sources)` without mutating its inputs.
2. Yes/no answers: probability >= `JEV_CONFIDENCE_HIGH` sets true, <= `JEV_CONFIDENCE_LOW` sets false, otherwise the rule value is kept; `weapon` maps to `weapons`; `unconscious` true maps `consciousness` to `unconscious` and false to `conscious`.
3. Patients: the Jev choice is used only when its confidence >= `JEV_CONFIDENCE_HIGH`; choice `0` yields `numberOfPatients = 0`.
4. Departments: start from the rule list; each confident police/ems/fire answer adds (yes) or removes (no) `Police` / `Emergency Medical` / `Fire`, output in that canonical order; uncertain answers leave membership unchanged.
5. `sources` lists a field (`weapons`, `consciousness`, `numberOfPatients`, `departments`) as `"jev"` only when the Jev-derived value differs from the rule value.
6. Partial Jev answers merge what is present; empty or `None` answers return the rule fields and empty `sources`.
7. Unit tests cover each band, boundaries at 0.3/0.7, patients 0 and 10, department add/remove/order, no mutation, and partial answers.

## Requirements implemented

- Business rules #1-#4
- User flows step 3
- architecture.md Override/merge rules

## Depends on

- MOS-STORY-003-001

## Agents likely needed

- [ ] frontend
- [x] backend
- [ ] infrastructure

## Status

- [x] Implemented
- [x] Tested
- [x] Committed
