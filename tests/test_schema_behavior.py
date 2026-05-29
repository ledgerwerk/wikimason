from __future__ import annotations

import json
from pathlib import Path

from wikimason.build import build_vault
from wikimason.cli import main
from wikimason.scaffold import init_vault
from wikimason.schema import default_schema, schema_to_dict


def _write_source(vault: Path, name: str = "a") -> None:
    (vault / "Raw/Sources" / f"{name}.md").write_text(
        (
            '---\nTitle: A\nAuthor: ""\nReference: ""\n'
            "ContentType:\n  - note\n"
            "Created: 2026-05-28\nProcessed: false\n"
            "tags:\n  - source\n---\n\n# A\n"
        ),
        encoding="utf-8",
    )


def test_schema_allows_custom_status_from_toml(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)
    _write_source(vault)
    config_path = vault / "wikimason.toml"
    config_text = config_path.read_text(encoding="utf-8")
    config_path.write_text(
        config_text.replace(
            (
                'allowed = ["seed", "active", '
                '"canonical", "stale", "needs_review", '
                '"draft", "stable", "deprecated"]'
            ),
            (
                'allowed = ["seed", "active", '
                '"canonical", "stale", "needs_review", '
                '"draft", "stable", "deprecated", "researching"]'
            ),
        ),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "note",
                "new",
                "--vault",
                str(vault),
                "--kind",
                "topic",
                "--title",
                "Research Topic",
                "--source",
                "Raw/Sources/a.md",
                "--allow-incomplete",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "note",
                "new",
                "--vault",
                str(vault),
                "--kind",
                "concept",
                "--title",
                "Research Note",
                "--source",
                "Raw/Sources/a.md",
                "--status",
                "researching",
                "--related",
                "Wiki/Topics/research-topic.md",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "note",
                "validate",
                "Wiki/Concepts/research-note.md",
                "--vault",
                str(vault),
            ]
        )
        == 0
    )


def test_schema_custom_kind_creates_in_configured_folder_from_toml(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)
    _write_source(vault)
    config_path = vault / "wikimason.toml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8")
        + """

[schema.note_kinds.decision]
folder = "Wiki/Decisions"
tag = "decision"
template = "decision-note.md"
detail_heading = "Decision"
required_sections = ["Decision", "Related", "Sources"]
""",
        encoding="utf-8",
    )
    (vault / "_templates/decision-note.md").write_text(
        "---\n"
        "tags:\n"
        "  - decision\n"
        "topics: {{topics_yaml}}\n"
        "status: {{status}}\n"
        "created: {{date}}\n"
        "updated: {{date}}\n"
        "sources: {{sources_yaml}}\n"
        "source_count: {{source_count}}\n"
        "aliases: {{aliases_yaml}}\n"
        "---\n\n"
        "# {{title}}\n\n"
        "## Decision\n\n"
        "-\n\n"
        "## Related\n\n"
        "-\n\n"
        "## Sources\n\n"
        "{{sources_links}}\n",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "note",
                "new",
                "--vault",
                str(vault),
                "--kind",
                "decision",
                "--title",
                "Adopt Schema",
                "--source",
                "Raw/Sources/a.md",
                "--allow-incomplete",
            ]
        )
        == 0
    )

    target = vault / "Wiki/Decisions/adopt-schema.md"
    assert target.exists()
    assert main(["vault", "lint", "--vault", str(vault)]) == 0

    build_vault(vault)

    assert "Adopt Schema" in (vault / "Wiki/Decisions/index.md").read_text(
        encoding="utf-8"
    )
    assert "Wiki/Decisions/adopt-schema.md" in (vault / "Wiki/catalog.jsonl").read_text(
        encoding="utf-8"
    )


def test_legacy_schema_json_is_still_loaded_without_toml(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)
    _write_source(vault)
    (vault / "wikimason.toml").unlink()
    schema = schema_to_dict(default_schema())
    assert isinstance(schema["statuses"], dict)
    schema["statuses"]["allowed"].append("researching")
    (vault / "Schema/wikimason.json").write_text(
        json.dumps(schema),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "note",
                "new",
                "--vault",
                str(vault),
                "--kind",
                "topic",
                "--title",
                "Legacy Research Topic",
                "--source",
                "Raw/Sources/a.md",
                "--allow-incomplete",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "note",
                "new",
                "--vault",
                str(vault),
                "--kind",
                "concept",
                "--title",
                "Legacy Research Note",
                "--source",
                "Raw/Sources/a.md",
                "--status",
                "researching",
                "--related",
                "Wiki/Topics/legacy-research-topic.md",
            ]
        )
        == 0
    )
