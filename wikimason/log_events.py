from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .logs import LogEvent


def _level_for(status: str, exit_code: int) -> str:
    if status in {"invalid", "error"} or exit_code > 0:
        return "error"
    if status in {"actionable", "ambiguous", "not_found", "warning"}:
        return "warning"
    return "info"


def _event(
    *,
    command: str,
    status: str,
    title: str,
    summary: str = "",
    action: str | None = None,
    exit_code: int = 0,
    paths: Sequence[str] = (),
    sources: Sequence[str] = (),
    counts: Mapping[str, int | float | str] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> LogEvent:
    return LogEvent(
        action=action or command,
        command=command,
        title=title,
        status=status,
        exit_code=exit_code,
        level=_level_for(status, exit_code),
        summary=summary,
        paths=tuple(paths),
        sources=tuple(sources),
        counts=dict(counts or {}),
        metadata=dict(metadata or {}),
    )


def change_event(
    command: str,
    title: str,
    *,
    summary: str = "",
    paths: Sequence[str] = (),
    sources: Sequence[str] = (),
    counts: Mapping[str, int | float | str] | None = None,
    metadata: Mapping[str, Any] | None = None,
    status: str = "changed",
    exit_code: int = 0,
    action: str | None = None,
) -> LogEvent:
    return _event(
        command=command,
        status=status,
        title=title,
        summary=summary,
        action=action,
        exit_code=exit_code,
        paths=paths,
        sources=sources,
        counts=counts,
        metadata=metadata,
    )


def audit_event(
    command: str,
    title: str,
    *,
    summary: str = "",
    counts: Mapping[str, int | float | str] | None = None,
    metadata: Mapping[str, Any] | None = None,
    status: str = "clean",
    exit_code: int = 0,
    action: str | None = None,
    paths: Sequence[str] = (),
    sources: Sequence[str] = (),
) -> LogEvent:
    return _event(
        command=command,
        status=status,
        title=title,
        summary=summary,
        action=action,
        exit_code=exit_code,
        counts=counts,
        metadata=metadata,
        paths=paths,
        sources=sources,
    )


def source_event(
    command: str,
    status: str,
    path: str,
    *,
    title: str,
    summary: str = "",
    source_id: str | None = None,
    counts: Mapping[str, int | float | str] | None = None,
    metadata: Mapping[str, Any] | None = None,
    exit_code: int = 0,
) -> LogEvent:
    merged_metadata = dict(metadata or {})
    if source_id:
        merged_metadata.setdefault("source_id", source_id)
    return change_event(
        command,
        title,
        summary=summary,
        paths=(path,),
        counts=counts,
        metadata=merged_metadata,
        status=status,
        exit_code=exit_code,
    )


def query_event(query: str, rows: Sequence[Mapping[str, object]]) -> LogEvent:
    return audit_event(
        "query",
        "Searched catalog",
        summary=f"Query: {query}",
        counts={"rows": len(rows)},
        metadata={"tagged": "false"},
    )


def lint_event(
    command: str, payload: Mapping[str, object], *, strict: bool = False
) -> LogEvent:
    findings = payload.get("findings", [])
    finding_count = len(findings) if isinstance(findings, list) else 0
    titles = {
        "lint": "Linted compiled pages",
        "vault.lint": "Linted vault",
        "source.lint": "Linted source manifest",
        "links.check": "Checked wiki links",
    }
    summary = (
        "Lint passed with no findings."
        if bool(payload.get("ok", False))
        else f"Lint completed with {finding_count} finding(s)."
    )
    status = "clean" if bool(payload.get("ok", False)) else "invalid"
    exit_code = (
        int(payload.get("exit_code", 0))
        if "exit_code" in payload
        else (0 if status == "clean" else 1)
    )
    return audit_event(
        command,
        titles.get(command, "Ran lint checks"),
        summary=summary,
        counts={"findings": finding_count},
        metadata={"strict": str(strict).lower()},
        status=status,
        exit_code=exit_code,
    )
