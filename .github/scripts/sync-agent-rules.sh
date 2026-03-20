#!/usr/bin/env bash
# Syncs SKILL.md files from snowflake-skills/ into agent-specific config directories.
#
# Creates/updates:
#   .cursor/rules/<skill>.mdc
#   .windsurf/rules/<skill>.md
#   .claude/rules/<skill>.md
#
# Usage: .github/scripts/sync-agent-rules.sh
#   Run after modifying any SKILL.md to keep agent dirs in sync.

set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

mkdir -p .cursor/rules .windsurf/rules .claude/rules

# Clean existing agent rules (remove stale skills that were deleted)
rm -f .cursor/rules/*.mdc .windsurf/rules/*.md .claude/rules/*.md

synced=0
for skill_file in snowflake-skills/*/SKILL.md; do
  dir="$(dirname "$skill_file")"
  name="$(basename "$dir")"

  # Skip TEMPLATE
  [[ "$name" == "TEMPLATE" ]] && continue

  cp "$skill_file" ".cursor/rules/${name}.mdc"
  cp "$skill_file" ".windsurf/rules/${name}.md"
  cp "$skill_file" ".claude/rules/${name}.md"
  ((synced++)) || true
done

echo "Synced $synced skill(s) to .cursor/rules/, .windsurf/rules/, .claude/rules/"
