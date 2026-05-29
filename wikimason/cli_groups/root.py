"""Top-level root commands (version, help, init, query, lint, status, doctor, log, audit)."""  # noqa: E501

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
import typer

from .. import __version__
from ..audit import audit_vault
from ..cli_helpers import (
    _run_doctor,
    _run_lint,
    _vault_from_ctx,
)
from ..cli_output import emit
from ..ingest import doctor_status, ingest_status
from ..logs import append_log
from ..profiles import canonical_profile_name
from ..scaffold import init_vault
from ..search import search_catalog


def register_root(app: typer.Typer) -> None:  # noqa: C901
    """Register top-level commands directly on the root *app*."""

    @app.command(hidden=True)
    def version() -> None:
        print(f"wikimason {__version__}")

    @app.command(
        "help",
        context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
        hidden=True,
    )
    def help_command(ctx: typer.Context) -> None:
        parts = list(ctx.args)
        root = typer.main.get_command(app)
        command = root
        sub_ctx = click.Context(root, info_name="wikimason")
        for part in parts:
            if not hasattr(command, "get_command"):
                raise typer.BadParameter(f"not a command group: {part}")
            next_command = command.get_command(sub_ctx, part)
            if next_command is None:
                raise typer.BadParameter(f"unknown help topic: {' '.join(parts)}")
            command = next_command
            sub_ctx = click.Context(command, info_name=part, parent=sub_ctx)
        click.echo(command.get_help(sub_ctx))
        raise typer.Exit(0)

    @app.command(
        "init",
        context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
    )
    def init_cmd(
        ctx: typer.Context,
        profile: str = typer.Option(
            "markdown",
            "--profile",
            "--tool",
            help="Profile: markdown, obsidian, logseq.",
        ),
        demo: bool = typer.Option(
            False, "--demo", help="Initialize with demo content."
        ),
        env: str | None = typer.Option(None, "--env", help="Named env config."),
    ) -> None:
        # Support legacy positional profile: init markdown /path, init logseq /path
        args = ctx.args
        positional_profile = None
        remaining: list[str] = []
        for token in args:
            if (
                token in {"obsidian", "markdown", "logseq", "generic"}
                and not positional_profile
                and not remaining
            ):
                positional_profile = token
                if token == "generic":
                    print("Deprecated: use `wikimason init markdown`.", file=sys.stderr)
            elif not token.startswith("-"):
                remaining.append(token)
        if positional_profile:
            profile = positional_profile
        target = (
            Path(remaining[0]).expanduser().resolve()
            if remaining
            else Path.cwd().resolve()
        )
        init_vault(target, demo=demo, profile=canonical_profile_name(profile), env=env)
        print(f"initialized {target}")
        raise typer.Exit(0)

    @app.command("query")
    def query_cmd(
        ctx: typer.Context,
        query: str = typer.Argument(None, help="Search query."),
        tag: str | None = typer.Option(None, "--tag", help="Filter by tag."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        rows = search_catalog(vault, query=query or "", tag=tag, limit=10)
        if fmt == "json":
            print(json.dumps(rows, sort_keys=True))
        else:
            for row in rows:
                print(f"{row['title']}\t{row['path']}")
        raise typer.Exit(0)

    @app.command("lint")
    def lint_cmd(
        ctx: typer.Context,
        strict: bool = typer.Option(False, "--strict"),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        _run_lint(ctx, strict, fmt)

    @app.command("status")
    def status_cmd(
        ctx: typer.Context,
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        payload = ingest_status(vault)
        payload["doctor"] = doctor_status(vault)
        text = str(payload["next_action"])
        raise typer.Exit(emit(payload, text, fmt))

    @app.command("doctor")
    def doctor_cmd(
        ctx: typer.Context,
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        _run_doctor(ctx, fmt)

    @app.command("log")
    def log_cmd(
        ctx: typer.Context,
        title: str = typer.Option(..., "--title", help="Log title."),
        details: str = typer.Option(..., "--details", help="Log details."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        path = append_log(vault, title, details)
        print(path.relative_to(vault).as_posix())
        raise typer.Exit(0)

    @app.command("audit")
    def audit_cmd(
        ctx: typer.Context,
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        findings = audit_vault(vault)
        if fmt == "json":
            print(
                json.dumps({"ok": not findings, "findings": findings}, sort_keys=True)
            )
        else:
            print("\n".join(findings))
        raise typer.Exit(0 if not findings else 1)
