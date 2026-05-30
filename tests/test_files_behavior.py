from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from wikimason.errors import UsageError
from wikimason.files import (
    append_file,
    delete_file,
    folder_file_count,
    list_files,
    list_folders,
    move_file,
    open_file,
    prepend_file,
    read_template,
    rename_file,
    resolve_existing_path,
    search_files,
    write_file,
)
from wikimason.scaffold import init_vault


def test_list_files_folders_and_counts(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)
    (vault / "notes").mkdir(parents=True, exist_ok=True)
    (vault / "notes/demo.txt").write_text("demo", encoding="utf-8")

    md_rows = list_files(vault, ext="md")
    assert all(row.endswith(".md") for row in md_rows)
    assert "notes/demo.txt" not in md_rows

    folders = list_folders(vault)
    assert "notes" in folders
    assert folder_file_count(vault) >= len(md_rows)


def test_write_file_template_and_overwrite_guards(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)

    created = write_file(
        vault,
        "Wiki/Topics/from-template.md",
        template="topic-note",
        title="From Template",
    )
    assert created.exists()
    rendered = created.read_text(encoding="utf-8")
    assert "From Template" in rendered

    with pytest.raises(UsageError, match="target exists"):
        write_file(vault, "Wiki/Topics/from-template.md", content="again")

    with pytest.raises(UsageError, match="template not found"):
        read_template(vault, "missing-template")


def test_resolve_existing_path_falls_back_to_filename_resolution(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)
    target = vault / "Wiki/Topics/fallback-demo.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# Demo\n", encoding="utf-8")

    resolved = resolve_existing_path(vault, "fallback-demo")
    assert resolved == target


def test_append_inline_and_prepend_without_frontmatter(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)

    path = vault / "Scratch.md"
    path.write_text("alpha", encoding="utf-8")
    append_file(vault, "Scratch.md", "-beta", inline=True)
    assert path.read_text(encoding="utf-8") == "alpha-beta"

    prepend_file(vault, "Scratch.md", "intro")
    assert path.read_text(encoding="utf-8").startswith("intro\nalpha-beta")


def test_move_and_rename_paths(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)

    original = vault / "Wiki/Topics/move-me.md"
    original.parent.mkdir(parents=True, exist_ok=True)
    original.write_text("# move\n", encoding="utf-8")

    moved = move_file(vault, "Wiki/Topics/move-me.md", "Wiki/Topics/moved.md")
    assert moved.name == "moved.md"

    renamed_slug = rename_file(vault, "Wiki/Topics/moved.md", "Readable Title")
    assert renamed_slug.name == "readable-title.md"

    renamed_path = rename_file(
        vault, "Wiki/Topics/readable-title.md", "Wiki/Topics/final.md"
    )
    assert renamed_path.as_posix().endswith("Wiki/Topics/final.md")


def test_open_file_uses_uri_template_and_browser_toggle(
    tmp_path: Path, monkeypatch
) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)
    target = vault / "Wiki/Topics/open-me.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# open\n", encoding="utf-8")

    opened: list[str] = []
    monkeypatch.setenv("WIKIMASON_OPEN_BROWSER", "1")
    monkeypatch.setattr(
        "wikimason.files.webbrowser.open", lambda uri: opened.append(uri)
    )

    config = SimpleNamespace(
        tool_config=SimpleNamespace(open_uri_template="obsidian://open?path={path}")
    )
    uri = open_file(config, target)

    assert uri.startswith("obsidian://open?path=")
    assert opened == [uri]


def test_search_files_context_limit_and_fuzzy_paths(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)

    a = vault / "Wiki/Topics/a.md"
    b = vault / "Wiki/Topics/b.md"
    a.parent.mkdir(parents=True, exist_ok=True)
    a.write_text(
        "Alpha line\nRun wikimason init obsidian before ingest.\n", encoding="utf-8"
    )
    b.write_text("Alpha second\n", encoding="utf-8")

    rows = search_files(vault, "Alpha", limit=1)
    assert len(rows) == 1

    context_rows = search_files(vault, "Alpha", context=True, limit=5)
    assert any(":1:Alpha" in row for row in context_rows)

    fuzzy_rows = search_files(vault, "wikimason init obsdian", fuzzy=True)
    assert "Wiki/Topics/a.md" in fuzzy_rows


def test_delete_file_paths(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)

    file_path = vault / "temp.md"
    file_path.write_text("temp", encoding="utf-8")
    result = delete_file(vault, "temp.md", permanent=False)
    assert result == ".trash/temp.md"
    assert (vault / ".trash/temp.md").exists()

    file_path = vault / "temp2.md"
    file_path.write_text("temp", encoding="utf-8")
    assert delete_file(vault, "temp2.md", permanent=True) == "deleted"
    assert not file_path.exists()
