from __future__ import annotations

import json
from pathlib import Path

from conftest import read_json, write_source_rel

from wikimason.cli import main
from wikimason.frontmatter import split_frontmatter
from wikimason.scaffold import init_vault


def test_note_new_preserves_comma_in_source_path(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)
    source_rel = write_source_rel(
        vault,
        (
            "Andrej Karpathy's LLM Wiki Create your own "
            "knowledge base  by Urvil Joshi  Apr, 2026  Medium.md"
        ),
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
                "Comma Source",
                "--source",
                source_rel,
                "--allow-incomplete",
                "--format",
                "json",
            ]
        )
        == 0
    )

    payload = read_json(capsys)
    data, _ = split_frontmatter(
        (vault / "Wiki/Topics/comma-source.md").read_text(encoding="utf-8")
    )

    assert payload["sources"] == [source_rel]
    assert data["sources"] == [source_rel]
    assert data["source_count"] == 1


def test_note_new_resolves_typographic_apostrophe_source_path(
    tmp_path: Path, capsys
) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)
    source_rel = write_source_rel(vault, "Andrej Karpathy’s LLM Wiki Apr, 2026.md")

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
                "Apostrophe Source",
                "--source",
                "Raw/Sources/Andrej Karpathy's LLM Wiki Apr, 2026.md",
                "--allow-incomplete",
                "--format",
                "json",
            ]
        )
        == 0
    )

    payload = read_json(capsys)
    assert payload["sources"] == [source_rel]


def test_note_new_rejects_missing_source(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)

    code = main(
        [
            "note",
            "new",
            "--vault",
            str(vault),
            "--kind",
            "topic",
            "--title",
            "Missing Source",
            "--source",
            "Raw/Sources/missing.md",
            "--allow-incomplete",
        ]
    )

    assert code == 2
    assert (
        "error: source path not found: Raw/Sources/missing.md"
        in capsys.readouterr().out
    )


def test_note_new_rejects_ambiguous_source_match(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)
    write_source_rel(vault, "Quote's.md")
    write_source_rel(vault, "Quote\u2019s.md")

    code = main(
        [
            "note",
            "new",
            "--vault",
            str(vault),
            "--kind",
            "topic",
            "--title",
            "Ambiguous Source",
            "--source",
            "Raw/Sources/Quote‘s.md",
            "--allow-incomplete",
        ]
    )

    assert code == 2
    out = capsys.readouterr().out
    assert "error: ambiguous source path: Raw/Sources/Quote‘s.md." in out
    assert "Raw/Sources/Quote's.md" in out
    assert "Raw/Sources/Quote’s.md" in out


def test_note_new_accepts_json_path_list(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)
    first = write_source_rel(vault, "Article, With Comma.md")
    second = write_source_rel(vault, "Second.md")

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
                "Json Source List",
                "--source",
                json.dumps([first, second]),
                "--allow-incomplete",
                "--format",
                "json",
            ]
        )
        == 0
    )

    payload = read_json(capsys)
    data, _ = split_frontmatter(
        (vault / "Wiki/Topics/json-source-list.md").read_text(encoding="utf-8")
    )
    assert payload["sources"] == [first, second]
    assert data["sources"] == [first, second]
    assert data["source_count"] == 2


def test_note_normalize_fix_resolves_source_to_canonical_path(
    tmp_path: Path, capsys
) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)
    source_rel = write_source_rel(vault, "Andrej Karpathy’s LLM Wiki Apr, 2026.md")
    note_path = vault / "Wiki/Topics/manual-normalize.md"
    note_path.write_text(
        """---
tags:
  - topic
topics: []
status: seed
created: 2026-05-28
updated: 2026-05-28
sources:
  - Raw/Sources/Andrej Karpathy's LLM Wiki Apr, 2026.md
source_count: 1
aliases: []
---

# Test
""",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "note",
                "normalize",
                "Wiki/Topics/manual-normalize.md",
                "--vault",
                str(vault),
                "--fix",
                "--format",
                "json",
            ]
        )
        == 0
    )

    payload = read_json(capsys)
    data, _ = split_frontmatter(note_path.read_text(encoding="utf-8"))
    assert payload["note"]["applied"] is True
    assert data["sources"] == [source_rel]


def test_note_normalize_fix_rejects_missing_source(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)
    note_path = vault / "Wiki/Topics/missing-source.md"
    note_path.write_text(
        """---
tags:
  - topic
topics: []
status: seed
created: 2026-05-28
updated: 2026-05-28
sources:
  - Raw/Sources/missing.md
source_count: 1
aliases: []
---

# Test
""",
        encoding="utf-8",
    )
    original = note_path.read_text(encoding="utf-8")

    code = main(
        [
            "note",
            "normalize",
            "Wiki/Topics/missing-source.md",
            "--vault",
            str(vault),
            "--fix",
        ]
    )

    assert code == 2
    assert note_path.read_text(encoding="utf-8") == original
    assert (
        "error: source path not found: Raw/Sources/missing.md"
        in capsys.readouterr().out
    )


def test_note_new_resolves_literal_unicode_escape_source_path(
    tmp_path: Path, capsys
) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)
    source_rel = write_source_rel(vault, "Agent Harness Engineering \u2013 O'Reilly.md")

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
                "Escaped Source",
                "--source",
                r"Raw/Sources/Agent Harness Engineering \u2013 O'Reilly.md",
                "--allow-incomplete",
                "--format",
                "json",
            ]
        )
        == 0
    )

    payload = read_json(capsys)
    assert payload["sources"] == [source_rel]
