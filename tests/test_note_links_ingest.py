from __future__ import annotations

import json
from pathlib import Path

import pytest

from wikimason.build import build_vault
from wikimason.cli import main
from wikimason.scaffold import init_vault


def write_source(vault: Path, name: str, title: str | None = None) -> Path:
    target = vault / "Raw/Sources" / f"{name}.md"
    rendered_title = title or name.replace("-", " ").title()
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


def read_json(capsys):
    return json.loads(capsys.readouterr().out.splitlines()[-1])


@pytest.mark.parametrize("tool", ["obsidian", "markdown"])
def test_note_new_with_source_and_related_lints_clean(
    tmp_path: Path, tool: str
) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, tool=tool)
    write_source(vault, "foo")

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
                "Foo",
                "--source",
                "Raw/Sources/foo.md",
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
                "Foo Concept",
                "--source",
                "Raw/Sources/foo.md",
                "--related",
                "Wiki/Topics/foo.md",
            ]
        )
        == 0
    )

    build_vault(vault)

    assert main(["vault", "lint", "--vault", str(vault)]) == 0


@pytest.mark.parametrize(
    ("tool", "expected"),
    [
        ("obsidian", "[[Wiki/Concepts/compiled-knowledge|Compiled Knowledge]]"),
        ("markdown", "[[Wiki/Concepts/compiled-knowledge|Compiled Knowledge]]"),
    ],
)
def test_links_resolve_uses_catalog_title_and_aliases(
    tmp_path: Path, capsys, tool: str, expected: str
) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=True, tool=tool)
    build_vault(vault)

    assert (
        main(
            [
                "links",
                "resolve",
                "distilled knowledge",
                "--vault",
                str(vault),
                "--format",
                "json",
            ]
        )
        == 0
    )
    alias_payload = read_json(capsys)

    assert alias_payload["matches"][0]["path"] == "Wiki/Concepts/compiled-knowledge.md"

    assert (
        main(
            [
                "links",
                "resolve",
                "Compiled Knowledge",
                "--vault",
                str(vault),
                "--format",
                "json",
            ]
        )
        == 0
    )
    title_payload = read_json(capsys)

    assert title_payload["matches"][0]["wikilink"] == expected


@pytest.mark.parametrize(
    ("tool", "expected"),
    [
        ("obsidian", "[[Wiki/Concepts/compiled-knowledge|Compiled Knowledge]]"),
        ("markdown", "[[Wiki/Concepts/compiled-knowledge|Compiled Knowledge]]"),
    ],
)
def test_links_normalize_fixes_unique_unresolved_body_link(
    tmp_path: Path, tool: str, expected: str
) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=True, tool=tool)
    build_vault(vault)
    target = vault / "Wiki/Topics/wikimason.md"
    target.write_text(
        target.read_text(encoding="utf-8") + "\nSee [[Compiled Knowledge]].\n",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "links",
                "normalize",
                "Wiki/Topics/wikimason.md",
                "--vault",
                str(vault),
                "--fix",
            ]
        )
        == 0
    )

    text = target.read_text(encoding="utf-8")
    assert expected in text


@pytest.mark.parametrize(
    ("tool", "expected"),
    [
        ("obsidian", "[[Wiki/Concepts/compiled-knowledge|Compiled Knowledge]]"),
        ("markdown", "[[Wiki/Concepts/compiled-knowledge|Compiled Knowledge]]"),
    ],
)
def test_lint_json_suggestions(
    tmp_path: Path, capsys, tool: str, expected: str
) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=True, tool=tool)
    build_vault(vault)
    target = vault / "Wiki/Topics/wikimason.md"
    target.write_text(
        target.read_text(encoding="utf-8") + "\nSee [[Compiled Knowledge]].\n",
        encoding="utf-8",
    )

    assert main(["vault", "lint", "--vault", str(vault), "--format", "json"]) == 1

    payload = read_json(capsys)
    finding = next(
        item for item in payload["findings"] if item["code"] == "unresolved_body_link"
    )
    assert finding["suggestion"] == expected


def test_ingest_status_reports_actionable_missing_coverage(
    tmp_path: Path, capsys
) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)
    write_source(vault, "foo")

    assert main(["ingest", "status", "--vault", str(vault), "--format", "json"]) == 0

    payload = read_json(capsys)
    assert payload["next_action"] == "compile_missing_sources"
    assert payload["sources"]["total"] == 1
    assert payload["sources"]["covered"] == 0


