"""Agents command group."""

from __future__ import annotations

import typer

from ..agents import (
    agents_md_up_to_date,
    compute_input_hashes,
    write_agents_md,
)
from ..cli_helpers import CommandOutcome, _finish_command, _vault_from_ctx
from ..cli_output import emit
from ..config import load_runtime_config
from ..log_events import change_event
from ..paths import rel_to_vault


def register_agents(app: typer.Typer) -> None:
    _agents_app = typer.Typer(help="Agents documentation.")
    app.add_typer(_agents_app, name="agents")

    @_agents_app.command("compile")
    def agents_compile_cmd(
        ctx: typer.Context,
        check: bool = typer.Option(False, "--check"),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        config = load_runtime_config(vault)
        target = vault / config.paths.agents
        if check:
            ok = agents_md_up_to_date(vault, config=config)
            hashes = compute_input_hashes(vault, config=config)
            payload = {
                "ok": ok,
                "path": rel_to_vault(vault, target),
                "check": True,
                "input_hashes": hashes,
            }
            text = "AGENTS.md up to date" if ok else "AGENTS.md is stale"
            raise typer.Exit(emit(payload, text, fmt, exit_code=0 if ok else 1))
        out = write_agents_md(vault, force=True)
        payload = {"ok": True, "path": rel_to_vault(vault, out), "check": False}
        _finish_command(
            ctx,
            CommandOutcome(
                payload=payload,
                text=str(payload["path"]),
                command="agents.compile",
                status="changed",
            ),
            fmt,
            log_event=change_event(
                "agents.compile",
                "Compiled AGENTS.md",
                summary=str(payload["path"]),
                paths=(str(payload["path"]),),
            ),
        )

    @_agents_app.command("check")
    def agents_check_cmd(
        ctx: typer.Context,
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        config = load_runtime_config(vault)
        target = vault / config.paths.agents
        ok = agents_md_up_to_date(vault, config=config)
        hashes = compute_input_hashes(vault, config=config)
        payload = {
            "ok": ok,
            "path": rel_to_vault(vault, target),
            "check": True,
            "input_hashes": hashes,
        }
        text = "AGENTS.md up to date" if ok else "AGENTS.md is stale"
        raise typer.Exit(emit(payload, text, fmt, exit_code=0 if ok else 1))
