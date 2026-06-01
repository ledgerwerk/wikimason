from __future__ import annotations

import json
from pathlib import Path

from conftest import _strip_ansi

from wikimason.cli import main
from wikimason.scaffold import init_vault


def test_cli_log_group_help(capsys) -> None:
    assert main(["help", "log"]) == 0

    out = _strip_ansi(capsys.readouterr().out)
    assert "add" in out
    assert "tail" in out
    assert "check" in out


def test_cli_log_add_and_tail_json(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=False)

    assert (
        main(
            [
                "log",
                "add",
                "--vault",
                str(vault),
                "--action",
                "source.add",
                "--title",
                "Added source",
                "--details",
                "Copied new brief.",
                "--path",
                "Raw/brief.md",
                "--format",
                "json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "log.add"
    assert payload["status"] == "changed"
    assert payload["data"]["path"] == "Wiki/log.md"
    assert payload["data"]["paths"] == ["Raw/brief.md"]

    assert main(["log", "tail", "--vault", str(vault), "-n", "1", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "log.tail"
    assert payload["data"]["total"] == 1
    assert payload["data"]["items"][0]["action"] == "source.add"
    assert payload["data"]["items"][0]["command"] == "log.add"
    assert payload["data"]["items"][0]["paths"] == ["Raw/brief.md"]


def test_cli_log_check_json_reports_invalid_log(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=False)
    (vault / "Wiki/log.md").write_text("broken header\n", encoding="utf-8")

    assert main(["log", "check", "--vault", str(vault), "--format", "json"]) == 1

    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "log.check"
    assert payload["ok"] is False
    assert any(
        finding["code"] == "log_header_invalid"
        for finding in payload["data"]["findings"]
    )
