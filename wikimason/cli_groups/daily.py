"""Daily command group."""

from __future__ import annotations

from datetime import date

import typer

from ..cli_helpers import CommandOutcome, _finish_command, _vault_from_ctx
from ..cli_output import emit
from ..daily import append_daily, daily_note_path, prepend_daily, read_daily
from ..errors import UsageError
from ..log_events import change_event
from ..paths import rel_to_vault


def _parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise UsageError(f"invalid date: {value}") from exc


def register_daily(app: typer.Typer) -> None:
    _daily_app = typer.Typer(help="Daily note operations.")
    app.add_typer(_daily_app, name="daily")

    @_daily_app.command("path")
    def daily_path_cmd(
        ctx: typer.Context,
        day: str = typer.Argument(None, help="Date (YYYY-MM-DD)."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        d = _parse_date(day)
        path = daily_note_path(vault, d)
        payload = {"path": rel_to_vault(vault, path)}
        raise typer.Exit(emit(payload, payload["path"], fmt))

    @_daily_app.command("read")
    def daily_read_cmd(
        ctx: typer.Context,
        day: str = typer.Argument(None, help="Date (YYYY-MM-DD)."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        d = _parse_date(day)
        text = read_daily(vault, d)
        path = daily_note_path(vault, d)
        payload = {"path": rel_to_vault(vault, path), "content": text}
        raise typer.Exit(emit(payload, text, fmt))

    @_daily_app.command("append")
    def daily_append_cmd(
        ctx: typer.Context,
        content: str = typer.Option(..., "--content", help="Content to append."),
        day: str = typer.Argument(None, help="Date (YYYY-MM-DD)."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        d = _parse_date(day)
        path = append_daily(vault, content, d)
        payload = {"path": rel_to_vault(vault, path)}
        _finish_command(
            ctx,
            CommandOutcome(
                payload=payload,
                text=payload["path"],
                command="daily.append",
                status="changed",
            ),
            fmt,
            log_event=change_event(
                "daily.append",
                "Appended daily note",
                summary=payload["path"],
                paths=(payload["path"],),
            ),
        )

    @_daily_app.command("prepend")
    def daily_prepend_cmd(
        ctx: typer.Context,
        content: str = typer.Option(..., "--content", help="Content to prepend."),
        day: str = typer.Argument(None, help="Date (YYYY-MM-DD)."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        d = _parse_date(day)
        path = prepend_daily(vault, content, d)
        payload = {"path": rel_to_vault(vault, path)}
        _finish_command(
            ctx,
            CommandOutcome(
                payload=payload,
                text=payload["path"],
                command="daily.prepend",
                status="changed",
            ),
            fmt,
            log_event=change_event(
                "daily.prepend",
                "Prepended daily note",
                summary=payload["path"],
                paths=(payload["path"],),
            ),
        )
