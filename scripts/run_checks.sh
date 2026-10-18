#!/usr/bin/env bash
# Offline contributor checks. Each runtime suite creates its own disposable state.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
export PYTHONDONTWRITEBYTECODE=1
unset CORTEX_INTAKE_COMMON CORTEX_INTAKE_COMMON_COPY

python_bin="${PYTHON:-python3}"
"$python_bin" --version
for test_file in \
  eval/test_cortex_cli.py \
  eval/test_cortex_integrity.py \
  eval/test_install_sync_integrity.py \
  eval/test_hint_selector.py \
  eval/test_host_identity.py \
  eval/test_cortex_delegate_skill.py; do
  printf '\nRunning %s\n' "$test_file"
  "$python_bin" "$test_file"
done

"$python_bin" scripts/record_demo.py --check
"$python_bin" scripts/check_docs.py
if command -v node >/dev/null 2>&1; then
  node scripts/build_brand_assets.mjs --check
else
  printf '\nSkipping generated logo comparison (Node.js is not installed).\n'
fi
printf '\nAll selected offline checks passed.\n'
