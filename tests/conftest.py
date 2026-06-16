from __future__ import annotations

import json
import re
from pathlib import Path


def write_source(vault: Path, name: str, title: str | None = None) -> Path:
    """Create a minimal source note in the vault.

    Returns the absolute path to the created file.
    """
    if not name.endswith(".md"):
        name = f"{name}.md"
    target = vault / "Raw/Sources" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    rendered_title = title or name.removesuffix(".md").replace("-", " ").title()
    target.write_text(
        f"""---
Title: "{rendered_title}"
Author: ""
Reference: ""
ContentType:
  - note
Created: 2026-05-28
Processed: false
tags:
  - source
---

# {rendered_title}

Short source summary.
""",
        encoding="utf-8",
    )
    return target


def write_source_rel(vault: Path, name: str, title: str | None = None) -> str:
    """Create a minimal source note in the vault.

    Returns the vault-relative path as a string.
    """
    target = write_source(vault, name, title=title)
    return target.relative_to(vault).as_posix()


def read_json(capsys):
    """Parse the last line of captured stdout as JSON."""
    return json.loads(capsys.readouterr().out.splitlines()[-1])


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def remove_frontmatter_field(text: str, key: str) -> str:
    """Remove a key from YAML frontmatter, preserving the body and blank line."""
    from wikimason.frontmatter import render_frontmatter, split_frontmatter

    data, body = split_frontmatter(text)
    data.pop(key, None)
    body = body.lstrip("\n")
    if body:
        return f"{render_frontmatter(data)}\n\n{body}"
    return f"{render_frontmatter(data)}\n"
