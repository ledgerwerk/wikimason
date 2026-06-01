"""Operational log command group."""

from __future__ import annotations

import typer

from ..cli_helpers import _vault_from_ctx
from ..cli_output import OutputFormat, emit, normalize_format
from ..logs import LogEvent, append_log_event, check_log, tail_log


def _tail_text(entries: list[dict[str, object]]) -> str:
    if not entries:
        return "log empty"
    return "\n".join(
        f"{entry['timestamp']} {entry['action']} | {entry['title']}" for entry in entries
    )


def register_log(app: typer.Typer) -> None:
    _log_app = typer.Typer(help="Operational log commands.")
    app.add_typer(_log_app, name="log")

    @_log_app.command("add")
    def log_add_cmd(
        ctx: typer.Context,
        action: str = typer.Option(..., "--action", help="Operational action name."),
        title: str = typer.Option(..., "--title", help="Log title."),
        details: str = typer.Option("", "--details", help="Optional summary/details."),
        path: list[str] = typer.Option([], "--path", help="Related vault paths."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        target = append_log_event(
            vault,
            LogEvent(
                action=action,
                command="log.add",
                title=title,
                status="changed",
                summary=details.strip(),
                paths=tuple(path),
            ),
        )
        rel = target.relative_to(vault).as_posix()
        payload = {"path": rel, "action": action, "title": title, "paths": path}
        raise typer.Exit(
            emit(payload, rel, fmt, command="log.add", status="changed")
        )

    @_log_app.command("tail")
    def log_tail_cmd(
        ctx: typer.Context,
        limit: int = typer.Option(20, "-n", help="Number of entries to show."),
        action: str | None = typer.Option(None, "--action", help="Filter by action."),
        command: str | None = typer.Option(
            None, "--command", help="Filter by command name."
        ),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        entries = tail_log(vault, limit=limit, action=action, command=command)
        payload = {"items": entries, "total": len(entries)}
        raise typer.Exit(
            emit(payload, _tail_text(entries), fmt, command="log.tail", status="clean")
        )

    @_log_app.command("check")
    def log_check_cmd(
        ctx: typer.Context,
        strict: bool = typer.Option(False, "--strict", help="Fail on warnings."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        payload = check_log(vault, strict=strict)
        findings = payload["findings"]
        exit_code = 0 if payload["ok"] else 1
        status = "clean" if payload["ok"] else "invalid"
        if normalize_format(fmt) is OutputFormat.json:
            raise typer.Exit(
                emit(
                    payload,
                    "",
                    fmt,
                    exit_code=exit_code,
                    command="log.check",
                    status=status,
                )
            )
        if findings:
            for finding in findings:
                prefix = (
                    f"{finding['path']}:{finding['line']}"
                    if finding["line"]
                    else str(finding["path"])
                )
                line = f"{prefix}: {finding['message']}"
                suggestion = str(finding.get("suggestion") or "")
                if suggestion:
                    line += f" (suggestion: {suggestion})"
                typer.echo(line)
        else:
            typer.echo("log ok")
        raise typer.Exit(exit_code)
