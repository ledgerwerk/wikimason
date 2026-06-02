from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from conftest import write_source

from wikimason.build import build_vault
from wikimason.cli import main
from wikimason.config import load_config_file, write_config_file
from wikimason.logs import parse_log_entries
from wikimason.scaffold import init_vault


def _entries(vault: Path) -> list[dict[str, object]]:
    return parse_log_entries((vault / "Wiki/log.md").read_text(encoding="utf-8"))


def _set_logging(vault: Path, **kwargs: object) -> None:
    config_path = vault / "wikimason.toml"
    config = load_config_file(config_path)
    config = replace(config, logging=replace(config.logging, **kwargs))
    write_config_file(config_path, config, root_value=".")


def test_source_add_writes_log_entry(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=False)
    source_file = tmp_path / "brief.md"
    source_file.write_text("# Brief\n", encoding="utf-8")

    assert (
        main(
            [
                "source",
                "add",
                str(source_file),
                "--vault",
                str(vault),
                "--format",
                "json",
            ]
        )
        == 0
    )

    entry = _entries(vault)[-1]
    assert entry["action"] == "source.add"
    assert entry["command"] == "source.add"
    assert entry["title"] == "Added raw source"


def test_source_scan_without_update_does_not_write_log_entry(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=False)
    write_source(vault, "foo")

    assert main(["source", "scan", "--vault", str(vault), "--format", "json"]) == 0

    assert _entries(vault) == []


def test_query_writes_audit_log_entry(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=True)
    build_vault(vault)

    assert main(["query", "Project", "--vault", str(vault), "--format", "json"]) == 0

    assert _entries(vault) == []


def test_clean_doctor_skipped_by_default(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=True)

    assert main(["doctor", "--vault", str(vault), "--format", "json"]) == 0

    assert _entries(vault) == []


def test_clean_doctor_logged_in_diagnostic_mode(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=True)
    _set_logging(vault, mode="diagnostic")

    assert main(["doctor", "--vault", str(vault), "--format", "json"]) == 0

    entry = _entries(vault)[-1]
    assert entry["action"] == "doctor"
    assert entry["command"] == "doctor"


def test_vault_maintain_writes_log_without_log_option(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=True)
    build_vault(vault)

    assert main(["vault", "maintain", "--vault", str(vault), "--format", "json"]) == 0

    assert _entries(vault) == []


def test_vault_maintain_blocked_path_writes_log_entry(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=False)
    write_source(vault, "uncovered")

    assert main(["vault", "maintain", "--vault", str(vault), "--format", "json"]) == 1

    entry = _entries(vault)[-1]
    assert entry["action"] == "vault.maintain"
    assert entry["status"] == "invalid"
    assert entry["title"] == "Blocked vault maintenance"


def test_logging_disabled_suppresses_automatic_log(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=True)
    _set_logging(vault, enabled=False)

    assert main(["doctor", "--vault", str(vault), "--format", "json"]) == 0

    assert _entries(vault) == []


def test_log_add_still_writes_when_automatic_logging_disabled(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=False)
    _set_logging(vault, enabled=False)

    assert (
        main(
            [
                "log",
                "add",
                "--vault",
                str(vault),
                "--action",
                "manual.test",
                "--title",
                "Manual write",
                "--format",
                "json",
            ]
        )
        == 0
    )

    entry = _entries(vault)[-1]
    assert entry["command"] == "log.add"
    assert entry["action"] == "manual.test"
