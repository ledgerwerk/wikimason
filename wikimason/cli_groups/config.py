"""Config command group."""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

import typer

from ..cli_helpers import (
    _config_payload,
    _config_text,
    _write_migrated_config,
)
from ..cli_output import emit
from ..config import (
    default_config,
    env_config_path,
    find_wiki_root,
    looks_like_wiki_root,
)
from ..context import resolve_context
from ..errors import UsageError
from ..profiles import canonical_profile_name
from ..schema import load_vault_schema


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

    @_config_app.command("migrate")
    def config_migrate(
        ctx: typer.Context,
        path: Path = typer.Argument(None, help="Target wiki root."),
        profile: str = typer.Option(None, "--profile", "--tool", help="Profile."),
        env_name: str | None = typer.Option(None, "--env", help="Named env config."),
        force: bool = typer.Option(False, "--force", help="Overwrite existing config."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        state = ctx.find_root().obj
        requested_root = path or (Path(str(state.vault)) if state.vault else Path.cwd())
        target = find_wiki_root(requested_root) or requested_root
        if not looks_like_wiki_root(target):
            raise UsageError("config migrate requires an existing wiki root")
        inferred_tool = "obsidian" if (target / ".obsidian").exists() else "markdown"
        actual_profile = canonical_profile_name(profile or inferred_tool)
        base_config = default_config(actual_profile, target, name=target.name)
        schema = load_vault_schema(target, config=base_config)
        writes = [{"path": target / "wikimason.toml", "name": target.name, "root": "."}]
        if env_name:
            writes.append(
                {
                    "path": env_config_path(env_name),
                    "name": env_name,
                    "root": str(target),
                }
            )
        existing = [w["path"] for w in writes if w["path"].exists()]
        if existing and not force:
            raise UsageError(f"config already exists: {existing[0]}")
        written: list[str] = []
        for item in writes:
            config = default_config(actual_profile, target, name=item["name"])
            _write_migrated_config(
                item["path"], config, schema, root_value=item["root"]
            )
            written.append(str(item["path"].expanduser().resolve()))
        payload = {"root": str(target), "profile": actual_profile, "written": written}
        raise typer.Exit(emit(payload, "\n".join(written), fmt))
