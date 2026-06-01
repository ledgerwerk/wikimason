"""Top-level root commands (version, help, init, query, lint, status, doctor, audit)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import click
import typer

from .. import __version__
from ..audit import audit_vault
from ..cli_helpers import (
    CommandOutcome,
    _finish_command,
    _run_doctor,
    _run_lint,
    _vault_from_ctx,
)
from ..cli_output import emit
from ..ingest import doctor_status, ingest_status
from ..log_events import audit_event, change_event, lint_event
from ..logs import append_log_event
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
        command: Any = root
        sub_ctx: Any = click.Context(cast(Any, root), info_name="wikimason")
        for part in parts:
            if not hasattr(command, "get_command"):
                raise typer.BadParameter(f"not a command group: {part}")
            next_command = command.get_command(sub_ctx, part)
            if next_command is None:
                raise typer.BadParameter(f"unknown help topic: {' '.join(parts)}")
            command = next_command
            sub_ctx = click.Context(command, info_name=part, parent=sub_ctx)
        click.echo(cast(Any, command).get_help(sub_ctx))
        raise typer.Exit(0)

    @app.command("init")
    def init_cmd(
        ctx: typer.Context,
        profile_or_path: str | None = typer.Argument(
            None, help="Profile (markdown|obsidian|logseq) or target path."
        ),
        path: Path | None = typer.Argument(None, help="Target path."),
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
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        profile_name = profile
        target = Path.cwd().resolve()
        if profile_or_path in {"markdown", "obsidian", "logseq"}:
            profile_name = str(profile_or_path)
            target = path.expanduser().resolve() if path else Path.cwd().resolve()
        else:
            if profile_or_path:
                target = Path(profile_or_path).expanduser().resolve()
            elif path is not None:
                target = path.expanduser().resolve()

        init_vault(
            target, demo=demo, profile=canonical_profile_name(profile_name), env=env
        )
        payload = {
            "path": str(target),
            "profile": canonical_profile_name(profile_name),
            "config_path": str(target / "wikimason.toml"),
            "env": env,
            "demo": demo,
        }
        append_log_event(
            target,
            change_event(
                "init",
                "Initialized vault",
                summary=f"initialized {target}",
                paths=("Wiki/log.md",),
                metadata={
                    "profile": canonical_profile_name(profile_name),
                    "demo": str(demo).lower(),
                },
            ),
        )
        raise typer.Exit(
            emit(
                payload, f"initialized {target}", fmt, command="init", status="changed"
            )
        )

    @app.command("query")
    def query_cmd(
        ctx: typer.Context,
        query: str = typer.Argument(None, help="Search query."),
        tag: str | None = typer.Option(None, "--tag", help="Filter by tag."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        rows = search_catalog(vault, query=query or "", tag=tag, limit=10)
        text = "\n".join(f"{row['title']}\t{row['path']}" for row in rows)
        append_log_event(
            vault,
            audit_event(
                "query",
                "Searched catalog",
                summary=f"Query: {query or ''}",
                counts={"rows": len(rows)},
                metadata={"tag": tag or ""},
            ),
        )
        raise typer.Exit(emit(rows, text, fmt))

    @app.command("lint")
    def lint_cmd(
        ctx: typer.Context,
        strict: bool = typer.Option(False, "--strict"),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        outcome = _run_lint(ctx, strict, command="lint")
        payload = outcome.payload["data"] if isinstance(outcome.payload, dict) else {}
        _finish_command(
            ctx,
            outcome,
            fmt,
            log_event=lint_event("lint", payload, strict=strict),
        )

    @app.command("status")
    def status_cmd(
        ctx: typer.Context,
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        payload = ingest_status(vault)
        payload["doctor"] = doctor_status(vault)
        text = str(payload["next_action"])
        _finish_command(
            ctx,
            CommandOutcome(
                payload=payload,
                text=text,
                command="status",
                status=payload.get("next_action", "clean"),
            ),
            fmt,
            log_event=audit_event(
                "status",
                "Checked vault status",
                summary=text,
                status=str(payload.get("next_action", "clean")),
            ),
        )

    @app.command("doctor")
    def doctor_cmd(
        ctx: typer.Context,
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        outcome = _run_doctor(ctx, command="doctor")
        payload = outcome.payload["data"] if isinstance(outcome.payload, dict) else {}
        checks = payload.get("checks", []) if isinstance(payload, dict) else []
        _finish_command(
            ctx,
            outcome,
            fmt,
            log_event=audit_event(
                "doctor",
                "Ran doctor checks",
                summary=outcome.text,
                counts={"checks": len(checks)},
                status=outcome.status,
                exit_code=outcome.exit_code,
            ),
        )

    @app.command("audit")
    def audit_cmd(
        ctx: typer.Context,
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        findings = audit_vault(vault)
        raw_payload = {"ok": not findings, "findings": findings}
        text = "\n".join(findings)
        payload = {
            "schema_version": 1,
            "ok": not findings,
            "command": "audit",
            "status": "clean" if not findings else "invalid",
            "exit_code": 0 if not findings else 1,
            "data": raw_payload,
            "warnings": [],
            "errors": [],
            "next_action": None,
            **raw_payload,
        }
        _finish_command(
            ctx,
            CommandOutcome(
                payload=payload,
                text=text or "audit clean",
                command="audit",
                status="clean" if not findings else "invalid",
                exit_code=0 if not findings else 1,
            ),
            fmt,
            log_event=audit_event(
                "audit",
                "Audited vault",
                summary=text or "Audit clean.",
                counts={"findings": len(findings)},
                status="clean" if not findings else "invalid",
                exit_code=0 if not findings else 1,
            ),
        )
