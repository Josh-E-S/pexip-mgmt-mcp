#!/usr/bin/env python3
"""Lint every skills/**/SKILL.md against the pexip-mgmt-skills conventions.

Rules (see spec/pexip-conventions.md):

  1. Frontmatter must have exactly: name, description, license.
  2. `name` must match the parent directory name.
  3. `name` must be kebab-case and prefixed `pexip-`.
  4. Combined `description` ≤ 1,536 characters.
  5. License must be `MIT`.
  6. No host-specific frontmatter keys (allowed-tools, disable-model-invocation,
     context, paths, hooks, agent, model, effort, argument-hint, arguments,
     user-invocable, when_to_use, shell).
  7. Body must end with a "Reference source" or "Authoritative docs" section.
  8. Body should be under 500 lines (warn at 250).

Exit code: 0 = all clean, 1 = warnings only, 2 = errors.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

HOST_SPECIFIC_KEYS = {
    "allowed-tools",
    "disable-model-invocation",
    "user-invocable",
    "context",
    "agent",
    "paths",
    "hooks",
    "argument-hint",
    "arguments",
    "model",
    "effort",
    "shell",
    "when_to_use",
}

DESCRIPTION_HARD_CAP = 1536
BODY_LINES_HARD_CAP = 500
BODY_LINES_WARN = 250
NAME_RE = re.compile(r"^pexip-[a-z0-9]+(-[a-z0-9]+)*$")


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Tiny YAML frontmatter parser — handles plain string and quoted values."""
    if not text.startswith("---\n"):
        raise ValueError("file does not start with '---'")
    body_start = text.find("\n---\n", 4)
    if body_start == -1:
        raise ValueError("no closing '---' for frontmatter")
    raw = text[4:body_start]
    body = text[body_start + 5 :]
    fm: dict[str, Any] = {}
    for raw_line in raw.splitlines():
        line = raw_line.rstrip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"malformed frontmatter line: {line!r}")
        k, _, v = line.partition(":")
        v = v.strip()
        # Strip wrapping quotes; treat everything as string.
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            v = v[1:-1]
        fm[k.strip()] = v
    return fm, body


def check(skill_md: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    text = skill_md.read_text(encoding="utf-8")
    try:
        fm, body = parse_frontmatter(text)
    except ValueError as e:
        return [f"frontmatter: {e}"], []

    # 1. Required keys.
    for key in ("name", "description", "license"):
        if key not in fm:
            errors.append(f"frontmatter: missing required key `{key}`")

    # 6. No host-specific keys.
    for key in fm:
        if key in HOST_SPECIFIC_KEYS:
            errors.append(
                f"frontmatter: `{key}` is host-specific — see spec/pexip-conventions.md"
            )

    # 2. Name matches directory.
    dir_name = skill_md.parent.name
    if fm.get("name") and fm["name"] != dir_name:
        errors.append(
            f"frontmatter: name={fm['name']!r} does not match directory name {dir_name!r}"
        )

    # 3. Name shape.
    if fm.get("name") and not NAME_RE.match(fm["name"]):
        errors.append(
            f"frontmatter: name={fm['name']!r} must be kebab-case and prefixed `pexip-`"
        )

    # 4. Description length.
    if "description" in fm:
        n = len(fm["description"])
        if n > DESCRIPTION_HARD_CAP:
            errors.append(
                f"frontmatter: description is {n} chars (cap {DESCRIPTION_HARD_CAP})"
            )

    # 5. License.
    if fm.get("license") and fm["license"] != "MIT":
        errors.append(f"frontmatter: license={fm['license']!r} must be 'MIT'")

    # 7. Reference source footer.
    body_lower = body.lower()
    if "## reference source" not in body_lower and "## authoritative docs" not in body_lower:
        errors.append(
            "body: missing '## Reference source' (or '## Authoritative docs') section"
        )

    # 8. Body line counts.
    lines = body.count("\n")
    if lines > BODY_LINES_HARD_CAP:
        errors.append(f"body: {lines} lines exceeds cap {BODY_LINES_HARD_CAP}")
    elif lines > BODY_LINES_WARN:
        warnings.append(
            f"body: {lines} lines exceeds target {BODY_LINES_WARN} — consider splitting"
        )

    return errors, warnings


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    skills_dir = root / "skills"
    if not skills_dir.is_dir():
        print(f"error: {skills_dir} does not exist", file=sys.stderr)
        return 2

    skill_files = sorted(skills_dir.glob("**/SKILL.md"))
    if not skill_files:
        print(f"error: no SKILL.md files under {skills_dir}", file=sys.stderr)
        return 2

    total_errors = 0
    total_warnings = 0
    for skill_md in skill_files:
        rel = skill_md.relative_to(root)
        errors, warnings = check(skill_md)
        if not errors and not warnings:
            print(f"OK   {rel}")
            continue
        for e in errors:
            print(f"ERR  {rel}: {e}")
            total_errors += 1
        for w in warnings:
            print(f"WARN {rel}: {w}")
            total_warnings += 1

    print()
    print(
        f"{len(skill_files)} skill(s) checked. "
        f"{total_errors} error(s), {total_warnings} warning(s)."
    )
    return 2 if total_errors else (1 if total_warnings else 0)


if __name__ == "__main__":
    sys.exit(main())
