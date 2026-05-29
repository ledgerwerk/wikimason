"""Agents command group."""

from __future__ import annotations

import typer

from ..agents import compile_agents_md, compute_input_hashes, write_agents_md
from ..cli_helpers import _vault_from_ctx
from ..cli_output import emit
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
        target = vault / "AGENTS.md"
        compiled = compile_agents_md(vault)
        if check:
            ok = target.exists() and target.read_text(encoding="utf-8") == compiled
            hashes = compute_input_hashes(vault)
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
        raise typer.Exit(emit(payload, str(payload["path"]), fmt))

    @_agents_app.command("check")
    def agents_check_cmd(
        ctx: typer.Context,
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        target = vault / "AGENTS.md"
        compiled = compile_agents_md(vault)
        ok = target.exists() and target.read_text(encoding="utf-8") == compiled
        hashes = compute_input_hashes(vault)
        payload = {
            "ok": ok,
            "path": rel_to_vault(vault, target),
            "check": True,
            "input_hashes": hashes,
        }
        text = "AGENTS.md up to date" if ok else "AGENTS.md is stale"
        raise typer.Exit(emit(payload, text, fmt, exit_code=0 if ok else 1))
