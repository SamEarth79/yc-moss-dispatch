# /schedule-resume

## Position in the framework

A standalone command that schedules a **future headless run of
`/implement-epic`** for a specific Epic in this product repo — for "I'm done
for now (or out of tokens), pick this up in N hours." It does not implement
anything itself in this session; it arms `scripts/schedule-resume.sh` and exits.

## Trigger

`/schedule-resume <feature-id> <delay>`

e.g. `/schedule-resume LIB-002 4h`, `/schedule-resume LIB-002 30m`

- `<feature-id>`: the short Epic identifier (e.g. `LIB-002`). The full folder
  name is resolved from `state.json` the same way `/implement-epic` does.
- `<delay>`: how long from now to wait before running. Required — do not guess.

If either argument is missing, ask for it (suggest `4h` as the common
token-reset case).

## What this command does

1. **Resolve the feature folder** from `state.json` using `<feature-id>`,
   exactly as `/implement-epic` does. If it doesn't resolve, stop — don't
   schedule a run that would immediately fail.

2. **Preflight — catch at schedule time what would waste the scheduled run:**
   - The resolved feature has `design: "complete"` and at least one story not
     yet `committed`/`skipped`, or all stories are committed but the PR is not
     `merged`. If there's nothing to do, say so and don't schedule.
   - The `claude` CLI is on PATH and `.claude/scripts/schedule-resume.sh`
     exists (synced via `sync-framework.sh`).
   - No resume is already scheduled (the script's PID file,
     `.claude/.resume-scheduled.pid`, with a live process). If one is, show
     when/what it will run and ask whether to cancel and reschedule
     (`kill <pid>`) — never stack scheduled runs.
   - Warn (schedule anyway) if the working tree is dirty: uncommitted stray
     changes will sit under whatever the headless run does.

3. **Schedule it:**
   ```bash
   bash .claude/scripts/schedule-resume.sh . <delay> "/implement-epic <feature-id> headless"
   ```
   The script detaches a background timer that, after the delay, runs
   `claude -p "/implement-epic <feature-id> headless"` in this repo — the
   same logic as running `/implement-epic` interactively, but under headless
   confirmation rules: auto-commit only on clean test passes, PR/push/review-fix
   loop allowed, **never merges**, parks anything ambiguous in `state.json`
   and stops.

4. **Confirm to the user:** when it fires, what it will run, the log file
   path, and the exact cancel command (`kill <pid>`).

5. Remind them of the one real limitation: the timer is a background process —
   it survives closing this session and the terminal, but not a reboot.
   Reschedule after restarting the machine.

## Rules

- This command never runs `/implement-epic` directly — scheduling and
  executing are deliberately separate; run `/implement-epic <feature-id>`
  yourself if you want it now.
- One scheduled run at a time per repo, enforced by the PID file.
- The scheduled run follows the headless confirmation rules from
  `commands/resume.md` — most importantly: no merges, ever.
