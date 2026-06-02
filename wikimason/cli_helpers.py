"""Shared helpers for CLI command handlers."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NoReturn

import typer

from .cli_output import OutputFormat, emit, normalize_format, result_payload
from .cli_state import resolve_vault
from .config import load_runtime_config
from .logs import LogEvent, append_log_event
from .notes import new_note, parse_path_values
from .paths import rel_to_vault

# ---------------------------------------------------------------------------
# Context / vault helpers
# ---------------------------------------------------------------------------


def _vault_from_ctx(ctx: typer.Context) -> Path:
    state = ctx.find_root().obj
    return resolve_vault(state)


def _config_payload(context: Any) -> dict[str, Any]:
    return {
        "root": str(context.root),
        "config_path": (
            str(context.config_path) if context.config_path is not None else None
        ),
        "env": context.env,
        "resolution": context.resolution,
        "diagnostics": list(context.diagnostics),
        "profile": context.config.profile,
        "paths": context.config.paths.as_dict(),
        "links": context.config.links.as_dict(),
        "profile_settings": context.config.profile_config.as_dict(),
        "logging": context.config.logging.as_dict(),
    }


def _config_text(payload: dict[str, Any]) -> str:
    lines = [
        f"root: {payload['root']}",
        f"profile: {payload['profile']}",
        f"resolution: {payload['resolution']}",
    ]
    if payload["config_path"] is not None:
        lines.append(f"config_path: {payload['config_path']}")
    if payload["env"] is not None:
        lines.append(f"env: {payload['env']}")
    diagnostics = payload.get("diagnostics", [])
    if diagnostics:
        lines.extend(["diagnostics:"] + [f"- {item}" for item in diagnostics])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Payload / text rendering helpers
# ---------------------------------------------------------------------------


def _delta_text(delta: dict[str, list[dict[str, Any]]]) -> str:
    return "\n".join(
        [
            f"new: {len(delta['new'])}",
            f"content_changed: {len(delta['content_changed'])}",
            f"metadata_changed: {len(delta['metadata_changed'])}",
            f"missing_coverage: {len(delta['missing_coverage'])}",
            f"removed: {len(delta['removed'])}",
            f"covered: {len(delta['covered'])}",
        ]
    )


def _doctor_payload(vault: Path) -> dict[str, Any]:
    from .ingest import doctor_status

    payload = doctor_status(vault)
    checks = []
    for check in payload["checks"]:
        row = dict(check)
        if row["label"] == "Python runtime":
            row["detail"] = sys.version.split()[0]
        checks.append(row)
    required_ok = all(
        bool(check["ok"]) for check in checks if bool(check.get("required", False))
    )
    maintenance_ok = all(
        bool(check["ok"]) for check in checks if not bool(check.get("required", False))
    )
    if not required_ok:
        status = "invalid"
    elif not maintenance_ok:
        status = "degraded"
    else:
        status = "clean"
    return {
        "ok": payload["ok"],
        "required_ok": required_ok,
        "maintenance_ok": maintenance_ok,
        "status": status,
        "checks": checks,
    }


def _doctor_text(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    for check in payload["checks"]:
        label = str(check["label"])
        ok = bool(check["ok"])
        required = bool(check["required"])
        if label == "Python runtime":
            lines.append(f"[ok] {label} - {check.get('detail', '')}")
            continue
        state = "ok" if ok else ("fail" if required else "warn")
        lines.append(f"[{state}] {label}")
    return "\n".join(lines)


def _collect_tags(vault: Path) -> dict[str, int]:
    from .config import load_runtime_config
    from .page_profiles import split_page_text
    from .paths import compiled_md_files

    rows: dict[str, int] = {}
    config = load_runtime_config(vault)
    for path in compiled_md_files(vault):
        text = path.read_text(encoding="utf-8")
        data, _ = split_page_text(text, config=config)
        tags = data.get("tags", [])
        if isinstance(tags, list):
            for value in tags:
                tag = f"#{str(value).lstrip('#')}"
                rows[tag] = rows.get(tag, 0) + 1
        for token in text.split():
            if token.startswith("#") and len(token) > 1 and token[1].isalnum():
                rows[token] = rows.get(token, 0) + 1
    return rows


# ---------------------------------------------------------------------------
# Exit helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CommandOutcome:
    payload: object
    text: str
    command: str
    status: str
    exit_code: int = 0
    warnings: tuple[str, ...] = field(default_factory=tuple)
    errors: tuple[str, ...] = field(default_factory=tuple)
    next_action: str | None = None


def _exit_emit(payload: object, text: str, fmt: str, *, exit_code: int = 0) -> NoReturn:
    """Emit *payload*/*text* via :func:`emit` and raise ``typer.Exit``."""
    raise typer.Exit(emit(payload, text, fmt, exit_code=exit_code))


def _finish_command(
    ctx: typer.Context,
    outcome: CommandOutcome,
    fmt: str,
    *,
    log_event: LogEvent | None = None,
) -> NoReturn:
    """Emit one command outcome and optionally append a structured log event."""
    text = outcome.text
    warnings = list(outcome.warnings)
    if log_event is not None:
        try:
            _append_command_log(ctx, log_event)
        except OSError as exc:
            message = f"log write failed: {exc}"
            warnings.append(message)
            if normalize_format(fmt) is not OutputFormat.json:
                text = f"{text}\nwarning: {message}" if text else f"warning: {message}"
    raise typer.Exit(
        emit(
            outcome.payload,
            text,
            fmt,
            exit_code=outcome.exit_code,
            command=outcome.command,
            status=outcome.status,
            warnings=warnings,
            errors=list(outcome.errors),
            next_action=outcome.next_action,
        )
    )


def _context_from_ctx(ctx: typer.Context) -> Any:
    vault = _vault_from_ctx(ctx)
    return type(
        "CommandContext",
        (),
        {"root": vault, "config": load_runtime_config(vault)},
    )()


def _append_command_log(
    ctx: typer.Context,
    event: LogEvent | None,
    *,
    force: bool = False,
) -> Path | None:
    if event is None:
        return None
    context = _context_from_ctx(ctx)
    return append_log_event(context.root, event, config=context.config, force=force)


def _exit_rows(rows: Sequence[str], fmt: str, *, total: bool = False) -> None:
    """Emit a row list.  When *total* is true, also emit the count."""
    if total:
        _exit_emit({"total": len(rows)}, str(len(rows)), fmt)
    _exit_emit(rows, "\n".join(rows), fmt)


# ---------------------------------------------------------------------------
# Shared command implementations
# ---------------------------------------------------------------------------


def _findings_text(payload: dict[str, Any], *, success_text: str) -> str:
    findings = payload["findings"]
    if not findings:
        return success_text
    lines: list[str] = []
    for finding in findings:
        prefix = (
            f"{finding['path']}:{finding['line']}"
            if finding["line"]
            else finding["path"]
        )
        line = f"{prefix}: {finding['message']}"
        if finding["suggestion"]:
            line += f" (suggestion: {finding['suggestion']})"
        lines.append(line)
    return "\n".join(lines)


def _run_doctor(ctx: typer.Context, *, command: str) -> CommandOutcome:
    """Build the shared result for ``vault doctor`` and top-level ``doctor``."""
    vault = _vault_from_ctx(ctx)
    raw = _doctor_payload(vault)
    exit_code = 0 if raw["ok"] else 1
    status = str(raw["status"])
    return CommandOutcome(
        payload=result_payload(
            command=command,
            status=status,
            data=raw,
            exit_code=exit_code,
        ),
        text=_doctor_text(raw),
        command=command,
        status=status,
        exit_code=exit_code,
    )


def _run_lint(ctx: typer.Context, strict: bool, *, command: str) -> CommandOutcome:
    """Build the shared result for ``vault lint`` and top-level ``lint``."""
    from .lint import lint_payload

    vault = _vault_from_ctx(ctx)
    payload = lint_payload(vault, strict=strict)
    exit_code = 0 if payload["ok"] else 1
    status = "clean" if exit_code == 0 else "invalid"
    return CommandOutcome(
        payload=result_payload(
            command=command,
            status=status,
            data=payload,
            exit_code=exit_code,
        ),
        text=_findings_text(payload, success_text="lint passed"),
        command=command,
        status=status,
        exit_code=exit_code,
    )


def _note_create_payload(vault: Path, scaffold: Any) -> dict[str, Any]:
    """Build the JSON payload returned by page-create / note-new."""
    return {
        "path": rel_to_vault(vault, scaffold.path),
        "kind": scaffold.kind,
        "title": scaffold.title,
        "status": scaffold.status,
        "sources": list(scaffold.sources),
        "related": list(scaffold.related),
        "allow_incomplete": scaffold.allow_incomplete,
    }


def _run_note_create(
    ctx: typer.Context,
    *,
    command: str,
    kind: str,
    title: str,
    source: list[str],
    related: list[str],
    status: str,
    summary: str,
    body: str | None,
    body_file: str | None,
    path: str | None,
    dry_run: bool,
    print_note: bool,
    allow_incomplete: bool,
) -> CommandOutcome:
    """Build the shared result for ``page create`` and ``note new``."""
    vault = _vault_from_ctx(ctx)
    scaffold = new_note(
        vault,
        kind=kind,
        title=title,
        sources=parse_path_values(source),
        related=parse_path_values(related),
        status=status,
        summary=summary,
        body=body,
        body_file=body_file,
        path=path,
        dry_run=dry_run,
        allow_incomplete=allow_incomplete,
    )
    payload = _note_create_payload(vault, scaffold)
    if dry_run:
        payload["content"] = scaffold.content
    text = scaffold.content if print_note else str(payload["path"])
    outcome_status = "clean" if dry_run else "changed"
    wrapped = result_payload(command=command, status=outcome_status, data=payload)
    wrapped.update(payload)
    return CommandOutcome(
        payload=wrapped,
        text=text,
        command=command,
        status=outcome_status,
    )


def _run_row_command(
    ctx: typer.Context, get_rows: Any, *, command: str
) -> CommandOutcome:
    """Build the shared result for ``links unresolved``, ``links orphans``, ``links deadends``."""  # noqa: E501
    vault = _vault_from_ctx(ctx)
    rows = get_rows(vault)
    status = "actionable" if rows else "clean"
    wrapped = result_payload(
        command=command,
        status=status,
        data={"items": rows, "total": len(rows)},
    )
    wrapped.update({"items": rows, "total": len(rows)})
    return CommandOutcome(
        payload=wrapped,
        text="\n".join(rows),
        command=command,
        status=status,
    )
