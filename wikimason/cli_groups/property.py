"""Property command group."""

from __future__ import annotations

import json

import typer

from ..cli_helpers import _vault_from_ctx
from ..cli_output import emit
from ..config import load_runtime_config
from ..files import resolve_existing_path
from ..paths import rel_to_vault
from ..properties import (
    list_property_names,
    read_property,
    remove_property,
    set_property,
    update_aliases,
)


def register_property(app: typer.Typer) -> None:
    _property_app = typer.Typer(help="Property operations.")
    app.add_typer(_property_app, name="property")

    @_property_app.command("list")
    def property_list_cmd(
        ctx: typer.Context,
        path: str = typer.Argument(None, help="File path."),
        total: bool = typer.Option(False, "--total"),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        config = load_runtime_config(vault)
        target = resolve_existing_path(vault, path) if path else None
        rows = list_property_names(vault, target, config=config)
        if total:
            raise typer.Exit(emit({"total": len(rows)}, str(len(rows)), fmt))
        raise typer.Exit(emit(rows, "\n".join(rows), fmt))

    @_property_app.command("get")
    def property_get_cmd(
        ctx: typer.Context,
        path: str = typer.Argument(..., help="File path."),
        key: str = typer.Argument(..., help="Property key."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        config = load_runtime_config(vault)
        target = resolve_existing_path(vault, path)
        text = target.read_text(encoding="utf-8")
        value = read_property(text, key, config=config, path=target)
        payload = {"path": rel_to_vault(vault, target), "key": key, "value": value}
        rendered = json.dumps(value) if isinstance(value, (list, dict)) else str(value)
        raise typer.Exit(emit(payload, rendered, fmt))

    @_property_app.command("set")
    def property_set_cmd(
        ctx: typer.Context,
        path: str = typer.Argument(..., help="File path."),
        key: str = typer.Argument(..., help="Property key."),
        value: str = typer.Argument(..., help="Property value."),
        type_hint: str | None = typer.Option(None, "--type", help="Type hint."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        config = load_runtime_config(vault)
        target = resolve_existing_path(vault, path)
        text = target.read_text(encoding="utf-8")
        updated = set_property(text, key, value, type_hint, config=config, path=target)
        target.write_text(updated, encoding="utf-8")
        raise typer.Exit(emit({"ok": True}, "ok", fmt))

    @_property_app.command("remove")
    def property_remove_cmd(
        ctx: typer.Context,
        path: str = typer.Argument(..., help="File path."),
        key: str = typer.Argument(..., help="Property key."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        config = load_runtime_config(vault)
        target = resolve_existing_path(vault, path)
        text = target.read_text(encoding="utf-8")
        target.write_text(
            remove_property(text, key, config=config, path=target), encoding="utf-8"
        )
        raise typer.Exit(emit({"ok": True}, "ok", fmt))

    @_property_app.command("aliases")
    def property_aliases_cmd(
        ctx: typer.Context,
        path: str = typer.Argument(..., help="File path."),
        add: list[str] = typer.Option([], "--add", help="Aliases to add."),
        remove: list[str] = typer.Option([], "--remove", help="Aliases to remove."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        config = load_runtime_config(vault)
        target = resolve_existing_path(vault, path)
        text = target.read_text(encoding="utf-8")
        updated = update_aliases(
            text, add=tuple(add), remove=tuple(remove), config=config, path=target
        )
        target.write_text(updated, encoding="utf-8")
        aliases = read_property(updated, "aliases", config=config, path=target)
        payload = {"path": rel_to_vault(vault, target), "aliases": aliases}
        rendered = json.dumps(aliases) if isinstance(aliases, list) else str(aliases)
        raise typer.Exit(emit(payload, rendered, fmt))
