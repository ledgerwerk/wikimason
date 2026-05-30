"""Shared helpers for CLI command handlers."""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, NoReturn

import typer

from .cli_output import emit
from .cli_state import resolve_vault
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
    return {"ok": payload["ok"], "checks": checks}


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


def _exit_emit(payload: object, text: str, fmt: str, *, exit_code: int = 0) -> NoReturn:
    """Emit *payload*/*text* via :func:`emit` and raise ``typer.Exit``."""
    raise typer.Exit(emit(payload, text, fmt, exit_code=exit_code))


def _exit_rows(rows: Sequence[str], fmt: str, *, total: bool = False) -> None:
    """Emit a row list.  When *total* is true, also emit the count."""
    if total:
        _exit_emit({"total": len(rows)}, str(len(rows)), fmt)
    _exit_emit(rows, "\n".join(rows), fmt)


# ---------------------------------------------------------------------------
# Shared command implementations
# ---------------------------------------------------------------------------


def _run_doctor(ctx: typer.Context, fmt: str) -> None:
    """Shared body for ``vault doctor`` and top-level ``doctor``."""
    vault = _vault_from_ctx(ctx)
    payload = _doctor_payload(vault)
    if fmt == "json":
        print(json.dumps(payload, sort_keys=True))
    else:
        print(_doctor_text(payload))
    raise typer.Exit(0 if payload["ok"] else 1)


def _run_lint(ctx: typer.Context, strict: bool, fmt: str) -> None:
    """Shared body for ``vault lint`` and top-level ``lint``."""
    from .cli_output import print_findings_payload
    from .lint import lint_payload

    vault = _vault_from_ctx(ctx)
    payload = lint_payload(vault, strict=strict)
    raise typer.Exit(
        print_findings_payload(payload, success_text="lint passed", fmt=fmt)
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
    kind: str,
    title: str,
    source: list[str],
    related: list[str],
    status: str,
    summary: str,
    body_file: str | None,
    allow_incomplete: bool,
    fmt: str,
) -> None:
    """Shared body for ``page create`` and ``note new``."""
    vault = _vault_from_ctx(ctx)
    scaffold = new_note(
        vault,
        kind=kind,
        title=title,
        sources=parse_path_values(source),
        related=parse_path_values(related),
        status=status,
        summary=summary,
        body_file=body_file,
        allow_incomplete=allow_incomplete,
    )
    payload = _note_create_payload(vault, scaffold)
    _exit_emit(payload, payload["path"], fmt)


def _run_row_command(ctx: typer.Context, get_rows: Any, fmt: str) -> None:
    """Shared body for ``links unresolved``, ``links orphans``, ``links deadends``."""
    vault = _vault_from_ctx(ctx)
    rows = get_rows(vault)
    _exit_emit(rows, "\n".join(rows), fmt)
