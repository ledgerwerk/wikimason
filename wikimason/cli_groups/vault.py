"""Vault command group."""

from __future__ import annotations

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
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        target = path or Path.cwd().resolve()
        init_vault(target, demo=demo, profile=canonical_profile_name(profile), env=env)
        payload = {
            "path": str(target),
            "profile": canonical_profile_name(profile),
            "config_path": str(target / "wikimason.toml"),
            "env": env,
            "demo": demo,
        }
        raise typer.Exit(emit(payload, f"initialized {target}", fmt))

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
        payload = {
            "updated_source_count": result.updated_source_count,
            "catalog_count": result.catalog_count,
        }
        text = f"updated_source_count={result.updated_source_count}"
        raise typer.Exit(emit(payload, text, fmt))

    @_vault_app.command("lint")
    def vault_lint_cmd(
        ctx: typer.Context,
        strict: bool = typer.Option(False, "--strict"),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        _run_lint(ctx, strict, fmt, command="vault.lint")

    @_vault_app.command("maintain")
    def vault_maintain_cmd(
        ctx: typer.Context,
        log: str | None = typer.Option(None, "--log", help="Log message."),
        accept_covered: bool = typer.Option(
            False, "--accept-covered", help="Accept covered sources."
        ),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        doctor_payload = _doctor_payload(vault)
        if not doctor_payload["ok"]:
            payload = {"ok": False, "doctor": doctor_payload}
            raise typer.Exit(
                emit(
                    payload,
                    _doctor_text(doctor_payload),
                    fmt,
                    exit_code=1,
                    command="vault.maintain",
                    status="invalid",
                )
            )
        if not accept_covered:
            delta_payload, delta_errors = source_delta(vault)
            if delta_errors:
                raise typer.Exit(
                    emit(
                        {"ok": False, "errors": delta_errors},
                        "\n".join(delta_errors),
                        fmt,
                        exit_code=1,
                        command="vault.maintain",
                        status="error",
                    )
                )
            assert delta_payload is not None
            if int(str(delta_payload["actionable_count"])) > 0:
                raise typer.Exit(
                    emit(
                        {
                            "ok": False,
                            "reason": "actionable_source_delta",
                            "delta": delta_payload,
                        },
                        "actionable source delta",
                        fmt,
                        exit_code=2,
                        command="vault.maintain",
                        status="actionable",
                    )
                )
        result = build_vault(vault)
        lint_errors = lint_vault(vault)
        source_scan_payload(vault, update=True, accept_covered=accept_covered)
        source_lint_errors = source_lint(vault)
        audit_findings = audit_vault(vault)
        if log:
            append_log(vault, "maintain", log)
        from ..source_delta import source_coverage_report

        coverage = source_coverage_report(vault)
        lint_ok = not lint_errors
        source_lint_ok = not source_lint_errors
        links_ok = True  # links check runs in lint
        agents_ok = not audit_findings
        overall_ok = lint_ok and source_lint_ok and agents_ok
        payload = {
            "doctor_ok": True,
            "source_lint_ok": source_lint_ok,
            "lint_ok": lint_ok,
            "links_ok": links_ok,
            "agents_ok": agents_ok,
            "ok": overall_ok,
            "sources": {
                "total": coverage["total"],
                "covered": coverage["covered"],
                "actionable_count": (coverage["total"] - coverage["covered"]),
                "coverage_percent": coverage["coverage_percent"],
            },
            "catalog_count": result.catalog_count,
            "updated_source_count": result.updated_source_count,
            "lint_errors": lint_errors,
            "source_lint_errors": source_lint_errors,
            "audit_findings": audit_findings,
        }
        next_action = "maintain_clean_vault" if overall_ok else "repair_required"
        text = "maintain passed" if overall_ok else "maintain failed"
        exit_code = 0 if overall_ok else 1
        if not overall_ok and fmt != "json":
            text = "\n".join(lint_errors + source_lint_errors + audit_findings)
        raise typer.Exit(
            emit(
                payload,
                text,
                fmt,
                exit_code=exit_code,
                command="vault.maintain",
                status="clean" if overall_ok else "invalid",
                next_action=next_action,
            )
        )
