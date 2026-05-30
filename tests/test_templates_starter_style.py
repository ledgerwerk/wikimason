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


def test_note_new_cli_metadata_overrides_stale_vault_template(tmp_path: Path) -> None:
    """P0 fix: CLI-provided metadata must be authoritative over stale templates."""
    from conftest import write_source_rel

    from wikimason.frontmatter import split_frontmatter

    vault = tmp_path / "vault"
    init_vault(vault)
    source_rel = write_source_rel(vault, "a.md")

    # Write a stale template that hard-codes sources: [], status: active, old dates.
    (vault / "_templates/topic-note.md").write_text(
        "---\n"
        "tags:\n  - topic\n"
        "topics: []\n"
        "status: active\n"
        "created: 2026-05-28\n"
        "updated: 2026-05-28\n"
        "sources: []\n"
        "source_count: 0\n"
        "aliases: []\n"
        "---\n\n"
        "# {{title}}\n\n"
        "## Sources\n\n"
        "{{sources_links}}\n",
        encoding="utf-8",
    )

    scaffold = new_note(
        vault,
        "topic",
        "A",
        [source_rel],
        allow_incomplete=True,
        status="seed",
    )

    data, body = split_frontmatter(scaffold.path.read_text(encoding="utf-8"))
    assert data["sources"] == [source_rel], (
        f"Expected sources=[{source_rel}], got {data['sources']}"
    )
    assert data["source_count"] == 1, (
        f"Expected source_count=1, got {data['source_count']}"
    )
    assert data["status"] == "seed", f"Expected status=seed, got {data['status']}"
    # Dates should be today, not the stale template date.
    assert data["created"] != "2026-05-28", (
        f"Expected fresh date, got {data['created']}"
    )
    assert data["updated"] != "2026-05-28", (
        f"Expected fresh date, got {data['updated']}"
    )