def test_ingest_plan_returns_note_targets_for_source(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)
    write_source(vault, "llms-core-setup-v1-0-0", title="LLMs Core Setup")

    assert (
        main(
            [
                "ingest",
                "plan",
                "Raw/Sources/llms-core-setup-v1-0-0.md",
                "--vault",
                str(vault),
                "--format",
                "json",
            ]
        )
        == 0
    )

    payload = read_json(capsys)
    assert payload["source_title"] == "LLMs Core Setup"
    assert (
        payload["recommended_notes"][0]["path_hint"] == "Wiki/Topics/llms-core-setup.md"
    )
    assert payload["recommended_notes"][-1]["path_hint"].startswith("Wiki/Logs/")


def test_ingest_finish_exit_2_when_delta_still_actionable(
    tmp_path: Path, capsys
) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)
    write_source(vault, "foo")
    write_source(vault, "bar")

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
                "Foo",
                "--source",
                "Raw/Sources/foo.md",
                "--allow-incomplete",
            ]
        )
        == 0
    )

    code = main(
        [
            "ingest",
            "finish",
            "--vault",
            str(vault),
            "--accept-covered",
            "--format",
            "json",
        ]
    )

    payload = read_json(capsys)
    assert code == 2
    assert payload["actionable_count"] == 1
    assert payload["coverage"]["total"] == 2
    assert payload["coverage"]["covered"] == 1


def test_source_scan_has_no_weak_sources_for_resolved_path_input(
    tmp_path: Path, capsys
) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)
    name = (
        "Andrej Karpathy's LLM Wiki Create your own "
        "knowledge base  by Urvil Joshi  Apr, 2026  Medium.md"
    )
    (vault / "Raw/Sources" / name).write_text(
        "---\nTitle: Test\n---\n\n# Test\n",
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
                "Path Scenario",
                "--source",
                (
                    "Raw/Sources/Andrej Karpathy's LLM Wiki "
                    "Create your own knowledge base  by Urvil "
                    "Joshi  Apr, 2026  Medium.md"
                ),
                "--allow-incomplete",
            ]
        )
        == 0
    )

    assert (
        main(
            [
                "source",
                "scan",
                "--vault",
                str(vault),
                "--update",
                "--accept-covered",
                "--format",
                "json",
            ]
        )
        == 0
    )

    payload = read_json(capsys)
    assert payload["weak_sources"] == []


def test_first_run_acceptance_scenario(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)
    write_source(vault, "llms-core-setup-v1-0-0", title="LLMs Core Setup")

    notes = [
        ("topic", "LLMs Core Setup", True),
        ("concept", "Compiled Note Layer", False),
        ("concept", "Source Layer", False),
        ("entity", "WikiMason CLI", False),
        ("project", "LLM Wiki Build", False),
        ("log", "Initial LLM Wiki Ingest", False),
    ]
    for kind, title, allow_incomplete in notes:
        argv = [
            "note",
            "new",
            "--vault",
            str(vault),
            "--kind",
            kind,
            "--title",
            title,
            "--source",
            "Raw/Sources/llms-core-setup-v1-0-0.md",
        ]
        if allow_incomplete:
            argv.append("--allow-incomplete")
        else:
            argv.extend(["--related", "Wiki/Topics/llms-core-setup.md"])
        assert main(argv) == 0

    assert main(["links", "check", "--vault", str(vault), "--format", "json"]) == 0
    assert read_json(capsys) == []

    assert (
        main(
            [
                "ingest",
                "finish",
                "--vault",
                str(vault),
                "--accept-covered",
                "--format",
                "json",
            ]
        )
        == 0
    )
    finish_payload = read_json(capsys)
    assert finish_payload["coverage"]["coverage_percent"] == 100.0

    assert main(["source", "lint", "--vault", str(vault)]) == 0
    assert main(["vault", "lint", "--vault", str(vault)]) == 0
    assert main(["vault", "doctor", "--vault", str(vault)]) == 0


def test_links_normalize_fix_normalizes_source_frontmatter(
    tmp_path: Path, capsys
) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)
    from conftest import write_source_rel

    source_rel = write_source_rel(vault, "Agent Skills \u2013 O'Reilly.md")
    note = vault / "Wiki/Topics/agent-skills.md"
    note.write_text(
        """---
tags:
  - topic
topics: []
status: active
created: 2026-05-29
updated: 2026-05-29
sources:
  - Raw/Sources/Agent Skills \\u2013 O'Reilly.md
source_count: 1
aliases: []
---

# Agent Skills

## Related

-

## Sources

- [[Raw/Sources/Agent Skills \\u2013 O'Reilly.md]]
""",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "links",
                "normalize",
                "Wiki/Topics/agent-skills.md",
                "--vault",
                str(vault),
                "--fix",
                "--format",
                "json",
            ]
        )
        == 0
    )

    from wikimason.frontmatter import split_frontmatter

    data, body = split_frontmatter(note.read_text(encoding="utf-8"))
    assert data["sources"] == [source_rel]
    assert source_rel.removesuffix(".md") in body or source_rel in body
