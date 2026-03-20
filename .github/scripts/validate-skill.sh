#!/usr/bin/env bash
# Validates skill directories in a PR.
# Usage: validate-skill.sh <skill-dir> [<skill-dir> ...]
# If no args, validates all */SKILL.md directories.
#
# Exit codes:
#   0 — all checks passed
#   1 — one or more checks failed

set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

errors=0

check() {
  local skill_dir="$1"
  local ok=true

  echo "Checking $skill_dir ..."

  # 1. SKILL.md exists
  if [[ ! -f "$skill_dir/SKILL.md" ]]; then
    echo "  FAIL: SKILL.md not found"
    ok=false
  else
    # 2. YAML frontmatter has name
    if ! grep -q '^name:' "$skill_dir/SKILL.md"; then
      echo "  FAIL: SKILL.md missing 'name' in YAML frontmatter"
      ok=false
    fi

    # 3. YAML frontmatter has description
    if ! grep -q '^description:' "$skill_dir/SKILL.md"; then
      echo "  FAIL: SKILL.md missing 'description' in YAML frontmatter"
      ok=false
    fi

    # 4. "When to Use" section exists
    if ! grep -q '^## When to Use' "$skill_dir/SKILL.md"; then
      echo "  FAIL: SKILL.md missing '## When to Use' section"
      ok=false
    fi
  fi

  # 5. README.md exists
  if [[ ! -f "$skill_dir/README.md" ]]; then
    echo "  FAIL: README.md not found"
    ok=false
  fi

  # 6. No credential files
  local cred_patterns=("*.p8" "*.pem" "*.key" "*.der" ".env" ".env.*" "credentials.json" "secrets.json" "*.secret")
  for pattern in "${cred_patterns[@]}"; do
    local found
    found="$(find "$skill_dir" -name "$pattern" -not -path '*/.git/*' 2>/dev/null || true)"
    if [[ -n "$found" ]]; then
      echo "  FAIL: Credential file detected: $found"
      ok=false
    fi
  done

  if $ok; then
    echo "  PASS"
  else
    ((errors++)) || true
  fi
}

# ---------- determine which dirs to check ----------

dirs=()
if [[ $# -gt 0 ]]; then
  dirs=("$@")
else
  for skill_file in snowflake-skills/*/SKILL.md; do
    dirs+=("$(dirname "$skill_file")")
  done
fi

if [[ ${#dirs[@]} -eq 0 ]]; then
  echo "No skill directories to validate."
  exit 0
fi

for dir in "${dirs[@]}"; do
  check "$dir"
done

echo ""
if [[ $errors -gt 0 ]]; then
  echo "FAILED: $errors skill(s) have issues."
  exit 1
else
  echo "ALL PASSED: ${#dirs[@]} skill(s) validated."
  exit 0
fi
