#!/usr/bin/env bash
# Scans */SKILL.md, extracts YAML frontmatter, and regenerates the skills
# table in README.md between the BEGIN/END markers.
#
# Exit codes:
#   0 — README was updated (or already up to date)
#   1 — error

set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

README="README.md"
BEGIN_MARKER="<!-- BEGIN_SKILLS_TABLE -->"
END_MARKER="<!-- END_SKILLS_TABLE -->"

# ---------- collect rows from SKILL.md frontmatter ----------

rows=""
for skill_file in snowflake-skills/*/SKILL.md; do
  dir="$(dirname "$skill_file")"

  # Skip TEMPLATE directory
  [[ "$(basename "$dir")" == "TEMPLATE" ]] && continue

  name="" desc=""

  # Parse YAML frontmatter (between --- lines)
  in_front=false
  while IFS= read -r line; do
    if [[ "$line" == "---" ]]; then
      if $in_front; then break; fi
      in_front=true
      continue
    fi
    if $in_front; then
      case "$line" in
        name:*)  name="$(echo "$line" | sed 's/^name:[[:space:]]*//' | tr -d '"')" ;;
        description:*)
          desc="$(echo "$line" | sed 's/^description:[[:space:]]*//' | tr -d '"')"
          # Truncate at ". Use " or ". Triggers" to get short summary
          desc="$(echo "$desc" | sed -E 's/\. Use (for|when).*$//' | sed 's/\. Triggers.*$//')"
          ;;
      esac
    fi
  done < "$skill_file"

  if [[ -z "$name" || -z "$desc" ]]; then
    echo "WARNING: $skill_file missing name or description in frontmatter" >&2
    continue
  fi

  rows+="| [$name]($dir/) | $desc |"$'\n'
done

if [[ -z "$rows" ]]; then
  echo "ERROR: No skills found" >&2
  exit 1
fi

# Sort rows alphabetically, drop empty lines
rows="$(echo -n "$rows" | sort | sed '/^$/d')"

# ---------- rebuild the table ----------

# Write the replacement block to a temp file (avoids awk multiline issues)
tmpfile="$(mktemp)"
trap 'rm -f "$tmpfile"' EXIT

{
  echo "$BEGIN_MARKER"
  echo "| Skill | What it does |"
  echo "|-------|-------------|"
  echo "$rows"
  echo "$END_MARKER"
} > "$tmpfile"

# ---------- splice into README ----------

# Replace everything between markers (inclusive) with the new table block
python3 -c "
import sys
readme = open('$README').read()
begin, end = '$BEGIN_MARKER', '$END_MARKER'
i = readme.index(begin)
j = readme.index(end) + len(end)
table = open(sys.argv[1]).read().rstrip('\n')
open('$README', 'w').write(readme[:i] + table + readme[j:])
" "$tmpfile"

echo "Skills table updated in $README"
