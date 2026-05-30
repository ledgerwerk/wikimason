"""Config command group."""

from __future__ import annotations

import os
import shlex
import subprocess

import typer

from ..cli_helpers import (
    _config_payload,
    _config_text,
)
from ..cli_output import emit
from ..context import resolve_context
from ..errors import UsageError


def register_config(app: typer.Typer) -> None:
    _config_app = typer.Typer(help="Configuration management.")
    app.add_typer(_config_app, name="config")

    @_config_app.command("show")
    def config_show(
        ctx: typer.Context,
        fmt: str = typer.Option(
            "text", "--format", help="Output format: text or json."
        ),
    ) -> None:
        state = ctx.find_root().obj
        context = resolve_context(
            vault=str(state.vault) if state.vault else None,
            env=state.env,
            config_path=str(state.config_path) if state.config_path else None,
        )
        payload = _config_payload(context)
        raise typer.Exit(emit(payload, _config_text(payload), fmt))

    @_config_app.command("edit")
    def config_edit(
        ctx: typer.Context,
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        state = ctx.find_root().obj
        context = resolve_context(
            vault=str(state.vault) if state.vault else None,
            env=state.env,
            config_path=str(state.config_path) if state.config_path else None,
        )
        if context.config_path is None:
            raise UsageError("config edit requires a resolved config file")
        editor = os.environ.get("EDITOR")
        if not editor:
            raise UsageError("config edit requires $EDITOR")
        command = [*shlex.split(editor), str(context.config_path)]
        subprocess.run(command, check=True)
        payload = {"path": str(context.config_path)}
        raise typer.Exit(emit(payload, payload["path"], fmt))

    @_config_app.command("validate")
    def config_validate(
        ctx: typer.Context,
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        state = ctx.find_root().obj
        context = resolve_context(
            vault=str(state.vault) if state.vault else None,
            env=state.env,
            config_path=str(state.config_path) if state.config_path else None,
        )
        payload = _config_payload(context)
        payload["ok"] = True
        raise typer.Exit(emit(payload, "config valid", fmt))
