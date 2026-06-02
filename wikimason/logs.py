from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from .config import (
    LoggingConfig,
    LogRotationConfig,
    WikiMasonConfig,
    load_runtime_config,
)
from .log_policy import NON_CLEAN_STATUSES, should_log_event
from .paths import rel_to_vault

DEFAULT_LOG_PATH = "Wiki/log.md"
LOG_HEADER = "# Wiki Log\n\n"
LOG_HEADING_RE = re.compile(
    r"^## \[(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)\] "
    r"(?P<action>[a-z0-9_.-]+) \| (?P<title>.+)$"
)
ARCHIVE_NAME_RE = re.compile(r"^log\.(\d+)\.md$")
MAX_SCALAR_LENGTH = 240
MAX_ENTRY_BODY_BYTES = 8 * 1024
ALLOWED_STATUSES = {
    "clean",
    "changed",
    "invalid",
    "error",
    "actionable",
    "not_found",
    "ambiguous",
    "skipped",
    "degraded",
    "warning",
}

LogLevel = Literal["info", "warning", "error"]


@dataclass(frozen=True)
class LogEvent:
    action: str
    title: str
    command: str
    status: str = "clean"
    exit_code: int = 0
    level: LogLevel = "info"
    summary: str = ""
    paths: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    counts: dict[str, int | float | str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime | None = None


def _default_logging() -> LoggingConfig:
    return LoggingConfig(
        enabled=True,
        path=DEFAULT_LOG_PATH,
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


def _logging_config(vault: Path, config: WikiMasonConfig | None) -> LoggingConfig:
    if config is not None:
        return config.logging
    return load_runtime_config(vault).logging


def log_path(vault: Path, logging: LoggingConfig | None = None) -> Path:
    active = logging or _default_logging()
    return vault / active.path


def ensure_log_file(vault: Path, logging: LoggingConfig | None = None) -> Path:
    target = log_path(vault, logging)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_text(LOG_HEADER, encoding="utf-8", newline="\n")
    return target


def _format_timestamp(timestamp: datetime | None) -> str:
    value = timestamp or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return (
        value.astimezone(timezone.utc)
        .replace(microsecond=0)
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )


def _sanitize_scalar(value: Any) -> str:
    text = str(value).replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n")
    if len(text) <= MAX_SCALAR_LENGTH:
        return text
    return text[: MAX_SCALAR_LENGTH - 3].rstrip() + "..."


def _render_kv_pairs(values: dict[str, Any], *, omit_empty: bool = False) -> str:
    parts: list[str] = []
    for key, value in values.items():
        if omit_empty and value in {None, ""}:
            continue
        parts.append(f"{key}={_sanitize_scalar(value)}")
    return " ".join(parts)


def _render_log_event_diagnostic(event: LogEvent) -> str:
    lines = [
        f"## [{_format_timestamp(event.timestamp)}] {event.action} | "
        f"{_sanitize_scalar(event.title)}",
        "",
        f"- status: {_sanitize_scalar(event.status)}",
        f"- command: {_sanitize_scalar(event.command)}",
        f"- exit_code: {event.exit_code}",
        f"- level: {_sanitize_scalar(event.level)}",
    ]
    if event.paths:
        lines.append(
            "- paths: " + ", ".join(_sanitize_scalar(path) for path in event.paths)
        )
    if event.sources:
        lines.append(
            "- sources: "
            + ", ".join(_sanitize_scalar(source) for source in event.sources)
        )
    if event.summary.strip():
        lines.append(f"- summary: {_sanitize_scalar(event.summary.strip())}")
    if event.counts:
        lines.append(f"- counts: {_render_kv_pairs(event.counts)}")
    if event.metadata:
        lines.append(f"- metadata: {_render_kv_pairs(event.metadata)}")
    return "\n".join(lines)


def _should_include_counts(event: LogEvent, logging: LoggingConfig) -> bool:
    if not event.counts:
        return False
    if logging.include_counts == "always":
        return True
    if logging.include_counts == "non_clean":
        return event.status in NON_CLEAN_STATUSES
    return False


def _render_log_event_compact(event: LogEvent, logging: LoggingConfig) -> str:
    lines = [
        f"## [{_format_timestamp(event.timestamp)}] {event.action} | "
        f"{_sanitize_scalar(event.title)}",
        "",
        f"- status: {_sanitize_scalar(event.status)}",
        f"- command: {_sanitize_scalar(event.command)}",
    ]
    if event.exit_code != 0:
        lines.append(f"- exit_code: {event.exit_code}")
    if event.level in {"warning", "error"}:
        lines.append(f"- level: {_sanitize_scalar(event.level)}")
    if event.paths:
        lines.append(
            "- paths: " + ", ".join(_sanitize_scalar(path) for path in event.paths)
        )
    if event.sources:
        lines.append(
            "- sources: "
            + ", ".join(_sanitize_scalar(source) for source in event.sources)
        )
    summary = event.summary.strip()
    if summary:
        lines.append(
            f"- summary: {_sanitize_scalar(summary[: logging.max_summary_chars])}"
        )
    if _should_include_counts(event, logging):
        lines.append(f"- counts: {_render_kv_pairs(event.counts)}")
    if event.metadata and (logging.include_metadata or logging.mode == "diagnostic"):
        metadata = _render_kv_pairs(event.metadata, omit_empty=True)
        if metadata:
            lines.append(f"- metadata: {metadata}")
    return "\n".join(lines)


def render_log_event(event: LogEvent, *, config: LoggingConfig | None = None) -> str:
    mode = config.mode if config is not None else "diagnostic"
    if mode == "diagnostic":
        return _render_log_event_diagnostic(event)
    return _render_log_event_compact(event, config)


def _separator_for_append(target: Path) -> str:
    size = target.stat().st_size
    if size == 0:
        return ""
    with target.open("rb") as fh:
        fh.seek(max(0, size - 2))
        tail = fh.read().decode("utf-8", errors="ignore")
    if tail.endswith("\n\n"):
        return ""
    if tail.endswith("\n"):
        return "\n"
    return "\n\n"


def archived_log_paths(vault: Path, logging: LoggingConfig) -> list[Path]:
    archive_dir = vault / logging.rotation.archive_dir
    if not archive_dir.exists():
        return []
    numbered: list[tuple[int, Path]] = []
    for path in archive_dir.glob("log.*.md"):
        match = ARCHIVE_NAME_RE.match(path.name)
        if match is None:
            continue
        numbered.append((int(match.group(1)), path))
    numbered.sort(reverse=True)
    return [path for _, path in numbered]


def _rotate_log_now(vault: Path, logging: LoggingConfig) -> bool:
    target = log_path(vault, logging)
    if not target.exists():
        return False
    archive_dir = vault / logging.rotation.archive_dir
    archive_dir.mkdir(parents=True, exist_ok=True)
    max_files = logging.rotation.max_files
    if max_files > 0:
        oldest = archive_dir / f"log.{max_files}.md"
        if oldest.exists():
            oldest.unlink()
        for idx in range(max_files - 1, 0, -1):
            src = archive_dir / f"log.{idx}.md"
            if src.exists():
                src.rename(archive_dir / f"log.{idx + 1}.md")
        target.rename(archive_dir / "log.1.md")
    else:
        target.unlink()
    ensure_log_file(vault, logging)
    return True


def rotate_log_if_needed(
    vault: Path,
    target: Path,
    rotation: LogRotationConfig,
    *,
    pending_bytes: int,
    active_path: str = DEFAULT_LOG_PATH,
) -> bool:
    if not rotation.enabled or rotation.strategy == "none":
        return False
    if not target.exists():
        return False
    if target.stat().st_size + pending_bytes <= rotation.max_bytes:
        return False
    logging = _default_logging()
    logging = LoggingConfig(
        **{
            **logging.as_dict(),
            "path": active_path,
            "rotation": rotation,
        }
    )
    return _rotate_log_now(vault, logging)


def rotate_log(
    vault: Path,
    *,
    config: WikiMasonConfig | None = None,
    force: bool = False,
) -> dict[str, Any]:
    logging = _logging_config(vault, config)
    target = ensure_log_file(vault, logging)
    rotated = _rotate_log_now(vault, logging) if force else False
    archives = archived_log_paths(vault, logging)
    return {
        "rotated": rotated,
        "path": rel_to_vault(vault, target),
        "archive_count": len(archives),
    }


def append_log_event(
    vault: Path,
    event: LogEvent,
    *,
    config: WikiMasonConfig | None = None,
    force: bool = False,
) -> Path | None:
    logging = _logging_config(vault, config)
    if not should_log_event(event, logging, force=force):
        return None
    target = ensure_log_file(vault, logging)
    block = render_log_event(event, config=logging).rstrip() + "\n"
    rotate_log_if_needed(
        vault,
        target,
        logging.rotation,
        pending_bytes=len(block.encode("utf-8")),
        active_path=logging.path,
    )
    target = ensure_log_file(vault, logging)
    with target.open("a", encoding="utf-8", newline="\n") as fh:
        separator = _separator_for_append(target)
        if separator:
            fh.write(separator)
        fh.write(block)
    return target


def append_log(vault: Path, title: str, details: str) -> Path | None:
    return append_log_event(
        vault,
        LogEvent(
            action="manual",
            command="log.add",
            title=title,
            summary=details.strip(),
        ),
        force=True,
    )


def _parse_key_value_pairs(value: str) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for token in value.split():
        key, sep, token_value = token.partition("=")
        if sep and key:
            pairs[key] = token_value
    return pairs


def _coerce_scalar(value: str) -> int | float | str:
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


def _finalize_entry(entry: dict[str, Any], body_lines: list[str]) -> dict[str, Any]:
    body = "\n".join(body_lines).strip("\n")
    payload = dict(entry)
    payload["body"] = body
    fields: dict[str, Any] = {}
    for line in body_lines:
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        key, sep, value = stripped[2:].partition(":")
        if not sep:
            continue
        field_name = key.strip()
        field_value = value.strip()
        if field_name == "exit_code":
            try:
                fields[field_name] = int(field_value)
            except ValueError:
                fields[field_name] = field_value
        elif field_name in {"paths", "sources"}:
            fields[field_name] = [
                item.strip() for item in field_value.split(",") if item.strip()
            ]
        elif field_name in {"counts", "metadata"}:
            fields[field_name] = {
                key: _coerce_scalar(raw)
                for key, raw in _parse_key_value_pairs(field_value).items()
            }
        else:
            fields[field_name] = field_value
    payload.update(fields)
    return payload


def parse_log_entries(text: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    body_lines: list[str] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        match = LOG_HEADING_RE.match(line)
        if match:
            if current is not None:
                entries.append(_finalize_entry(current, body_lines))
            current = {
                "timestamp": match.group("timestamp"),
                "action": match.group("action"),
                "title": match.group("title"),
                "line": line_number,
            }
            body_lines = []
            continue
        if current is not None:
            body_lines.append(line)
    if current is not None:
        entries.append(_finalize_entry(current, body_lines))
    return entries


def read_log_texts(
    vault: Path,
    logging: LoggingConfig,
    *,
    include_archives: bool,
) -> list[tuple[Path, str]]:
    paths: list[Path] = []
    if include_archives:
        paths.extend(archived_log_paths(vault, logging))
    paths.append(ensure_log_file(vault, logging))
    rows: list[tuple[Path, str]] = []
    for path in paths:
        rows.append((path, path.read_text(encoding="utf-8")))
    return rows


def tail_log(
    vault: Path,
    limit: int = 20,
    action: str | None = None,
    command: str | None = None,
    *,
    include_archives: bool = False,
    config: WikiMasonConfig | None = None,
) -> list[dict[str, Any]]:
    logging = _logging_config(vault, config)
    combined: list[dict[str, Any]] = []
    for path, text in read_log_texts(vault, logging, include_archives=include_archives):
        rel_path = rel_to_vault(vault, path)
        for entry in parse_log_entries(text):
            entry_with_path = dict(entry)
            entry_with_path["path"] = rel_path
            combined.append(entry_with_path)
    if action is not None:
        combined = [entry for entry in combined if entry["action"] == action]
    if command is not None:
        combined = [entry for entry in combined if entry.get("command") == command]
    if limit <= 0:
        return []
    return combined[-limit:]


def _finding(
    *,
    path: str,
    line: int,
    code: str,
    message: str,
    suggestion: str,
    severity: str = "error",
) -> dict[str, Any]:
    return {
        "path": path,
        "line": line,
        "code": code,
        "message": message,
        "suggestion": suggestion,
        "severity": severity,
    }


def _parse_timestamp(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None


def _check_log_text(
    vault: Path,
    path: Path,
    text: str,
    *,
    strict: bool,
) -> tuple[list[dict[str, Any]], int]:
    findings: list[dict[str, Any]] = []
    rel_path = rel_to_vault(vault, path)
    non_empty = [
        (index, line.strip())
        for index, line in enumerate(text.splitlines(), 1)
        if line.strip()
    ]
    if non_empty and non_empty[0][1] != "# Wiki Log":
        findings.append(
            _finding(
                path=rel_path,
                line=non_empty[0][0],
                code="log_header_invalid",
                message="first non-empty line must be # Wiki Log",
                suggestion="Restore the standard log header.",
            )
        )
    lines = text.splitlines()
    entries = parse_log_entries(text)
    entry_by_line = {int(entry["line"]): entry for entry in entries}
    for line_number, line in enumerate(lines, start=1):
        if line.startswith("## ") and line_number not in entry_by_line:
            findings.append(
                _finding(
                    path=rel_path,
                    line=line_number,
                    code="log_heading_format",
                    message="log entry heading must match ## [timestamp]"
                    " action | title",
                    suggestion="Use wikimason log add or rerender this entry.",
                )
            )
    previous_timestamp: datetime | None = None
    for entry in entries:
        line_number = int(entry["line"])
        timestamp = _parse_timestamp(str(entry["timestamp"]))
        if timestamp is None:
            findings.append(
                _finding(
                    path=rel_path,
                    line=line_number,
                    code="log_timestamp_invalid",
                    message=(
                        "timestamp must be a valid UTC ISO timestamp with "
                        "second precision"
                    ),
                    suggestion="Use UTC timestamps like 2026-06-01T13:04:55Z.",
                )
            )
        elif previous_timestamp is not None and timestamp < previous_timestamp:
            findings.append(
                _finding(
                    path=rel_path,
                    line=line_number,
                    code="log_timestamp_order",
                    message="log entry timestamps should be monotonic non-decreasing",
                    suggestion="Reorder entries so timestamps do not go backwards.",
                    severity="error" if strict else "warning",
                )
            )
        if timestamp is not None:
            previous_timestamp = timestamp
        if "status" not in entry:
            findings.append(
                _finding(
                    path=rel_path,
                    line=line_number,
                    code="log_missing_status",
                    message="log entry must include a - status: bullet",
                    suggestion="Add a status bullet such as clean or changed.",
                )
            )
        elif str(entry["status"]) not in ALLOWED_STATUSES:
            findings.append(
                _finding(
                    path=rel_path,
                    line=line_number,
                    code="log_status_invalid",
                    message="log status must be one of the known operational statuses",
                    suggestion="Use a known status such as clean, changed, invalid, or actionable.",  # noqa: E501
                )
            )
        if "command" not in entry:
            findings.append(
                _finding(
                    path=rel_path,
                    line=line_number,
                    code="log_missing_command",
                    message="log entry must include a - command: bullet",
                    suggestion="Add the CLI command identity to the log entry.",
                )
            )
        if len(str(entry.get("body", "")).encode("utf-8")) > MAX_ENTRY_BODY_BYTES:
            findings.append(
                _finding(
                    path=rel_path,
                    line=line_number,
                    code="log_entry_too_large",
                    message="log entry body should stay below 8 KiB",
                    suggestion="Move large details elsewhere and keep"
                    " the entry compact.",
                    severity="warning",
                )
            )
    return findings, len(entries)


def check_log(
    vault: Path,
    strict: bool = False,
    *,
    include_archives: bool = False,
    config: WikiMasonConfig | None = None,
) -> dict[str, Any]:
    logging = _logging_config(vault, config)
    findings: list[dict[str, Any]] = []
    total_entries = 0
    for path, text in read_log_texts(vault, logging, include_archives=include_archives):
        path_findings, entry_count = _check_log_text(vault, path, text, strict=strict)
        findings.extend(path_findings)
        total_entries += entry_count
    ok = not any(finding["severity"] == "error" for finding in findings)
    return {"ok": ok, "entries": total_entries, "findings": findings}


def log_stats(
    vault: Path,
    *,
    include_archives: bool = False,
    config: WikiMasonConfig | None = None,
) -> dict[str, Any]:
    logging = _logging_config(vault, config)
    target = ensure_log_file(vault, logging)
    active_text = target.read_text(encoding="utf-8")
    active_entries = parse_log_entries(active_text)
    archives = archived_log_paths(vault, logging)
    archive_bytes = sum(path.stat().st_size for path in archives)
    archive_entries = 0
    if include_archives:
        for archive in archives:
            archive_entries += len(
                parse_log_entries(archive.read_text(encoding="utf-8"))
            )
    return {
        "path": rel_to_vault(vault, target),
        "active_bytes": target.stat().st_size,
        "active_entries": len(active_entries),
        "archive_count": len(archives),
        "archive_bytes": archive_bytes,
        "archive_entries": archive_entries if include_archives else None,
        "rotation": logging.rotation.as_dict(),
    }
