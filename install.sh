#!/usr/bin/env bash
# Cortex installer — copies the routing layer into ~/.claude/
# Idempotent. Doesn't overwrite your cortex.md if you've already populated it.
# Doesn't touch settings.json — SessionStart hook is opt-in via README instructions.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${CLAUDE_DIR:-$HOME/.claude}"
BIN_DIR="$CLAUDE_DIR/bin"
SKILLS_DIR="$CLAUDE_DIR/skills"

bold()  { printf '\033[1m%s\033[0m\n' "$*"; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }
yellow(){ printf '\033[33m%s\033[0m\n' "$*"; }
dim()   { printf '\033[2m%s\033[0m\n' "$*"; }

bold "Installing Cortex into $CLAUDE_DIR"
echo

# Ensure target dirs exist
mkdir -p "$BIN_DIR" "$SKILLS_DIR"

# 1. CLI binary
install -m 0755 "$SCRIPT_DIR/bin/cortex" "$BIN_DIR/cortex"
green "  ✓ bin/cortex          → $BIN_DIR/cortex"

# 2. Skills (3 of them)
for skill in cortex-log cortex-learn cortex-reroute; do
  mkdir -p "$SKILLS_DIR/$skill"
  cp "$SCRIPT_DIR/skills/$skill/SKILL.md" "$SKILLS_DIR/$skill/SKILL.md"
  green "  ✓ skills/$skill/SKILL.md"
done

# 3. cortex.md — only if not already present
CORTEX_MD="$CLAUDE_DIR/cortex.md"
if [ -f "$CORTEX_MD" ]; then
  cp "$SCRIPT_DIR/templates/cortex.md" "$CORTEX_MD.new"
  yellow "  ! cortex.md already exists — wrote template to $CORTEX_MD.new"
  yellow "    Diff and merge by hand. Don't blow away your customizations."
else
  cp "$SCRIPT_DIR/templates/cortex.md" "$CORTEX_MD"
  green "  ✓ templates/cortex.md → $CORTEX_MD"
fi

# 4. Initialize empty log if missing (so /cortex-log doesn't error on first run)
LOG="$CLAUDE_DIR/cortex-log.jsonl"
[ -f "$LOG" ] || touch "$LOG"

echo
green "Done."
echo
bold "Next steps"
dim   "  1. Add @cortex.md to your CLAUDE.md so it loads globally:"
echo  "       echo '@cortex.md' >> $CLAUDE_DIR/CLAUDE.md"
echo
dim   "  2. (Optional) Wire the SessionStart hook for weekly self-audits:"
dim   "     See the README → 'Optional: SessionStart hook' section."
echo
dim   "  3. Edit $CORTEX_MD — populate the Workflow Registry with YOUR systems."
dim   "     The starter is a skeleton; the value is in your own routes."
echo
dim   "  4. Try it:"
echo  "       python3 $BIN_DIR/cortex doctor"
echo  "       python3 $BIN_DIR/cortex --help"
echo
