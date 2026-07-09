#!/usr/bin/env bash
# Scaffold a new skill from template/new-skill/.
#
# Usage:
#   ./scripts/new-skill.sh <domain> <skill-name>
#
# Example:
#   ./scripts/new-skill.sh events pexip-event-replay
#
# Creates: skills/<domain>/<skill-name>/SKILL.md (and any sibling template files)
# and rewrites the frontmatter `name` field to match the directory name.
set -euo pipefail

if [[ $# -ne 2 ]]; then
    echo "usage: $0 <domain> <skill-name>" >&2
    echo "  e.g. $0 events pexip-event-replay" >&2
    exit 2
fi

domain="$1"
name="$2"

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/.." && pwd)"

src="$root/template/new-skill"
dst="$root/skills/$domain/$name"

if [[ ! -d "$src" ]]; then
    echo "error: template not found at $src" >&2
    exit 1
fi

if [[ -e "$dst" ]]; then
    echo "error: $dst already exists" >&2
    exit 1
fi

mkdir -p "$(dirname "$dst")"
cp -r "$src" "$dst"

# Replace the FIXME name in the new SKILL.md.
# Use a portable sed -i that works on macOS bash 3.2 (BSD sed) and GNU sed.
if sed --version >/dev/null 2>&1; then
    # GNU
    sed -i "s/^name: pexip-FIXME$/name: $name/" "$dst/SKILL.md"
else
    # BSD (macOS)
    sed -i '' "s/^name: pexip-FIXME$/name: $name/" "$dst/SKILL.md"
fi

echo "Created: $dst/SKILL.md"
echo "Now edit the FIXME markers and fill in the body. Then run:"
echo "  ./scripts/validate-skills.py"
