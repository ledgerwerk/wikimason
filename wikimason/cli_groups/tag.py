"""Tag command group."""

from __future__ import annotations

import typer

from ..cli_helpers import _collect_tags, _vault_from_ctx
from ..cli_output import emit


def register_tag(app: typer.Typer) -> None:
    _tag_app = typer.Typer(help="Tag operations.")
    app.add_typer(_tag_app, name="tag")

    @_tag_app.command("list")
    def tag_list_cmd(
        ctx: typer.Context,
        counts: bool = typer.Option(False, "--counts"),
        sort_count: bool = typer.Option(False, "--sort-count"),
        total: bool = typer.Option(False, "--total"),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        rows = _collect_tags(vault)
        if total:
            raise typer.Exit(emit({"total": len(rows)}, str(len(rows)), fmt))
        if counts:
            items = (
                sorted(rows.items(), key=lambda item: (-item[1], item[0]))
                if sort_count
                else sorted(rows.items())
            )
            text = "\n".join(f"{tag}\t{count}" for tag, count in items)
            raise typer.Exit(emit(dict(items), text, fmt))
        raise typer.Exit(emit(sorted(rows), "\n".join(sorted(rows)), fmt))

    @_tag_app.command("count")
    def tag_count_cmd(
        ctx: typer.Context,
        name: str = typer.Argument(..., help="Tag name."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        rows = _collect_tags(vault)
        tag = f"#{name.lstrip('#')}"
        payload = {"tag": tag, "count": rows.get(tag, 0)}
        raise typer.Exit(emit(payload, str(payload["count"]), fmt))
