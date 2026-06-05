"""Ingest command group."""

from __future__ import annotations

import typer

from ..cli_helpers import CommandOutcome, _finish_command, _vault_from_ctx
from ..cli_output import result_payload
from ..errors import UsageError
from ..ingest import (
    ingest_finish,
    ingest_plan,
    ingest_status,
    render_ingest_finish_json,
)
from ..log_events import audit_event, change_event


def register_ingest(app: typer.Typer) -> None:
    _ingest_app = typer.Typer(help="Ingest operations.")
    app.add_typer(_ingest_app, name="ingest")

    @_ingest_app.callback(invoke_without_command=True)
    def ingest_root(
        ctx: typer.Context,
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        if ctx.invoked_subcommand is not None:
            return
        vault = _vault_from_ctx(ctx)
        raw = ingest_status(vault)
        payload = result_payload(
            command="ingest",
            status=(
                "actionable"
                if raw["next_action"] != "maintain_clean_vault"
                else "clean"
            ),
            data=raw,
        )
        _finish_command(
            ctx,
            CommandOutcome(
                payload=payload,
                text=str(raw["next_action"]),
                command="ingest",
                status=(
                    "actionable"
                    if raw["next_action"] != "maintain_clean_vault"
                    else "clean"
                ),
            ),
            fmt,
            log_event=audit_event(
                "ingest",
                "Checked ingest readiness",
                summary=str(raw["next_action"]),
                status=(
                    "actionable"
                    if raw["next_action"] != "maintain_clean_vault"
                    else "clean"
                ),
            ),
        )

    @_ingest_app.command("status")
    def ingest_status_cmd(
        ctx: typer.Context,
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        raw = ingest_status(vault)
        text = raw["next_action"]
        payload = result_payload(
            command="ingest.status",
            status="actionable" if text != "maintain_clean_vault" else "clean",
            data=raw,
        )
        _finish_command(
            ctx,
            CommandOutcome(
                payload=payload,
                text=str(text),
                command="ingest.status",
                status="actionable" if text != "maintain_clean_vault" else "clean",
            ),
            fmt,
            log_event=audit_event(
                "ingest.status",
                "Checked ingest status",
                summary=str(text),
                status="actionable" if text != "maintain_clean_vault" else "clean",
            ),
        )

    @_ingest_app.command("plan")
    def ingest_plan_cmd(
        ctx: typer.Context,
        sources: list[str] = typer.Argument(None, help="Source paths."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        raw = ingest_plan(vault, sources or [])
        text = (
            raw["source"]
            if isinstance(raw, dict) and "source" in raw
            else "multiple sources"
        )
        payload = result_payload(command="ingest.plan", status="clean", data=raw)
        _finish_command(
            ctx,
            CommandOutcome(
                payload=payload,
                text=text,
                command="ingest.plan",
                status="clean",
            ),
            fmt,
            log_event=audit_event(
                "ingest.plan",
                "Planned ingest",
                summary=text,
                counts={"sources": len(sources or [])},
            ),
        )

    @_ingest_app.command("finish")
    def ingest_finish_cmd(
        ctx: typer.Context,
        accept_covered: bool = typer.Option(False, "--accept-covered"),
        scope: str = typer.Option(
            "changed",
            "--scope",
            help="Validation scope: changed|all.",
        ),
        source: str | None = typer.Option(
            None, "--source", help="Restrict scoped checks to one source path."
        ),
        details: bool = typer.Option(
            False, "--details", help="Include full coverage records."
        ),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        if scope not in {"changed", "all"}:
            raise UsageError("--scope must be one of: changed, all")
        vault = _vault_from_ctx(ctx)
        result = ingest_finish(
            vault, accept_covered=accept_covered, scope=scope, source=source
        )
        raw = render_ingest_finish_json(result, details=details)
        status = "clean"
        if not result.global_lint_ok and result.scoped_lint_ok:
            status = "blocked_by_global_lint"
        elif result.exit_code == 2:
            status = "actionable"
        elif result.exit_code == 1:
            status = "invalid"
        payload = result_payload(
            command="ingest.finish",
            status=status,
            data=raw,
            exit_code=result.exit_code,
        )
        text = "ingest finish clean" if result.exit_code == 0 else result.next_action
        _finish_command(
            ctx,
            CommandOutcome(
                payload=payload,
                text=text,
                command="ingest.finish",
                status=status,
                exit_code=result.exit_code,
            ),
            fmt,
            log_event=change_event(
                "ingest.finish",
                "Finished ingest",
                summary=text,
                counts={"exit_code": result.exit_code},
                metadata={
                    "scope": scope,
                    "accept_covered": str(accept_covered).lower(),
                    "source": source or "",
                },
                status=status,
                exit_code=result.exit_code,
            ),
        )
