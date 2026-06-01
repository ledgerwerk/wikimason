from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from wikimason.logs import (
    LOG_HEADING_RE,
    LogEvent,
    append_log_event,
    check_log,
    ensure_log_file,
    parse_log_entries,
    render_log_event,
    tail_log,
)
from wikimason.scaffold import init_vault


def _event(action: str, title: str, *, command: str | None = None) -> LogEvent:
    return LogEvent(
        action=action,
        title=title,
        command=command or action,
        status="changed",
        exit_code=0,
        summary=f"{title} summary",
        timestamp=datetime(2026, 6, 1, 13, 4, 55, tzinfo=timezone.utc),
    )


def test_render_log_event_heading_parseable() -> None:
    rendered = render_log_event(_event("source.add", "Added raw source"))

    first_line = rendered.splitlines()[0]
    match = LOG_HEADING_RE.match(first_line)

    assert match is not None
    assert match.group("action") == "source.add"
    assert match.group("title") == "Added raw source"
    assert "- status: changed" in rendered
    assert "- command: source.add" in rendered


def test_append_log_event_preserves_existing_content(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    log_file = ensure_log_file(vault)
    log_file.write_text("# Custom Log\n\nKeep me.\n", encoding="utf-8")

    append_log_event(vault, _event("query", "Searched catalog"))

    content = log_file.read_text(encoding="utf-8")
    assert "Keep me." in content
    assert "## [2026-06-01T13:04:55Z] query | Searched catalog" in content
    assert "- status: changed" in content


def test_append_log_event_uses_append_shape(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=False)

    append_log_event(vault, _event("source.add", "Added first source"))
    append_log_event(
        vault,
        LogEvent(
            action="query",
            title="Searched catalog",
            command="query",
            status="clean",
            summary="Query: skills",
            timestamp=datetime(2026, 6, 1, 13, 6, 10, tzinfo=timezone.utc),
        ),
    )

    content = (vault / "Wiki/log.md").read_text(encoding="utf-8")
    assert content.startswith("# Wiki Log\n\n## [2026-06-01T13:04:55Z] source.add")
    assert len(re.findall(r"^## \[", content, flags=re.MULTILINE)) == 2


def test_parse_log_entries_returns_recent_entries(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    append_log_event(vault, _event("source.add", "Added first source"))
    append_log_event(
        vault,
        LogEvent(
            action="lint",
            title="Linted compiled pages",
            command="lint",
            status="invalid",
            exit_code=1,
            summary="Lint completed with 3 findings.",
            timestamp=datetime(2026, 6, 1, 13, 8, 22, tzinfo=timezone.utc),
        ),
    )
    append_log_event(
        vault,
        LogEvent(
            action="query",
            title="Searched catalog",
            command="query",
            status="clean",
            summary="Query: agent skills",
            timestamp=datetime(2026, 6, 1, 13, 9, 10, tzinfo=timezone.utc),
        ),
    )

    entries = parse_log_entries((vault / "Wiki/log.md").read_text(encoding="utf-8"))
    recent = tail_log(vault, limit=2)
    lint_only = tail_log(vault, limit=5, command="lint")

    assert [entry["action"] for entry in entries] == ["source.add", "lint", "query"]
    assert [entry["action"] for entry in recent] == ["lint", "query"]
    assert len(lint_only) == 1
    assert lint_only[0]["command"] == "lint"


def test_log_check_flags_bad_heading(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    log_file = ensure_log_file(vault)
    log_file.write_text(
        "# Wiki Log\n\n## bad heading\n\n- status: changed\n- command: source.add\n",
        encoding="utf-8",
    )

    result = check_log(vault)

    assert result["ok"] is False
    assert any(finding["code"] == "log_heading_format" for finding in result["findings"])


def test_log_check_flags_missing_status_or_command(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    log_file = ensure_log_file(vault)
    log_file.write_text(
        "# Wiki Log\n\n## [2026-06-01T13:04:55Z] source.add | Added raw source\n\n- summary: Added raw source to the vault.\n",
        encoding="utf-8",
    )

    result = check_log(vault)
    codes = {finding["code"] for finding in result["findings"]}

    assert {"log_missing_status", "log_missing_command"} <= codes


def test_log_check_allows_initial_header_only(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    ensure_log_file(vault)

    result = check_log(vault)

    assert result == {"ok": True, "entries": 0, "findings": []}
