"""Folder command group."""

from __future__ import annotations

import typer

from ..cli_helpers import _vault_from_ctx
from ..cli_output import emit
from ..files import folder_file_count, list_folders
from ..paths import rel_to_vault, resolve_path_in_vault


def register_folder(app: typer.Typer) -> None:
    _folder_app = typer.Typer(help="Folder operations.")
    app.add_typer(_folder_app, name="folder")

    @_folder_app.command("list")
    def folder_list_cmd(
        ctx: typer.Context,
        path: str = typer.Argument(None, help="Subpath."),
        total: bool = typer.Option(False, "--total"),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        rows = list_folders(vault, path)
        if total:
            raise typer.Exit(emit({"total": len(rows)}, str(len(rows)), fmt))
        raise typer.Exit(emit(rows, "\n".join(rows), fmt))

    @_folder_app.command("info")
    def folder_info_cmd(
        ctx: typer.Context,
        path: str = typer.Argument(None, help="Folder path."),
        files: bool = typer.Option(False, "--files"),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        folder = resolve_path_in_vault(vault, path) if path else vault
        payload = {
            "path": rel_to_vault(vault, folder) if folder != vault else ".",
            "files": folder_file_count(vault, path),
        }
        text = str(payload["files"]) if files else str(folder)
        raise typer.Exit(emit(payload, text, fmt))
