from __future__ import annotations

from pathlib import Path

import pytest

from wikimason.build import build_vault
from wikimason.frontmatter import update_frontmatter
from wikimason.lint import lint_vault
from wikimason.scaffold import init_vault


def test_missing_related_fails(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=True)
    build_vault(vault)
    target = vault / "Wiki/Concepts/compiled-knowledge.md"
    text = target.read_text(encoding="utf-8").replace("## Related", "## Linked")
    target.write_text(text, encoding="utf-8")
    errors = lint_vault(vault)
    assert any("missing ## Related section" in error for error in errors)


def test_source_count_mismatch_fails(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=True)
    build_vault(vault)
    target = vault / "Wiki/Concepts/compiled-knowledge.md"
    target.write_text(
        update_frontmatter(target.read_text(encoding="utf-8"), {"source_count": 9}),
        encoding="utf-8",
    )
    errors = lint_vault(vault)
    assert any("source_count mismatch" in error for error in errors)


def test_unknown_tag_fails(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=True)
    build_vault(vault)
    target = vault / "Wiki/Concepts/compiled-knowledge.md"
    target.write_text(
        update_frontmatter(target.read_text(encoding="utf-8"), {"tags": ["unknown"]}),
        encoding="utf-8",
    )
    errors = lint_vault(vault)
    assert any("unknown tag" in error for error in errors)


@pytest.mark.parametrize(
    ("tool", "snippet"),
    [
        ("obsidian", "\nSee [[Missing/Note]].\n"),
        ("markdown", "\nSee [Missing](../Missing/Note.md).\n"),
    ],
)
def test_unresolved_body_link_fails(tmp_path: Path, tool: str, snippet: str) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=True, tool=tool)
    build_vault(vault)
    target = vault / "Wiki/Concepts/compiled-knowledge.md"
    target.write_text(
        target.read_text(encoding="utf-8") + snippet,
        encoding="utf-8",
    )
    errors = lint_vault(vault)
    assert any("unresolved body link" in error for error in errors)


def test_valid_scaffold_passes(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=True)
    build_vault(vault)
    assert lint_vault(vault) == []


def test_logseq_missing_required_field_fails(tmp_path: Path) -> None:
    """Logseq pages without required 'tags' property fail lint."""
    vault = tmp_path / "vault"
    init_vault(vault, demo=True, profile="logseq")
    build_vault(vault)
    # Find a non-index Logseq page
    target = next(p for p in (vault / "pages").rglob("*.md") if "index" not in p.name)
    text = target.read_text(encoding="utf-8")
    text = "\n".join(
        line for line in text.splitlines() if not line.startswith("- tags::")
    )
    target.write_text(text, encoding="utf-8")
    errors = lint_vault(vault)
    assert any("missing field" in error for error in errors), f"Got: {errors}"


def test_logseq_invalid_status_fails(tmp_path: Path) -> None:
    """Logseq pages with invalid status fail lint."""
    vault = tmp_path / "vault"
    init_vault(vault, demo=True, profile="logseq")
    build_vault(vault)
    target = next(p for p in (vault / "pages").rglob("*.md") if "index" not in p.name)
    text = target.read_text(encoding="utf-8")
    text = text.replace("- status:: active", "- status:: invalid_status")
    target.write_text(text, encoding="utf-8")
    errors = lint_vault(vault)
    assert any("invalid status" in error for error in errors), f"Got: {errors}"


def test_logseq_source_count_mismatch_fails(tmp_path: Path) -> None:
    """Logseq pages with source_count mismatch fail lint."""
    vault = tmp_path / "vault"
    init_vault(vault, demo=True, profile="logseq")
    build_vault(vault)
    target = next(p for p in (vault / "pages").rglob("*.md") if "index" not in p.name)
    text = target.read_text(encoding="utf-8")
    text = text.replace("- source_count:: 1", "- source_count:: 99")
    target.write_text(text, encoding="utf-8")
    errors = lint_vault(vault)
    assert any("source_count mismatch" in error for error in errors), f"Got: {errors}"


def test_valid_logseq_scaffold_passes(tmp_path: Path) -> None:
    """A fresh Logseq scaffold passes lint."""
    vault = tmp_path / "vault"
    init_vault(vault, demo=True, profile="logseq")
    build_vault(vault)
    assert lint_vault(vault) == []
