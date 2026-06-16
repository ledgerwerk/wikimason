"""Catalog command group."""

from __future__ import annotations

import typer

from ..build import build_vault
from ..catalog import catalog_status, iter_catalog_entries, write_catalog
from ..cli_helpers import CommandOutcome, _exit_emit, _finish_command, _vault_from_ctx
from ..errors import UsageError
from ..log_events import change_event
from ..search import search_catalog


def register_catalog(app: typer.Typer) -> None:
    _catalog_app = typer.Typer(help="Catalog operations.")
    app.add_typer(_catalog_app, name="catalog")

    @_catalog_app.command("search")
    def catalog_search_cmd(
        ctx: typer.Context,
        query_arg: str | None = typer.Argument(None, help="Search query."),
        query_opt: str | None = typer.Option(
            None, "--query", "-q", help="Search query."
        ),
        tag: str | None = typer.Option(None, "--tag", help="Filter by tag."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        actual_query = query_opt or query_arg or ""
        if not actual_query:
            raise UsageError("catalog search requires QUERY or --query")
        rows = search_catalog(vault, query=actual_query, tag=tag, limit=10)
        text = "\n".join(f"{row['title']}\t{row['path']}" for row in rows)
        _exit_emit(rows, text, fmt)

    @_catalog_app.command("build")
    def catalog_build_cmd(
        ctx: typer.Context,
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        entries = list(iter_catalog_entries(vault))
        write_catalog(vault, entries)
        payload = {"ok": True, "count": len(entries), "path": "Wiki/catalog.jsonl"}
        _finish_command(
            ctx,
            CommandOutcome(
                payload=payload,
                text=str(len(entries)),
                command="catalog.build",
                status="changed",
            ),
            fmt,
            log_event=change_event(
                "catalog.build",
                "Built catalog",
                summary=f"Wrote {len(entries)} catalog entries.",
                paths=("Wiki/catalog.jsonl",),
                counts={"count": len(entries)},
            ),
        )

    @_catalog_app.command("check")
    def catalog_check_cmd(
        ctx: typer.Context,
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        payload = catalog_status(vault)
        text = "catalog up to date" if payload["ok"] else "catalog is stale"
        _exit_emit(payload, text, fmt, exit_code=0 if payload["ok"] else 1)

    @_catalog_app.command("rebuild")
    def catalog_rebuild_cmd(
        ctx: typer.Context,
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        result = build_vault(vault)
        payload = {
            "updated_type_count": result.updated_type_count,
            "updated_source_count": result.updated_source_count,
            "catalog_count": result.catalog_count,
        }
        _finish_command(
            ctx,
            CommandOutcome(
                payload=payload,
                text=(
                    f"updated_type_count={result.updated_type_count}"
                    f" updated_source_count={result.updated_source_count}"
                ),
                command="catalog.rebuild",
                status="changed",
            ),
            fmt,
            log_event=change_event(
                "catalog.rebuild",
                "Rebuilt catalog",
                summary=f"updated_source_count={result.updated_source_count}",
                paths=("Wiki/catalog.jsonl",),
                counts={
                    "updated_type_count": result.updated_type_count,
                    "updated_source_count": result.updated_source_count,
                    "catalog_count": result.catalog_count,
                },
            ),
        )
