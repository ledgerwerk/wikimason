from __future__ import annotations

from pathlib import Path

from wikimason.config import default_config
from wikimason.link_format import (
    extract_internal_link_targets,
    format_link,
    normalize_internal_link_target,
)


def test_format_link_uses_profile_defaults(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    obsidian = default_config("obsidian", vault)
    markdown = default_config("markdown", vault)

    assert (
        format_link(
            obsidian.links,
            "Wiki/Concepts/compiled-knowledge.md",
            label="Compiled Knowledge",
        )
        == "[[Wiki/Concepts/compiled-knowledge|Compiled Knowledge]]"
    )
    assert (
        format_link(
            markdown.links,
            "Wiki/Concepts/compiled-knowledge.md",
            label="Compiled Knowledge",
            source_path="Wiki/Topics/wikimason.md",
        )
        == "[[Wiki/Concepts/compiled-knowledge|Compiled Knowledge]]"
    )


def test_extract_internal_link_targets_accepts_mixed_syntax(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    targets = extract_internal_link_targets(
        "See [[Wiki/Topics/wikimason|WikiMason]] and [Compiled Knowledge](../Concepts/compiled-knowledge.md).",  # noqa: E501
        vault=vault,
        source_path="Wiki/Topics/example.md",
    )

    assert "Wiki/Topics/wikimason.md" in targets
    assert "Wiki/Concepts/compiled-knowledge.md" in targets


def test_normalize_internal_link_target_handles_markdown_and_wikilinks() -> None:
    assert (
        normalize_internal_link_target("[[Wiki/Topics/wikimason]]")
        == "Wiki/Topics/wikimason.md"
    )
    assert (
        normalize_internal_link_target(
            "[Compiled Knowledge](../Concepts/compiled-knowledge.md)",
            source_path="Wiki/Topics/wikimason.md",
        )
        == "Wiki/Concepts/compiled-knowledge.md"
    )


def test_links_check_ignores_markdown_links_inside_code_fences(
    tmp_path: Path, capsys
) -> None:
    from wikimason.cli import main
    from wikimason.scaffold import init_vault

    vault = tmp_path / "vault"
    init_vault(vault)
    note = vault / "Wiki/Concepts/examples.md"
    note.write_text(
        """---
tags:
  - concept
topics: []
status: active
created: 2026-05-29
updated: 2026-05-29
sources: []
source_count: 0
aliases: []
---

# Examples

```markdown
[example](path.md)
[[missing.md]]
```

Use `[example](path.md)` as literal syntax.

## Related

-

## Sources

-
""",
        encoding="utf-8",
    )

    assert main(["links", "check", "--vault", str(vault), "--format", "json"]) == 0
