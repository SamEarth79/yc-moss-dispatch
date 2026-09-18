#!/usr/bin/env bash
#
# Syncs this framework into the .claude/ directory of the current working directory.
#
# Usage (run from the target product repo):
#   bash /path/to/Agent-Framework/scripts/sync-framework.sh

set -euo pipefail

FRAMEWORK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="$(pwd)"
CLAUDE_DIR="$TARGET_DIR/.claude"

if [[ "$FRAMEWORK_DIR" == "$TARGET_DIR" ]]; then
  echo "Error: run this from the target product repo, not from the framework repo itself." >&2
  exit 1
fi

mkdir -p "$CLAUDE_DIR"

for dir in commands agents templates rules skills scripts; do
  src="$FRAMEWORK_DIR/$dir"
  [[ -d "$src" ]] || continue
  mkdir -p "$CLAUDE_DIR/$dir"
  rsync -a --delete "$src/" "$CLAUDE_DIR/$dir/"
done

cp "$FRAMEWORK_DIR/CLAUDE.md" "$CLAUDE_DIR/CLAUDE.md"

chmod +x "$CLAUDE_DIR/scripts/"*.sh 2>/dev/null || true

echo "Synced framework from $FRAMEWORK_DIR"
echo "             into    $CLAUDE_DIR"
