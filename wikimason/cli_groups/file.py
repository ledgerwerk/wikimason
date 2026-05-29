"""File command group."""

from __future__ import annotations

import typer

from ..cli_helpers import _exit_rows, _vault_from_ctx
from ..cli_output import emit
from ..config import load_runtime_config
from ..files import (
    append_file,
    delete_file,
    move_file,
    open_file,
    prepend_file,
    read_file,
    rename_file,
    resolve_existing_path,
    search_files,
    write_file,
)
from ..paths import rel_to_vault


def register_file(app: typer.Typer) -> None:
    _file_app = typer.Typer(help="File operations.")
    app.add_typer(_file_app, name="file")

    @_file_app.command("list")
    def file_list_cmd(
        ctx: typer.Context,
        path: str = typer.Argument(None, help="Subpath."),
        total: bool = typer.Option(False, "--total"),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        rows = list_files(vault, path)
        _exit_rows(rows, fmt, total=total)

    @_file_app.command("read")
    def file_read_cmd(
        ctx: typer.Context,
        path: str = typer.Argument(..., help="File path."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        content = read_file(vault, path)
        payload = {"path": path, "content": content}
        raise typer.Exit(emit(payload, content, fmt))

    @_file_app.command("write")
    def file_write_cmd(
        ctx: typer.Context,
        path: str = typer.Argument(..., help="File path."),
        content: str = typer.Option(..., "--content", help="File content."),
        overwrite: bool = typer.Option(False, "--overwrite"),
        template: str | None = typer.Option(None, "--template"),
        title: str | None = typer.Option(None, "--title"),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        target = write_file(
            vault,
            path,
            content=content,
            overwrite=overwrite,
            template=template,
            title=title,
        )
        payload = {"path": rel_to_vault(vault, target)}
        raise typer.Exit(emit(payload, payload["path"], fmt))

    @_file_app.command("append")
    def file_append_cmd(
        ctx: typer.Context,
        path: str = typer.Argument(..., help="File path."),
        content: str = typer.Option(..., "--content", help="Content to append."),
        inline: bool = typer.Option(False, "--inline"),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        target = append_file(vault, path, content, inline=inline)
        payload = {"path": rel_to_vault(vault, target)}
        raise typer.Exit(emit(payload, payload["path"], fmt))

    @_file_app.command("prepend")
    def file_prepend_cmd(
        ctx: typer.Context,
        path: str = typer.Argument(..., help="File path."),
        content: str = typer.Option(..., "--content", help="Content to prepend."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        target = prepend_file(vault, path, content)
        payload = {"path": rel_to_vault(vault, target)}
        raise typer.Exit(emit(payload, payload["path"], fmt))

    @_file_app.command("move")
    def file_move_cmd(
        ctx: typer.Context,
        old: str = typer.Argument(..., help="Old path."),
        new: str = typer.Argument(..., help="New path."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        target = move_file(vault, old, new)
        payload = {"path": rel_to_vault(vault, target)}
        raise typer.Exit(emit(payload, payload["path"], fmt))

    @_file_app.command("rename")
    def file_rename_cmd(
        ctx: typer.Context,
        old: str = typer.Argument(..., help="Old path."),
        new: str = typer.Argument(..., help="New name."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        target = rename_file(vault, old, new)
        payload = {"path": rel_to_vault(vault, target)}
        raise typer.Exit(emit(payload, payload["path"], fmt))

    @_file_app.command("delete")
    def file_delete_cmd(
        ctx: typer.Context,
        path: str = typer.Argument(..., help="File path."),
        permanent: bool = typer.Option(False, "--permanent"),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        result = delete_file(vault, path, permanent=permanent)
        payload = {"result": result}
        raise typer.Exit(emit(payload, result, fmt))

    @_file_app.command("open")
    def file_open_cmd(
        ctx: typer.Context,
        path: str = typer.Argument(..., help="File path."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        target = resolve_existing_path(vault, path)
        uri = open_file(load_runtime_config(vault), target)
        payload = {"path": rel_to_vault(vault, target), "uri": uri}
        raise typer.Exit(emit(payload, uri, fmt))

    @_file_app.command("search")
    def file_search_cmd(
        ctx: typer.Context,
        query: str = typer.Option(..., "--query", help="Search query."),
        path: str | None = typer.Option(None, "--path", help="Subpath."),
        limit: int = typer.Option(100, "--limit", help="Max results."),
        context: bool = typer.Option(False, "--context", help="Show context lines."),
        case_sensitive: bool = typer.Option(False, "--case", help="Case-sensitive."),
        fuzzy: bool = typer.Option(False, "--fuzzy", help="Fuzzy search."),
        total: bool = typer.Option(False, "--total"),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        rows = search_files(
            vault,
            query,
            path=path,
            limit=limit,
            context=context,
            case_sensitive=case_sensitive,
            fuzzy=fuzzy,
        )
        _exit_rows(rows, fmt, total=total)
