from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import read_json, write_source
from wikimason.cli import main
from wikimason.command_registry import COMMAND_REGISTRY
from wikimason.links import backlinks, deadend_notes, orphan_notes, unresolved_links
from wikimason.scaffold import init_vault
from wikimason.search_backends import (
    CatalogBackend,
    CommandBackend,
    FileNameBackend,
    PathBackend,
    SourceBackend,
)


def run_cli(vault: Path, *argv: str) -> int:
    return main(["--vault", str(vault), *argv])


def test_link_inventory_functions_characterize_core_behavior(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "a.md").write_text("# A\n\n[[b]]\n[[Missing]]\n", encoding="utf-8")
    (vault / "b.md").write_text("# B\n", encoding="utf-8")
    (vault / "c.md").write_text("# C\n", encoding="utf-8")

    assert backlinks(vault, "b") == ["a.md"]
    assert unresolved_links(vault) == ["Missing"]
    assert orphan_notes(vault) == ["a", "c"]
    assert deadend_notes(vault) == ["b.md", "c.md"]


def test_links_unresolved_cli_json_shape(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)
    bad = vault / "Wiki/Topics/bad-link.md"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("# Bad\n\n[[DefinitelyMissing]]\n", encoding="utf-8")

    assert run_cli(vault, "links", "unresolved", "--format", "json") == 0
    payload = read_json(capsys)
    assert isinstance(payload, list)
    assert "DefinitelyMissing" in payload


def test_catalog_backend_tolerates_blank_lines_and_fails_on_malformed_json(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    (vault / "Wiki").mkdir(parents=True)
    catalog = vault / "Wiki/catalog.jsonl"
    catalog.write_text(
        '{"path": "Wiki/Topics/demo.md", "title": "Demo"}\n\n',
        encoding="utf-8",
    )

    backend = CatalogBackend(vault)
    rows = backend.candidates("demo")
    assert len(rows) == 1
    assert rows[0].path == "Wiki/Topics/demo.md"

    catalog.write_text("{not-json}\n", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        backend.candidates("demo")


def test_source_path_and_filename_backends_are_deterministic(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)

    write_source(vault, "zeta-source")
    write_source(vault, "alpha-source")
    (vault / "Wiki/Topics/z-last.md").write_text("# Z\n", encoding="utf-8")
    (vault / "Wiki/Topics/a-first.md").write_text("# A\n", encoding="utf-8")

    source_rows = SourceBackend(vault).candidates("", limit=50)
    source_keys = [row.key for row in source_rows]
    assert source_keys == sorted(source_keys)
    assert all("stem" in row.fields and "name" in row.fields for row in source_rows)

    path_rows = PathBackend(vault).candidates("", limit=200)
    path_keys = [row.key for row in path_rows]
    assert path_keys == sorted(path_keys)

    name_rows = FileNameBackend(vault).candidates("", limit=200)
    name_keys = [row.key for row in name_rows]
    assert name_keys == sorted(name_keys)


def test_command_backend_excludes_legacy_aliases() -> None:
    expected = [" ".join(info.path) for info in COMMAND_REGISTRY if not info.legacy_aliases]
    actual = [row.key for row in CommandBackend().candidates("", limit=500)]
    assert actual == expected[:500]


def test_query_cli_json_shape(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=True)

    assert run_cli(vault, "query", "welcome", "--format", "json") == 0
    payload = read_json(capsys)
    assert isinstance(payload, list)
    assert payload
    assert "path" in payload[0]
    assert "title" in payload[0]
