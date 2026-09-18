#!/usr/bin/env bash
#
# Schedules a one-shot headless run of framework work in a product repo,
# for when you want to stop now and have Claude pick up where it left off
# later (e.g. after a token-limit reset). Normally invoked via the
# /schedule-resume command, but works standalone.
#
# Usage (run from anywhere):
#   ./scripts/schedule-resume.sh <path-to-product-repo> <delay> [prompt]
#
#   <delay> is hours by default, or suffixed: 30m, 4h.
#   [prompt] defaults to "/implement-all headless" — the state-driven
#   driver that works through every designed feature in state.json.
#   e.g. ./scripts/schedule-resume.sh ~/Code/my-app 4h
#        ./scripts/schedule-resume.sh ~/Code/my-app 30m "/resume headless"
#
# Behavior:
#   - Sleeps for the delay in a detached background process (survives this
#     terminal closing; does NOT survive a reboot — reschedule if you
#     restart the machine).
#   - Then runs: claude -p "<prompt>" in the product repo.
#     Headless-mode rules (commands/resume.md): commits only on clean test
#     passes, may push and open/update the PR and run the review loop,
#     NEVER merges, and parks anything ambiguous in state.json rather than
#     deciding it.
#   - Logs everything to <product-repo>/.claude/resume-<timestamp>.log.
#
# Only one scheduled resume is allowed at a time per product repo; a PID
# file guards against stacking runs.

set -euo pipefail

TARGET_DIR="${1:-}"
DELAY="${2:-4h}"
PROMPT="${3:-/implement-all headless}"

if [[ -z "$TARGET_DIR" || ! -d "$TARGET_DIR" ]]; then
  echo "Usage: $0 <path-to-product-repo> <delay: e.g. 30m, 4h>" >&2
  exit 1
fi
TARGET_DIR="$(cd "$TARGET_DIR" && pwd)"

if [[ ! -f "$TARGET_DIR/knowledge/state.json" ]]; then
  echo "No knowledge/state.json in $TARGET_DIR — nothing to resume." >&2
  exit 1
fi

if ! command -v claude >/dev/null 2>&1; then
  echo "claude CLI not found on PATH." >&2
  exit 1
fi

# Parse delay into seconds (default unit: hours).
case "$DELAY" in
  *m) SECONDS_TO_WAIT=$(( ${DELAY%m} * 60 )) ;;
  *h) SECONDS_TO_WAIT=$(( ${DELAY%h} * 3600 )) ;;
  *[!0-9]*) echo "Bad delay: $DELAY (use e.g. 30m or 4h)" >&2; exit 1 ;;
  *)  SECONDS_TO_WAIT=$(( DELAY * 3600 )) ;;
esac

PID_FILE="$TARGET_DIR/.claude/.resume-scheduled.pid"
mkdir -p "$TARGET_DIR/.claude"
if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "A resume is already scheduled (PID $(cat "$PID_FILE"))." >&2
  echo "Kill it first if you want to reschedule: kill $(cat "$PID_FILE")" >&2
  exit 1
fi

LOG_FILE="$TARGET_DIR/.claude/resume-$(date +%Y%m%d-%H%M%S).log"

nohup bash -c "
  sleep $SECONDS_TO_WAIT
  cd '$TARGET_DIR'
  echo \"[schedule-resume] starting at \$(date)\"
  claude -p '$PROMPT' --permission-mode acceptEdits
  echo \"[schedule-resume] finished at \$(date) (exit \$?)\"
  rm -f '$PID_FILE'
" >> "$LOG_FILE" 2>&1 &

echo $! > "$PID_FILE"
echo "Scheduled headless run in $TARGET_DIR"
echo "  will run : claude -p \"$PROMPT\""
echo "  fires in : $DELAY"
echo "  log      : $LOG_FILE"
echo "  cancel   : kill $(cat "$PID_FILE")"
