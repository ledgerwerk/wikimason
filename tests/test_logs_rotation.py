from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from wikimason.config import load_config_file, write_config_file
from wikimason.logs import LogEvent, append_log_event, check_log, tail_log
from wikimason.scaffold import init_vault


def _event(action: str, title: str) -> LogEvent:
    return LogEvent(
        action=action,
        title=title,
        command=action,
        status="changed",
        timestamp=datetime(2026, 6, 1, 13, 4, 55, tzinfo=timezone.utc),
        summary="x" * 256,
    )


def _configure_small_rotation(vault: Path, *, max_files: int = 2) -> None:
    config_path = vault / "wikimason.toml"
    config = load_config_file(config_path)
    config = replace(
        config,
        logging=replace(
            config.logging,
            rotation=replace(
                config.logging.rotation,
                strategy="size",
                max_bytes=4096,
                max_files=max_files,
                archive_dir="Wiki/logs",
            ),
        ),
    )
    write_config_file(config_path, config, root_value=".")


def test_append_log_event_rotates_when_size_exceeded(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=False)
    _configure_small_rotation(vault)

    for index in range(20):
        append_log_event(vault, _event(f"event.{index}", "Rotating event"))

    assert (vault / "Wiki/logs/log.1.md").exists()


def test_rotation_shifts_existing_archives(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=False)
    _configure_small_rotation(vault, max_files=3)

    for index in range(60):
        append_log_event(vault, _event(f"event.{index}", "Rotating event"))

    assert (vault / "Wiki/logs/log.1.md").exists()
    assert (vault / "Wiki/logs/log.2.md").exists()


def test_rotation_respects_max_files(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=False)
    _configure_small_rotation(vault, max_files=1)

    for index in range(50):
        append_log_event(vault, _event(f"event.{index}", "Rotating event"))

    assert (vault / "Wiki/logs/log.1.md").exists()
    assert not (vault / "Wiki/logs/log.2.md").exists()


def test_log_tail_archives_reads_oldest_to_newest_then_active(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=False)
    _configure_small_rotation(vault, max_files=2)

    for index in range(40):
        append_log_event(vault, _event(f"event.{index}", f"event-{index}"))

    rows = tail_log(vault, limit=200, include_archives=True)
    assert rows
    assert any(row["path"] == "Wiki/log.md" for row in rows)
    assert any(str(row["path"]).startswith("Wiki/logs/") for row in rows)


def test_log_check_archives_reports_path_specific_findings(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=False)
    _configure_small_rotation(vault, max_files=2)
    append_log_event(vault, _event("event.1", "event"))
    (vault / "Wiki/logs").mkdir(parents=True, exist_ok=True)
    (vault / "Wiki/logs/log.2.md").write_text("broken\n", encoding="utf-8")

    result = check_log(vault, include_archives=True)

    assert result["ok"] is False
    assert any(
        finding["path"] == "Wiki/logs/log.2.md" for finding in result["findings"]
    )
