"""Index command group."""

from __future__ import annotations

import typer

from ..build import index_status, rebuild_indexes
from ..catalog import iter_catalog_entries
from ..cli_helpers import _vault_from_ctx
from ..cli_output import emit


def register_index(app: typer.Typer) -> None:
    _index_app = typer.Typer(help="Index operations.")
    app.add_typer(_index_app, name="index")

    @_index_app.command("build")
    def index_build_cmd(
        ctx: typer.Context,
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        rebuild_indexes(vault, list(iter_catalog_entries(vault)))
        raise typer.Exit(emit({"ok": True}, "index rebuilt", fmt))

    @_index_app.command("check")
    def index_check_cmd(
        ctx: typer.Context,
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        payload = index_status(vault)
        text = "index up to date" if payload["ok"] else "index is stale"
        raise typer.Exit(emit(payload, text, fmt, exit_code=0 if payload["ok"] else 1))
