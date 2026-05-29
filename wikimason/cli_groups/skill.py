"""Skill command group."""

from __future__ import annotations

from pathlib import Path

import typer

from ..skills import skill_install, skill_path


def register_skill(app: typer.Typer) -> None:
    _skill_app = typer.Typer(help="Skill management.")
    app.add_typer(_skill_app, name="skill")

    @_skill_app.command("path")
    def skill_path_cmd() -> None:
        repo_root = Path(__file__).resolve().parent.parent.parent
        print(skill_path(repo_root))
        raise typer.Exit(0)

    @_skill_app.command("install")
    def skill_install_cmd(
        target: str = typer.Option(..., "--target", help="Install target path."),
        symlink: bool = typer.Option(False, "--symlink"),
    ) -> None:
        repo_root = Path(__file__).resolve().parent.parent.parent
        out = skill_install(
            repo_root, Path(target).expanduser().resolve(), symlink=symlink
        )
        print(out)
        raise typer.Exit(0)
