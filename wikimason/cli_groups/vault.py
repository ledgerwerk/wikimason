"""Vault command group."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from ..audit import audit_vault
from ..build import build_vault
from ..cli_helpers import (
    _doctor_payload,
    _doctor_text,
    _run_doctor,
    _run_lint,
    _vault_from_ctx,
)
from ..cli_output import emit
from ..lint import lint_vault
from ..logs import append_log
from ..profiles import canonical_profile_name
from ..scaffold import init_vault
from ..sources import source_delta, source_lint, source_scan_payload
from ..vault_registry import VaultRegistry


def register_vault(app: typer.Typer) -> None:
    _vault_app = typer.Typer(help="Vault management.")
    app.add_typer(_vault_app, name="vault")

    @_vault_app.command("init")
    def vault_init_cmd(
        ctx: typer.Context,
        path: Path = typer.Argument(None, help="Target path."),
        profile: str = typer.Option("markdown", "--profile", "--tool", help="Profile."),
        demo: bool = typer.Option(False, "--demo", help="With demo content."),
        env: str | None = typer.Option(None, "--env", help="Named env."),
    ) -> None:
        target = path or Path.cwd().resolve()
        init_vault(target, demo=demo, profile=canonical_profile_name(profile), env=env)
        print(f"initialized {target}")
        raise typer.Exit(0)

    @_vault_app.command("list")
    def vault_list_cmd(
        ctx: typer.Context,
        total: bool = typer.Option(False, "--total"),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vaults = VaultRegistry.default().load().get("vaults", {})
        if not isinstance(vaults, dict):
            vaults = {}
        if total:
            raise typer.Exit(emit({"total": len(vaults)}, str(len(vaults)), fmt))
        payload = {
            name: value.get("path")
            for name, value in vaults.items()
            if isinstance(value, dict) and "path" in value
        }
        raise typer.Exit(emit(payload, "\n".join(sorted(payload)), fmt))

    @_vault_app.command("register")
    def vault_register_cmd(
        ctx: typer.Context,
        name: str = typer.Argument(..., help="Vault name."),
        path: Path = typer.Argument(..., help="Vault path."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        target = path.expanduser().resolve()
        VaultRegistry.default().register(name, target)
        payload = {"name": name, "path": str(target)}
        raise typer.Exit(emit(payload, f"registered {name}", fmt))

    @_vault_app.command("doctor")
    def vault_doctor_cmd(
        ctx: typer.Context,
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        _run_doctor(ctx, fmt)

    @_vault_app.command("build")
    def vault_build_cmd(
        ctx: typer.Context,
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        result = build_vault(vault)
        if fmt == "json":
            print(
                json.dumps(
                    {
                        "updated_source_count": result.updated_source_count,
                        "catalog_count": result.catalog_count,
                    },
                    sort_keys=True,
                )
            )
        else:
            print(f"updated_source_count={result.updated_source_count}")
        raise typer.Exit(0)

    @_vault_app.command("lint")
    def vault_lint_cmd(
        ctx: typer.Context,
        strict: bool = typer.Option(False, "--strict"),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        _run_lint(ctx, strict, fmt)

    @_vault_app.command("maintain")
    def vault_maintain_cmd(
        ctx: typer.Context,
        log: str | None = typer.Option(None, "--log", help="Log message."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        doctor_payload = _doctor_payload(vault)
        if not doctor_payload["ok"]:
            if fmt == "json":
                print(
                    json.dumps({"ok": False, "doctor": doctor_payload}, sort_keys=True)
                )
            else:
                print(_doctor_text(doctor_payload))
            raise typer.Exit(1)
        delta_payload, delta_errors = source_delta(vault)
        if delta_errors:
            print("\n".join(delta_errors))
            raise typer.Exit(1)
        assert delta_payload is not None
        if int(str(delta_payload["actionable_count"])) > 0:
            raise typer.Exit(
                emit(
                    {
                        "ok": False,
                        "reason": "actionable_source_delta",
                        "delta": delta_payload,
                    },
                    json.dumps(delta_payload, sort_keys=True),
                    fmt,
                    exit_code=2,
                )
            )
        result = build_vault(vault)
        lint_errors = lint_vault(vault)
        source_scan_payload(vault, update=True, accept_covered=True)
        source_lint_errors = source_lint(vault)
        audit_findings = audit_vault(vault)
        if log:
            append_log(vault, "maintain", log)
        payload = {
            "ok": not lint_errors and not source_lint_errors and not audit_findings,
            "updated_source_count": result.updated_source_count,
            "catalog_count": result.catalog_count,
            "lint_errors": lint_errors,
            "source_lint_errors": source_lint_errors,
            "audit_findings": audit_findings,
        }
        text = "maintain passed"
        exit_code = 0 if payload["ok"] else 1
        if not payload["ok"] and fmt != "json":
            text = "\n".join(lint_errors + source_lint_errors + audit_findings)
        raise typer.Exit(emit(payload, text, fmt, exit_code=exit_code))
