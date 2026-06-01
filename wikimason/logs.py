from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

LOG_PATH = "Wiki/log.md"
LOG_HEADER = "# Wiki Log\n\n"
LOG_HEADING_RE = re.compile(
    r"^## \[(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)\] "
    r"(?P<action>[a-z0-9_.-]+) \| (?P<title>.+)$"
)
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


def log_path(vault: Path) -> Path:
    return vault / LOG_PATH


def ensure_log_file(vault: Path) -> Path:
    target = log_path(vault)
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


def _render_kv_pairs(values: dict[str, Any]) -> str:
    parts = [f"{key}={_sanitize_scalar(value)}" for key, value in values.items()]
    return " ".join(parts)


def render_log_event(event: LogEvent) -> str:
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
        lines.append("- paths: " + ", ".join(_sanitize_scalar(path) for path in event.paths))
    if event.sources:
        lines.append(
            "- sources: " + ", ".join(_sanitize_scalar(source) for source in event.sources)
        )
    if event.summary.strip():
        lines.append(f"- summary: {_sanitize_scalar(event.summary.strip())}")
    if event.counts:
        lines.append(f"- counts: {_render_kv_pairs(event.counts)}")
    if event.metadata:
        lines.append(f"- metadata: {_render_kv_pairs(event.metadata)}")
    return "\n".join(lines)


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


def append_log_event(vault: Path, event: LogEvent) -> Path:
    target = ensure_log_file(vault)
    block = render_log_event(event).rstrip() + "\n"
    with target.open("a", encoding="utf-8", newline="\n") as fh:
        separator = _separator_for_append(target)
        if separator:
            fh.write(separator)
        fh.write(block)
    return target


def append_log(vault: Path, title: str, details: str) -> Path:
    return append_log_event(
        vault,
        LogEvent(
            action="manual",
            command="log.add",
            title=title,
            summary=details.strip(),
        ),
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


def tail_log(
    vault: Path,
    limit: int = 20,
    action: str | None = None,
    command: str | None = None,
) -> list[dict[str, Any]]:
    target = ensure_log_file(vault)
    entries = parse_log_entries(target.read_text(encoding="utf-8"))
    if action is not None:
        entries = [entry for entry in entries if entry["action"] == action]
    if command is not None:
        entries = [entry for entry in entries if entry.get("command") == command]
    if limit <= 0:
        return []
    return entries[-limit:]


def _finding(
    *,
    line: int,
    code: str,
    message: str,
    suggestion: str,
    severity: str = "error",
) -> dict[str, Any]:
    return {
        "path": LOG_PATH,
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


def check_log(vault: Path, strict: bool = False) -> dict[str, Any]:
    target = ensure_log_file(vault)
    text = target.read_text(encoding="utf-8")
    findings: list[dict[str, Any]] = []
    non_empty = [(index, line.strip()) for index, line in enumerate(text.splitlines(), 1) if line.strip()]
    if non_empty and non_empty[0][1] != "# Wiki Log":
        findings.append(
            _finding(
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
                    line=line_number,
                    code="log_heading_format",
                    message="log entry heading must match ## [timestamp] action | title",
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
                    line=line_number,
                    code="log_timestamp_invalid",
                    message="timestamp must be a valid UTC ISO timestamp with second precision",
                    suggestion="Use UTC timestamps like 2026-06-01T13:04:55Z.",
                )
            )
        elif previous_timestamp is not None and timestamp < previous_timestamp:
            findings.append(
                _finding(
                    line=line_number,
                    code="log_timestamp_order",
                    message="log entry timestamps should be monotonic non-decreasing",
                    suggestion="Reorder or rerender entries so timestamps do not go backwards.",
                    severity="error" if strict else "warning",
                )
            )
        if timestamp is not None:
            previous_timestamp = timestamp

        if "status" not in entry:
            findings.append(
                _finding(
                    line=line_number,
                    code="log_missing_status",
                    message="log entry must include a - status: bullet",
                    suggestion="Add a status bullet such as clean or changed.",
                )
            )
        elif str(entry["status"]) not in ALLOWED_STATUSES:
            findings.append(
                _finding(
                    line=line_number,
                    code="log_status_invalid",
                    message="log status must be one of the known operational statuses",
                    suggestion="Use a known status such as clean, changed, invalid, or actionable.",
                )
            )

        if "command" not in entry:
            findings.append(
                _finding(
                    line=line_number,
                    code="log_missing_command",
                    message="log entry must include a - command: bullet",
                    suggestion="Add the CLI command identity to the log entry.",
                )
            )

        if len(str(entry.get("body", "")).encode("utf-8")) > MAX_ENTRY_BODY_BYTES:
            findings.append(
                _finding(
                    line=line_number,
                    code="log_entry_too_large",
                    message="log entry body should stay below 8 KiB",
                    suggestion="Move large details elsewhere and keep the log entry compact.",
                    severity="warning",
                )
            )

    ok = not any(finding["severity"] == "error" for finding in findings)
    return {"ok": ok, "entries": len(entries), "findings": findings}
