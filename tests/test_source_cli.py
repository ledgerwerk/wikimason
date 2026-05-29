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
    assert main(["source", "delta", "--vault", str(vault)]) in {0, 2}
    assert main(["source", "coverage", "--vault", str(vault), "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert "covered" in payload
    assert "total" in payload


def test_source_nested_aliases_match_legacy(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=True)

    assert main(["source", "delta", "--vault", str(vault), "--format", "json"]) in {
        0,
        2,
    }
    nested = json.loads(capsys.readouterr().out.splitlines()[-1])

    assert main(["source-delta", "--vault", str(vault), "--format", "json"]) in {0, 2}
    legacy = json.loads(capsys.readouterr().out.splitlines()[-1])

    # Ignore timestamps which differ between runs
    def _strip_ts(obj):
        if isinstance(obj, dict):
            return {
                k: _strip_ts(v)
                for k, v in obj.items()
                if k not in ("last_scanned_at", "first_seen_at")
            }
        if isinstance(obj, list):
            return [_strip_ts(v) for v in obj]
        return obj

    assert _strip_ts(nested) == _strip_ts(legacy)


def test_source_delta_json_output(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=True)
    main(["source-scan", "--vault", str(vault), "--update", "--accept-covered"])
    code = main(["source-delta", "--vault", str(vault), "--format", "json"])
    assert code in {0, 2}
    payload = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert "delta" in payload
    assert "actionable_count" in payload


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
    assert payload["matches"][0]["path"] == f"Raw/Sources/{name}"
    assert payload["matches"][0]["match"] in {"exact", "substring", "fuzzy"}


def test_source_read_resolves_typographic_path(tmp_path: Path, capsys) -> None:
    from conftest import write_source_rel

    vault = tmp_path / "vault"
    init_vault(vault)
    source_rel = write_source_rel(vault, "Agent Harness Engineering \u2013 O'Reilly.md")

    assert main([
        "source",
        "read",
        "Agent Harness Engineering O'Reilly",
        "--vault",
        str(vault),
        "--lines",
        "5",
        "--format",
        "json",
    ]) == 0

    payload = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert payload["path"] == source_rel
    assert payload["content"]


def test_source_delta_exit_2_has_exit_reason(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)
    (vault / "Raw/Sources/new.md").write_text("# New", encoding="utf-8")

    code = main(["source", "delta", "--vault", str(vault), "--format", "json"])
    assert code == 2

    payload = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert payload["actionable_count"] > 0
    assert payload["exit_reason"] == "actionable_source_work"
