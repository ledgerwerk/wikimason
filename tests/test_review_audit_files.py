from __future__ import annotations

from pathlib import Path

from conftest import read_json

from wikimason.audit import audit_vault
from wikimason.cli import main
from wikimason.files import delete_file, prepend_file
from wikimason.frontmatter import split_frontmatter
from wikimason.review import (
    ReviewItem,
    add_review_item,
    load_review_queue,
    resolve_review_item,
    review_queue_path,
)
from wikimason.scaffold import init_vault


def run_cli(vault: Path, *argv: str) -> int:
    return main(["--vault", str(vault), *argv])


def test_review_queue_round_trip_ignores_blank_and_malformed_lines(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)

    item = ReviewItem.new(kind="research_gap", title="Need review")
    add_review_item(vault, item)

    queue = review_queue_path(vault)
    queue.write_text(
        queue.read_text(encoding="utf-8") + "\n\n{bad json}\n", encoding="utf-8"
    )

    items = load_review_queue(vault)
    assert [row.review_id for row in items] == [item.review_id]


def test_review_resolve_updates_only_target_item(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)

    first = ReviewItem.new(kind="research_gap", title="First")
    second = ReviewItem.new(kind="research_gap", title="Second")
    add_review_item(vault, first)
    add_review_item(vault, second)

    updated = resolve_review_item(vault, first.review_id, "done")
    assert updated is not None
    assert updated.status == "done"

    status_by_id = {row.review_id: row.status for row in load_review_queue(vault)}
    assert status_by_id[first.review_id] == "done"
    assert status_by_id[second.review_id] == "open"


def test_review_cli_add_show_and_resolve_json(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)

    assert (
        run_cli(
            vault,
            "review",
            "add",
            "--kind",
            "research_gap",
            "--title",
            "Needs judgment",
            "--detail",
            "Check citations",
            "--format",
            "json",
        )
        == 0
    )
    created = read_json(capsys)

    assert (
        run_cli(vault, "review", "show", created["review_id"], "--format", "json") == 0
    )
    shown = read_json(capsys)
    assert shown["review_id"] == created["review_id"]
    assert shown["status"] == "open"

    assert (
        run_cli(
            vault,
            "review",
            "resolve",
            created["review_id"],
            "--status",
            "done",
            "--format",
            "json",
        )
        == 0
    )
    resolved = read_json(capsys)
    assert resolved["status"] == "done"


def test_review_show_missing_returns_exit_1(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)

    assert run_cli(vault, "review", "show", "rev_missing") == 1
    assert "review item not found" in capsys.readouterr().out


def test_audit_vault_flags_workspace_local_paths_and_binary_in_text_area(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / ".obsidian/workspace.json").write_text("{}", encoding="utf-8")
    (vault / "Nested/Wiki").mkdir(parents=True)
    (vault / "Nested/Wiki/manual.pdf").write_bytes(b"%PDF-1.4")
    (vault / "Wiki").mkdir(parents=True)
    (vault / "Wiki/leak.md").write_text(
        "developer home: /Users/alice", encoding="utf-8"
    )

    findings = audit_vault(vault)
    assert any("tracked local obsidian state" in row for row in findings)
    assert any("binary in text area" in row for row in findings)
    assert any("local path leak" in row for row in findings)


def test_audit_cli_json_shape_and_exit_codes(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)

    assert run_cli(vault, "audit", "--format", "json") == 0
    clean_payload = read_json(capsys)
    assert clean_payload["ok"] is True
    assert clean_payload["findings"] == []

    (vault / "Wiki/leak.md").write_text("path C:\\Users\\dev", encoding="utf-8")
    assert run_cli(vault, "audit", "--format", "json") == 1
    dirty_payload = read_json(capsys)
    assert dirty_payload["ok"] is False
    assert dirty_payload["findings"]


def test_prepend_file_preserves_frontmatter_and_updates_body(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)

    note = vault / "Wiki/Topics/demo.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(
        "---\ntitle: Demo\ntags:\n  - sample\n---\nOriginal line\n",
        encoding="utf-8",
    )

    prepend_file(vault, "Wiki/Topics/demo.md", "Prepended")
    data, body = split_frontmatter(note.read_text(encoding="utf-8"))

    assert data["title"] == "Demo"
    assert data["tags"] == ["sample"]
    assert body.lstrip().startswith("Prepended\nOriginal line")


def test_delete_file_moves_to_trash_and_permanent_removes(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)

    first = vault / "Scratch.md"
    first.write_text("scratch", encoding="utf-8")
    result = delete_file(vault, "Scratch.md", permanent=False)
    assert result == ".trash/Scratch.md"
    assert not first.exists()
    assert (vault / ".trash/Scratch.md").exists()

    second = vault / "Scratch2.md"
    second.write_text("scratch", encoding="utf-8")
    permanent_result = delete_file(vault, "Scratch2.md", permanent=True)
    assert permanent_result == "deleted"
    assert not second.exists()
