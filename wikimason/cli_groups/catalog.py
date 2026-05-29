"""Catalog command group."""

from __future__ import annotations

import json

import typer

from ..build import build_vault
from ..catalog import catalog_status, iter_catalog_entries, write_catalog
from ..cli_helpers import _vault_from_ctx
from ..cli_output import emit
from ..errors import UsageError
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
        if fmt == "json":
            print(json.dumps(rows, sort_keys=True))
        else:
            for row in rows:
                print(f"{row['title']}\t{row['path']}")
        raise typer.Exit(0)

    @_catalog_app.command("build")
    def catalog_build_cmd(
        ctx: typer.Context,
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        entries = list(iter_catalog_entries(vault))
        write_catalog(vault, entries)
        payload = {"ok": True, "count": len(entries), "path": "Wiki/catalog.jsonl"}
        raise typer.Exit(emit(payload, str(len(entries)), fmt))

    @_catalog_app.command("check")
    def catalog_check_cmd(
        ctx: typer.Context,
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        payload = catalog_status(vault)
        text = "catalog up to date" if payload["ok"] else "catalog is stale"
        raise typer.Exit(emit(payload, text, fmt, exit_code=0 if payload["ok"] else 1))

    @_catalog_app.command("rebuild")
    def catalog_rebuild_cmd(
        ctx: typer.Context,
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        result = build_vault(vault)
        payload = {
            "updated_source_count": result.updated_source_count,
            "catalog_count": result.catalog_count,
        }
        raise typer.Exit(
            emit(payload, f"updated_source_count={result.updated_source_count}", fmt)
        )
