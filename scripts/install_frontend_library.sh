#!/usr/bin/env bash
# Link the maintained library without replacing an installed Cortex CLI.
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
claude_target="${CLAUDE_DIR:-$HOME/.claude}"
codex_target="${CODEX_DIR:-${CODEX_HOME:-$HOME/.codex}}"

python3 "$repo_dir/scripts/validate_frontend_library.py"

# Check all destinations before writing any links.
for agent_home in "$claude_target" "$codex_target"; do
  [ -d "$agent_home" ] || continue
  for pair in "cortex-frontend:frontend" "skills/cortex-frontend-design:skills/cortex-frontend-design"; do
    destination="$agent_home/${pair%%:*}"
    source="$repo_dir/${pair#*:}"
    if [ -e "$destination" ] || [ -L "$destination" ]; then
      if [ ! -L "$destination" ] || [ "$(readlink "$destination")" != "$source" ]; then
        echo "Existing destination requires manual reconciliation: $destination" >&2
        exit 1
      fi
    fi
  done
done

for agent_home in "$claude_target" "$codex_target"; do
  if [ ! -d "$agent_home" ]; then
    echo "Skipped absent agent home: $agent_home"
    continue
  fi
  mkdir -p "$agent_home/skills"
  [ -L "$agent_home/cortex-frontend" ] || ln -s "$repo_dir/frontend" "$agent_home/cortex-frontend"
  [ -L "$agent_home/skills/cortex-frontend-design" ] || ln -s "$repo_dir/skills/cortex-frontend-design" "$agent_home/skills/cortex-frontend-design"
  echo "Frontend library linked in $agent_home"
done
