"""Template command group."""

from __future__ import annotations

import typer

from ..cli_helpers import _exit_rows, _vault_from_ctx
from ..cli_output import emit
from ..templates import list_templates, read_template_file, render_template_file


def register_template(app: typer.Typer) -> None:
    _template_app = typer.Typer(help="Template operations.")
    app.add_typer(_template_app, name="template")

    @_template_app.command("list")
    def template_list_cmd(
        ctx: typer.Context,
        total: bool = typer.Option(False, "--total"),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        rows = list_templates(vault)
        _exit_rows(rows, fmt, total=total)

    @_template_app.command("read")
    def template_read_cmd(
        ctx: typer.Context,
        name: str = typer.Argument(..., help="Template name."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        content = read_template_file(vault, name)
        payload = {"name": name, "content": content}
        raise typer.Exit(emit(payload, content, fmt))

    @_template_app.command("render")
    def template_render_cmd(
        ctx: typer.Context,
        name: str = typer.Argument(..., help="Template name."),
        title: str = typer.Option(..., "--title", help="Title."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        content = render_template_file(vault, name, title)
        payload = {"name": name, "content": content}
        raise typer.Exit(emit(payload, content, fmt))
