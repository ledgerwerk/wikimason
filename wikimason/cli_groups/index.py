"""Index command group."""

from __future__ import annotations

import typer

from ..build import index_status, rebuild_indexes
from ..catalog import iter_catalog_entries
from ..cli_helpers import CommandOutcome, _finish_command, _vault_from_ctx
from ..cli_output import emit
from ..log_events import change_event


def register_index(app: typer.Typer) -> None:
    _index_app = typer.Typer(help="Index operations.")
    app.add_typer(_index_app, name="index")

    @_index_app.command("build")
    def index_build_cmd(
        ctx: typer.Context,
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        entries = list(iter_catalog_entries(vault))
        rebuild_indexes(vault, entries)
        _finish_command(
            ctx,
            CommandOutcome(
                payload={"ok": True, "count": len(entries)},
                text="index rebuilt",
                command="index.build",
                status="changed",
            ),
            fmt,
            log_event=change_event(
                "index.build",
                "Built indexes",
                summary=f"Rebuilt indexes from {len(entries)} catalog entries.",
                counts={"count": len(entries)},
            ),
        )

    @_index_app.command("check")
    def index_check_cmd(
        ctx: typer.Context,
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        payload = index_status(vault)
        text = "index up to date" if payload["ok"] else "index is stale"
        raise typer.Exit(emit(payload, text, fmt, exit_code=0 if payload["ok"] else 1))
