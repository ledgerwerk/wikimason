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
        "See [[Wiki/Topics/wikimason|WikiMason]] and [Compiled Knowledge](../Concepts/compiled-knowledge.md).",
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
