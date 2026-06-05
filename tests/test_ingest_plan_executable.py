"""Test that ingest plan commands are executable against the installed CLI."""

from __future__ import annotations

import shlex
from pathlib import Path

from conftest import read_json, write_source

from wikimason.cli import main
from wikimason.scaffold import init_vault


def test_ingest_plan_commands_are_executable(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)
    write_source(vault, "foo")

    assert (
        main(
            [
                "ingest",
                "plan",
                "Raw/Sources/foo.md",
                "--vault",
                str(vault),
                "--format",
                "json",
            ]
        )
        == 0
    )

    payload = read_json(capsys)
    data = payload["data"]
    assert data["commands"]

    for command in data["commands"]:
        argv = shlex.split(command.removeprefix("wikimason "))
        assert main([*argv, "--vault", str(vault)]) == 0


def test_ingest_plan_recommended_notes_have_argv(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)
    write_source(vault, "foo")

    assert (
        main(
            [
                "ingest",
                "plan",
                "Raw/Sources/foo.md",
                "--vault",
                str(vault),
                "--format",
                "json",
            ]
        )
        == 0
    )

    payload = read_json(capsys)
    data = payload["data"]

    for note in data["recommended_notes"]:
        assert "command" in note, f"Missing 'command' in recommended_note: {note}"
        assert "argv" in note["command"], f"Missing 'argv' in command: {note}"
        argv = note["command"]["argv"]
        assert isinstance(argv, list)
        assert argv[0] == "note"
        assert argv[1] == "new"

        # Execute the argv to verify it's runnable.
        assert main([*argv, "--vault", str(vault)]) == 0


def test_ingest_plan_validation_has_argv(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)
    write_source(vault, "foo")

    assert (
        main(
            [
                "ingest",
                "plan",
                "Raw/Sources/foo.md",
                "--vault",
                str(vault),
                "--format",
                "json",
            ]
        )
        == 0
    )

    payload = read_json(capsys)
    data = payload["data"]
    assert "validation" in data
    assert "argv" in data["validation"]
    assert data["validation"]["argv"][0] == "vault"


def test_ingest_finish_json_compact_by_default(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)
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
                "--format",
                "json",
            ]
        )
        == 0
    )

    assert (
        main(
            [
                "ingest",
                "finish",
                "--accept-covered",
                "--vault",
                str(vault),
                "--format",
                "json",
            ]
        )
        == 0
    )
    payload = read_json(capsys)

    assert "records" not in payload["data"]["coverage"]


def test_ingest_finish_details_includes_coverage_records(
    tmp_path: Path, capsys
) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)
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
                "--format",
                "json",
            ]
        )
        == 0
    )

    assert (
        main(
            [
                "ingest",
                "finish",
                "--accept-covered",
                "--details",
                "--vault",
                str(vault),
                "--format",
                "json",
            ]
        )
        == 0
    )
    payload = read_json(capsys)

    assert "records" in payload["data"]["coverage"]


def test_ingest_plan_groups_related_sources(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)
    write_source(vault, "Vim Grammar", title="Vim Grammar")
    write_source(vault, "mastering-vim-grammar", title="Mastering Vim grammar")

    assert (
        main(["source", "scan", "--update", "--vault", str(vault), "--format", "json"])
        == 0
    )
    assert main(["ingest", "plan", "--vault", str(vault), "--format", "json"]) == 0
    payload = read_json(capsys)
    data = payload["data"]

    assert "sources" in data or "groups" in data
