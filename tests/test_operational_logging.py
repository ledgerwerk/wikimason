from __future__ import annotations

from pathlib import Path

from conftest import write_source

from wikimason.build import build_vault
from wikimason.cli import main
from wikimason.logs import parse_log_entries
from wikimason.scaffold import init_vault


def _entries(vault: Path) -> list[dict[str, object]]:
    return parse_log_entries((vault / "Wiki/log.md").read_text(encoding="utf-8"))


def test_source_add_writes_log_entry(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=False)
    source_file = tmp_path / "brief.md"
    source_file.write_text("# Brief\n", encoding="utf-8")

    assert (
        main(["source", "add", str(source_file), "--vault", str(vault), "--format", "json"])
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

    entry = _entries(vault)[-1]
    assert entry["action"] == "query"
    assert entry["command"] == "query"
    assert entry["title"] == "Searched catalog"


def test_vault_maintain_writes_log_without_log_option(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=True)
    build_vault(vault)

    assert main(["vault", "maintain", "--vault", str(vault), "--format", "json"]) == 0

    entry = _entries(vault)[-1]
    assert entry["action"] == "vault.maintain"
    assert entry["command"] == "vault.maintain"
    assert entry["title"] == "Ran vault maintenance"


def test_vault_maintain_blocked_path_writes_log_entry(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=False)
    write_source(vault, "uncovered")

    assert main(["vault", "maintain", "--vault", str(vault), "--format", "json"]) == 1

    entry = _entries(vault)[-1]
    assert entry["action"] == "vault.maintain"
    assert entry["status"] == "invalid"
    assert entry["title"] == "Blocked vault maintenance"
