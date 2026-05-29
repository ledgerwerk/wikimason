"""Migrate command group."""

from __future__ import annotations

from pathlib import Path

import typer

from ..cli_helpers import _run_migration


def register_migrate(app: typer.Typer) -> None:
    _migrate_app = typer.Typer(help="Profile migration.")
    app.add_typer(_migrate_app, name="migrate")

    @_migrate_app.command("logseq-to-obsidian")
    def migrate_logseq_to_obsidian(
        ctx: typer.Context,
        from_path: Path = typer.Option(..., "--from", help="Source vault."),
        to_path: Path = typer.Option(..., "--to", help="Target vault."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        _run_migration(from_path, to_path, "obsidian", fmt)

    @_migrate_app.command("obsidian-to-logseq")
    def migrate_obsidian_to_logseq(
        ctx: typer.Context,
        from_path: Path = typer.Option(..., "--from", help="Source vault."),
        to_path: Path = typer.Option(..., "--to", help="Target vault."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        _run_migration(from_path, to_path, "logseq", fmt)

    @_migrate_app.command("markdown-to-logseq")
    def migrate_markdown_to_logseq(
        ctx: typer.Context,
        from_path: Path = typer.Option(..., "--from", help="Source vault."),
        to_path: Path = typer.Option(..., "--to", help="Target vault."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        _run_migration(from_path, to_path, "logseq", fmt)

    @_migrate_app.command("logseq-to-markdown")
    def migrate_logseq_to_markdown(
        ctx: typer.Context,
        from_path: Path = typer.Option(..., "--from", help="Source vault."),
        to_path: Path = typer.Option(..., "--to", help="Target vault."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        _run_migration(from_path, to_path, "markdown", fmt)
