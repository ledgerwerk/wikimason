"""Ingest command group."""

from __future__ import annotations

import json

import typer

from ..cli_helpers import _vault_from_ctx
from ..cli_output import emit
from ..ingest import (
    ingest_finish,
    ingest_plan,
    ingest_status,
    render_ingest_finish_json,
)


def register_ingest(app: typer.Typer) -> None:
    _ingest_app = typer.Typer(help="Ingest operations.")
    app.add_typer(_ingest_app, name="ingest")

    @_ingest_app.callback(invoke_without_command=True)
    def ingest_root(
        ctx: typer.Context,
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        if ctx.invoked_subcommand is not None:
            return
        vault = _vault_from_ctx(ctx)
        payload = ingest_status(vault)
        raise typer.Exit(emit(payload, str(payload["next_action"]), fmt))

    @_ingest_app.command("status")
    def ingest_status_cmd(
        ctx: typer.Context,
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        payload = ingest_status(vault)
        text = payload["next_action"]
        raise typer.Exit(emit(payload, str(text), fmt))

    @_ingest_app.command("plan")
    def ingest_plan_cmd(
        ctx: typer.Context,
        sources: list[str] = typer.Argument(None, help="Source paths."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        payload = ingest_plan(vault, sources or [])
        text = (
            payload["source"]
            if isinstance(payload, dict) and "source" in payload
            else json.dumps(payload, sort_keys=True)
        )
        raise typer.Exit(emit(payload, text, fmt))

    @_ingest_app.command("finish")
    def ingest_finish_cmd(
        ctx: typer.Context,
        accept_covered: bool = typer.Option(False, "--accept-covered"),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        result = ingest_finish(vault, accept_covered=accept_covered)
        payload = render_ingest_finish_json(result)
        text = "ingest finish clean" if result.exit_code == 0 else result.next_action
        raise typer.Exit(emit(payload, text, fmt, exit_code=result.exit_code))
