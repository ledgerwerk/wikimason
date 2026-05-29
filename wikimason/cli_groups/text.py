"""Text command group."""

from __future__ import annotations

import typer

from ..cli_helpers import _vault_from_ctx
from ..cli_output import emit
from ..files import read_file
from ..text_tools import outline, wordcount


def register_text(app: typer.Typer) -> None:
    _text_app = typer.Typer(help="Text analysis.")
    app.add_typer(_text_app, name="text")

    @_text_app.command("wordcount")
    def text_wordcount_cmd(
        ctx: typer.Context,
        path: str = typer.Argument(..., help="File path."),
        words: bool = typer.Option(False, "--words"),
        characters: bool = typer.Option(False, "--characters"),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        text = read_file(vault, path)
        payload = wordcount(text)
        if words:
            raise typer.Exit(emit(payload, str(payload["words"]), fmt))
        if characters:
            raise typer.Exit(emit(payload, str(payload["characters"]), fmt))
        raise typer.Exit(
            emit(
                payload,
                f"words {payload['words']}\ncharacters {payload['characters']}",
                fmt,
            )
        )

    @_text_app.command("outline")
    def text_outline_cmd(
        ctx: typer.Context,
        path: str = typer.Argument(..., help="File path."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        text = read_file(vault, path)
        lines, payload = outline(text)
        raise typer.Exit(emit(payload, "\n".join(lines), fmt))
