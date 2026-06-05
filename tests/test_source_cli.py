from __future__ import annotations

import json
from pathlib import Path

from wikimason.cli import main
from wikimason.scaffold import init_vault


def test_source_cli_commands(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=True)
    assert (
        main(["source", "scan", "--vault", str(vault), "--update", "--accept-covered"])
        == 0
    )
    assert main(["source", "lint", "--vault", str(vault)]) == 0
    assert main(["source", "delta", "--vault", str(vault)]) == 0
    assert main(["source", "coverage", "--vault", str(vault), "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert "covered" in payload["data"]
    assert "total" in payload["data"]


def test_source_delta_json_output(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=True)
    main(["source", "scan", "--vault", str(vault), "--update", "--accept-covered"])
    # Default compact output
    code = main(["source", "delta", "--vault", str(vault), "--format", "json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert "actionable_count" in payload["data"]
    assert "counts" in payload["data"]
    # --details includes full delta records
    code = main(
        ["source", "delta", "--vault", str(vault), "--details", "--format", "json"]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert "delta" in payload["data"]
    assert "actionable_count" in payload["data"]


def test_removed_legacy_source_commands_are_invalid(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=True)

    assert main(["source-scan", "--vault", str(vault)]) == 2
    assert main(["source-delta", "--vault", str(vault)]) == 2
    assert main(["source-coverage", "--vault", str(vault)]) == 2


def test_removed_legacy_build_command_is_invalid(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=True)

    assert main(["build", "--vault", str(vault)]) == 2


def test_removed_migration_commands_are_invalid(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=True)

    assert main(["source", "migrate-frontmatter", "--vault", str(vault)]) == 2
    assert main(["config", "migrate", str(vault)]) == 2
    assert (
        main(
            [
                "migrate",
                "logseq-to-obsidian",
                "--from",
                str(vault),
                "--to",
                str(vault / "other"),
            ]
        )
        == 2
    )


def test_source_resolve_json_output(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)
    name = (
        "Andrej Karpathy's LLM Wiki Create your own "
        "knowledge base  by Urvil Joshi  Apr, 2026  Medium.md"
    )
    target = vault / "Raw/Sources" / name
    target.write_text("---\nTitle: Test\n---\n\n# Test\n", encoding="utf-8")

    assert (
        main(
            [
                "source",
                "resolve",
                "Andrej Karpathy's LLM Wiki Apr, 2026",
                "--vault",
                str(vault),
                "--format",
                "json",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out.splitlines()[-1])
    data = payload["data"]
    assert data["matches"][0]["path"] == f"Raw/Sources/{name}"
    assert data["matches"][0]["match"] in {"exact", "substring", "fuzzy"}


def test_source_read_resolves_typographic_path(tmp_path: Path, capsys) -> None:
    from conftest import write_source_rel

    vault = tmp_path / "vault"
    init_vault(vault)
    source_rel = write_source_rel(vault, "Agent Harness Engineering \u2013 O'Reilly.md")

    assert (
        main(
            [
                "source",
                "read",
                "Agent Harness Engineering O'Reilly",
                "--vault",
                str(vault),
                "--lines",
                "5",
                "--format",
                "json",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out.splitlines()[-1])
    data = payload["data"]
    assert data["path"] == source_rel
    assert data["content"]


def test_source_read_returns_ambiguous_without_first(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)
    (vault / "Raw/Sources/semantic-contracts.md").write_text("# A", encoding="utf-8")
    (vault / "Raw/Sources/semantic-contracts-v2.md").write_text("# B", encoding="utf-8")

    code = main(
        [
            "source",
            "read",
            "semantic contracts",
            "--vault",
            str(vault),
            "--format",
            "json",
        ]
    )
    assert code == 1
    payload = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert payload["status"] == "ambiguous"
    assert payload["data"]["matches"]


def test_source_delta_report_mode_exits_zero_when_actionable(
    tmp_path: Path, capsys
) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)
    (vault / "Raw/Sources/new.md").write_text("# New", encoding="utf-8")

    code = main(["source", "delta", "--vault", str(vault), "--format", "json"])
    assert code == 0

    payload = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert payload["status"] == "actionable"
    assert payload["data"]["actionable_count"] > 0


def test_source_delta_check_mode_exits_two_when_actionable(
    tmp_path: Path, capsys
) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)
    (vault / "Raw/Sources/new.md").write_text("# New", encoding="utf-8")

    code = main(
        ["source", "delta", "--check", "--vault", str(vault), "--format", "json"]
    )
    assert code == 2

    payload = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert payload["status"] == "actionable"
    assert payload["data"]["actionable_count"] > 0


def test_source_read_truncates_by_default_and_reports_metadata(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)
    body = "\n".join(f"line {i}" for i in range(300))
    target = vault / "Raw/Sources/long.md"
    target.write_text(f"---\nTitle: Long\n---\n\n{body}\n", encoding="utf-8")

    assert main(["source", "read", "Raw/Sources/long.md", "--vault", str(vault), "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out.splitlines()[-1])
    data = payload["data"]

    assert data["total_lines"] == 301
    assert data["returned_lines"] == 160
    assert data["truncated"] is True


def test_source_read_all_returns_full_content(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)
    body = "\n".join(f"line {i}" for i in range(300))
    target = vault / "Raw/Sources/long.md"
    target.write_text(f"---\nTitle: Long\n---\n\n{body}\n", encoding="utf-8")

    assert main([
        "source", "read", "Raw/Sources/long.md", "--all",
        "--vault", str(vault), "--format", "json",
    ]) == 0
    payload = json.loads(capsys.readouterr().out.splitlines()[-1])
    data = payload["data"]

    assert data["returned_lines"] == 301
    assert data["truncated"] is False
