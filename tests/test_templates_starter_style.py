from __future__ import annotations

from pathlib import Path

import pytest

from wikimason.errors import UsageError
from wikimason.notes import new_note
from wikimason.scaffold import init_vault
from wikimason.templates import template_path


def test_init_writes_starter_templates(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=False)
    for name in [
        "topic-note.md",
        "concept-note.md",
        "entity-note.md",
        "project-note.md",
        "log-note.md",
    ]:
        text = (vault / "_templates" / name).read_text(encoding="utf-8")
        assert "{{title}}" in text
        assert "{{date}}" in text
        assert "## Related" in text
        assert "## Sources" in text
    source = (vault / "_templates/source-note.md").read_text(encoding="utf-8")
    for field in (
        "Title:",
        "Author:",
        "Reference:",
        "ContentType:",
        "Created:",
        "Processed:",
        "tags:",
    ):
        assert field in source


def test_schema_docs_created(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=False)
    for name in [
        "frontmatter-schema.md",
        "lint-checklist.md",
        "naming-conventions.md",
        "workflow-examples.md",
        "command-reference.md",
    ]:
        assert (vault / "Schema" / name).exists()


def test_note_new_uses_vault_template(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=False)
    (vault / "Raw/Sources" / "a.md").write_text(
        (
            "---\nTitle: A\nCreated: 2026-05-28\n"
            "Processed: false\ntags:\n  - source\n---\n\n# A\n"
        ),
        encoding="utf-8",
    )
    (vault / "_templates" / "concept-note.md").write_text(
        "# {{title}}\n\nCUSTOM MARKER\n",
        encoding="utf-8",
    )

    scaffold = new_note(
        vault,
        "concept",
        "Custom Concept",
        ["Raw/Sources/a.md"],
        allow_incomplete=True,
    )

    text = scaffold.path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "CUSTOM MARKER" in text


def test_template_path_cannot_escape_templates(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=False)

    with pytest.raises(UsageError):
        template_path(vault, "../AGENTS")
