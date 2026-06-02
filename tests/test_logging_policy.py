from __future__ import annotations

from wikimason.config import LoggingConfig, LogRotationConfig
from wikimason.log_policy import should_log_event
from wikimason.logs import LogEvent


def _config(**overrides: object) -> LoggingConfig:
    base = LoggingConfig(
        enabled=True,
        path="Wiki/log.md",
        mode="normal",
        min_level="info",
        include_audit_success=False,
        include_metadata=False,
        include_counts="non_clean",
        max_summary_chars=160,
        include_commands=(),
        exclude_commands=(),
        rotation=LogRotationConfig(
            enabled=True,
            strategy="size",
            max_bytes=1_048_576,
            max_files=5,
            archive_dir="Wiki/logs",
        ),
    )
    return LoggingConfig(**{**base.__dict__, **overrides})


def _event(
    command: str,
    *,
    status: str = "clean",
    level: str = "info",
    exit_code: int = 0,
) -> LogEvent:
    return LogEvent(
        action=command,
        title=command,
        command=command,
        status=status,
        level=level,  # type: ignore[arg-type]
        exit_code=exit_code,
    )


def test_normal_mode_skips_clean_audit_event() -> None:
    assert should_log_event(_event("query", status="clean"), _config()) is False


def test_normal_mode_logs_changed_event() -> None:
    assert should_log_event(_event("source.add", status="changed"), _config()) is True


def test_normal_mode_logs_actionable_event_even_when_audit() -> None:
    assert (
        should_log_event(_event("source.delta", status="actionable"), _config()) is True
    )


def test_quiet_mode_logs_only_problem_events() -> None:
    config = _config(mode="quiet")
    assert should_log_event(_event("query", status="clean"), config) is False
    assert should_log_event(_event("source.delta", status="actionable"), config) is True


def test_diagnostic_mode_logs_clean_audit_event() -> None:
    assert should_log_event(_event("query", status="clean"), _config(mode="diagnostic"))


def test_exclude_command_wins_for_automatic_logging() -> None:
    config = _config(exclude_commands=("query",), mode="normal")
    assert should_log_event(_event("query", status="clean"), config) is False


def test_force_bypasses_disabled_logging_for_log_add() -> None:
    config = _config(enabled=False, exclude_commands=("log.add",))
    assert (
        should_log_event(_event("log.add", status="changed"), config, force=True)
        is True
    )
