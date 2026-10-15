#!/usr/bin/env bash
# Cortex installer — copies the routing layer into ~/.claude/
# Idempotent. Doesn't overwrite your cortex.md if you've already populated it.
# Doesn't touch settings.json — SessionStart hook is opt-in via README instructions.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${CORTEX_HOME:-${CLAUDE_DIR:-$HOME/.claude}}"
BIN_DIR="$CLAUDE_DIR/bin"
SKILLS_DIR="$CLAUDE_DIR/skills"
CODEX_DIR="${CODEX_DIR:-${CODEX_HOME:-$HOME/.codex}}"
SHARED_SKILLS_DIR="$HOME/.agents/skills"

# Keep all exposed copies maintained, without creating optional agent homes.
skill_targets=("$SKILLS_DIR")
skill_names=("cortex-log cortex-learn cortex-reroute cortex-init")
if [ -e "$CODEX_DIR" ] || [ -L "$CODEX_DIR" ]; then
  skill_targets+=("$CODEX_DIR/skills")
  skill_names+=("cortex-log cortex-learn cortex-reroute cortex-delegate")
fi
if [ -e "$HOME/.agents" ] || [ -L "$HOME/.agents" ]; then
  skill_targets+=("$SHARED_SKILLS_DIR")
  skill_names+=("cortex-log cortex-learn cortex-reroute")
fi

bold()  { printf '\033[1m%s\033[0m\n' "$*"; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }
yellow(){ printf '\033[33m%s\033[0m\n' "$*"; }
dim()   { printf '\033[2m%s\033[0m\n' "$*"; }

bold "Installing Cortex into $CLAUDE_DIR"
echo

skill_digest() {
  python3 -c 'import hashlib, pathlib, sys; print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())' "$1"
}

known_skill_content() {
  local source="$1" path="$2" stamp="$(dirname "$2")/.cortex-installed.sha256"
  local recorded relative revision repository
  cmp -s "$source" "$path" && return 0
  if [ -f "$stamp" ]; then
    recorded="$(<"$stamp")"
    if [[ "$recorded" =~ ^[0-9a-f]{64}$ ]] && [ "$recorded" = "$(skill_digest "$path")" ]; then
      return 0
    fi
  fi
  # Bootstrap installs made before content stamps existed. Only exact versions
  # of this skill in this checkout's history count, never arbitrary Git blobs.
  repository="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)" || return 1
  [ "$repository" = "$SCRIPT_DIR" ] || return 1
  relative="${source#"$SCRIPT_DIR/"}"
  while IFS= read -r revision; do
    if git -C "$SCRIPT_DIR" show "$revision:$relative" 2>/dev/null | cmp -s - "$path"; then
      return 0
    fi
  done < <(git -C "$SCRIPT_DIR" log --format=%H -- "$relative" 2>/dev/null)
  return 1
}

# Preflight every destination before writing anything. Never copy through links,
# including dangling links or linked ancestors, or replace a customized skill.
check_destination() {
  local path="$1" kind="$2" source="${3:-}" ancestor="$1"
  while [ "$ancestor" != / ] && [ "$ancestor" != . ]; do
    if [ -L "$ancestor" ]; then
      echo "Conflict: symlink at $ancestor" >&2
      exit 1
    fi
    ancestor="$(dirname "$ancestor")"
    if [ -e "$ancestor" ] && [ ! -d "$ancestor" ]; then
      echo "Conflict: non-directory ancestor $ancestor" >&2
      exit 1
    fi
  done
  if [ -e "$path" ]; then
    if { [ "$kind" = dir ] && [ ! -d "$path" ]; } ||
       { [ "$kind" != dir ] && [ ! -f "$path" ]; }; then
      echo "Conflict: unexpected destination type at $path" >&2
      exit 1
    fi
    if [ "$kind" = skill ] && ! known_skill_content "$source" "$path"; then
      echo "Conflict: customized skill at $path; preserve and merge it manually" >&2
      exit 1
    fi
  fi
}

check_destination "$BIN_DIR" dir
check_destination "$SKILLS_DIR" dir
check_destination "$BIN_DIR/cortex" file
check_destination "$BIN_DIR/cortex_jev.py" file
check_destination "$BIN_DIR/cortex_skill_evidence.py" file
for index in "${!skill_targets[@]}"; do
  target="${skill_targets[$index]}"
  check_destination "$target" dir
  for skill in ${skill_names[$index]}; do
    check_destination "$target/$skill" dir
    check_destination "$target/$skill/.cortex-installed.sha256" file
    check_destination "$target/$skill/SKILL.md" skill "$SCRIPT_DIR/skills/$skill/SKILL.md"
  done
done
check_destination "$CLAUDE_DIR/cortex.md" file
check_destination "$CLAUDE_DIR/cortex.md.new" file
check_destination "$CLAUDE_DIR/cortex-log.jsonl" file

# Ensure target dirs exist only after the complete preflight succeeds.
mkdir -p "$BIN_DIR" "$SKILLS_DIR"

# 1. CLI binary
install -m 0755 "$SCRIPT_DIR/bin/cortex" "$BIN_DIR/cortex"
install -m 0644 "$SCRIPT_DIR/bin/cortex_jev.py" "$BIN_DIR/cortex_jev.py"
install -m 0644 "$SCRIPT_DIR/bin/cortex_skill_evidence.py" "$BIN_DIR/cortex_skill_evidence.py"
green "  ✓ bin/cortex          → $BIN_DIR/cortex"
green "  ✓ bin/cortex_jev.py    → $BIN_DIR/cortex_jev.py (adviser off by default)"

# 2. Skills
for index in "${!skill_targets[@]}"; do
  target="${skill_targets[$index]}"
  for skill in ${skill_names[$index]}; do
    mkdir -p "$target/$skill"
    cp "$SCRIPT_DIR/skills/$skill/SKILL.md" "$target/$skill/SKILL.md"
    skill_digest "$target/$skill/SKILL.md" > "$target/$skill/.cortex-installed.sha256"
    green "  ✓ skills/$skill/SKILL.md → $target/$skill"
  done
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
# Printed commands must work even after a one-shot installer override, and when
# the selected state directory contains spaces or shell metacharacters.
printf -v cortex_command 'CORTEX_HOME=%q python3 %q' "$CLAUDE_DIR" "$BIN_DIR/cortex"
dim   "  1. Add @cortex.md to your CLAUDE.md so it loads globally:"
printf "       echo '@cortex.md' >> %q\n" "$CLAUDE_DIR/CLAUDE.md"
echo
dim   "  2. Build your registry automatically from what you already run:"
echo  "       run  /cortex-init   in your agent"
echo  "       (or  $cortex_command init   to just see the scan)"
dim   "     Keep the selected state root exported in the agent's environment:"
printf '       export CORTEX_HOME=%q\n' "$CLAUDE_DIR"
dim   "     It discovers your agents, skills, MCPs and CLIs and writes them into"
dim   "     the Workflow Registry — never overwriting your setup without a backup."
echo
dim   "  3. (Optional) Wire the SessionStart hook for weekly self-audits — see the README."
echo
dim   "  4. Try it:"
echo  "       $cortex_command doctor"
echo  "       $cortex_command --help"
echo
