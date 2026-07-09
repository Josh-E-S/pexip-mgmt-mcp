#!/usr/bin/env bash
# Install every skill in this package into a Claude-Code-style skills directory.
#
# Usage:
#   ./scripts/install.sh                          # → ~/.claude/skills
#   ./scripts/install.sh ./.claude/skills         # → relative target
#   ./scripts/install.sh --symlink ~/...          # symlinks instead of copies
#
# The Agent Skills hosts expect skills at <target>/<skill-name>/SKILL.md (flat).
# This package groups skills under skills/<domain>/<skill-name>/ for human
# navigation. We flatten on install — the domain folder is dropped.
set -euo pipefail

mode=copy
target="${HOME}/.claude/skills"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --symlink) mode=symlink ;;
        --copy)    mode=copy ;;
        -h|--help)
            sed -n '2,/^set -euo/p' "$0" | sed 's/^# \{0,1\}//' | head -n -1
            exit 0
            ;;
        *) target="$1" ;;
    esac
    shift
done

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/.." && pwd)"
src="$root/skills"

if [[ ! -d "$src" ]]; then
    echo "error: skills directory not found at $src" >&2
    exit 1
fi

mkdir -p "$target"

count=0
while IFS= read -r -d '' skill_md; do
    skill_dir="$(dirname "$skill_md")"
    name="$(basename "$skill_dir")"
    dest="$target/$name"
    if [[ -e "$dest" ]]; then
        echo "skip   $name (already exists at $dest)"
        continue
    fi
    case "$mode" in
        copy)
            cp -r "$skill_dir" "$dest"
            echo "copy   $name"
            ;;
        symlink)
            ln -s "$skill_dir" "$dest"
            echo "link   $name → $skill_dir"
            ;;
    esac
    count=$((count + 1))
done < <(find "$src" -name SKILL.md -print0 | sort -z)

echo
echo "Installed $count skill(s) to $target (mode: $mode)."
