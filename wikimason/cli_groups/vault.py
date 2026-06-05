"""Vault command group."""

from __future__ import annotations

from pathlib import Path

import typer

from ..agents import agents_md_up_to_date
from ..audit import audit_vault
from ..build import build_vault
from ..cli_helpers import (
    CommandOutcome,
    _append_command_log,
    _doctor_payload,
    _doctor_text,
    _finish_command,
    _run_doctor,
    _run_lint,
    _vault_from_ctx,
)
from ..cli_output import emit
from ..config import load_runtime_config
from ..lint import lint_vault
from ..log_events import audit_event, change_event, lint_event
from ..logs import append_log_event, check_log
from ..profiles import canonical_profile_name
from ..scaffold import init_vault
from ..sources import source_delta, source_lint, source_scan_payload
from ..vault_registry import VaultRegistry


def _finish_maintain(
    ctx: typer.Context,
    outcome: CommandOutcome,
    fmt: str,
    *,
    log_event: object | None = None,
) -> None:
    vault = _vault_from_ctx(ctx)
    warnings = list(outcome.warnings)
    text = outcome.text
    payload = (
        dict(outcome.payload)
        if isinstance(outcome.payload, dict)
        else {"result": outcome.payload}
    )
    if log_event is not None:
        try:
            _append_command_log(ctx, log_event)
        except OSError as exc:
            message = f"log write failed: {exc}"
            warnings.append(message)
            if fmt != "json":
                text = f"{text}\nwarning: {message}" if text else f"warning: {message}"
    log_result = check_log(vault, config=load_runtime_config(vault))
    payload["log_check"] = log_result
    exit_code = outcome.exit_code
    status = outcome.status
    if not bool(log_result.get("ok", False)):
        warnings.append("log check found issues")
        if exit_code == 0:
            exit_code = 1
            if status == "clean":
                status = "invalid"
        if fmt != "json":
            text = (
                f"{text}\nlog check found issues" if text else "log check found issues"
            )
    raise typer.Exit(
        emit(
            payload,
            text,
            fmt,
            exit_code=exit_code,
            command=outcome.command,
            status=status,
            warnings=warnings,
            errors=list(outcome.errors),
            next_action=outcome.next_action,
        )
    )


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
        append_log_event(
            target,
            change_event(
                "vault.init",
                "Initialized vault",
                summary=f"initialized {target}",
                paths=("Wiki/log.md",),
                metadata={
                    "profile": canonical_profile_name(profile),
                    "demo": str(demo).lower(),
                },
            ),
            config=load_runtime_config(target),
        )
        raise typer.Exit(
            emit(
                payload,
                f"initialized {target}",
                fmt,
                command="vault.init",
                status="changed",
            )
        )

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
        append_log_event(
            target,
            change_event(
                "vault.register",
                "Registered vault",
                summary=f"{name}: {target}",
                metadata={"name": name, "path": str(target)},
            ),
            config=load_runtime_config(target),
        )
        raise typer.Exit(
            emit(
                payload,
                f"registered {name}",
                fmt,
                command="vault.register",
                status="changed",
            )
        )

    @_vault_app.command("doctor")
    def vault_doctor_cmd(
        ctx: typer.Context,
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        outcome = _run_doctor(ctx, command="vault.doctor")
        payload = outcome.payload["data"] if isinstance(outcome.payload, dict) else {}
        checks = payload.get("checks", []) if isinstance(payload, dict) else []
        _finish_command(
            ctx,
            outcome,
            fmt,
            log_event=audit_event(
                "vault.doctor",
                "Ran vault doctor checks",
                summary=outcome.text,
                counts={"checks": len(checks)},
                status=outcome.status,
                exit_code=outcome.exit_code,
            ),
        )

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
        _finish_command(
            ctx,
            CommandOutcome(
                payload=payload,
                text=text,
                command="vault.build",
                status="changed",
            ),
            fmt,
            log_event=change_event(
                "vault.build",
                "Built vault",
                summary=text,
                counts={
                    "updated_source_count": result.updated_source_count,
                    "catalog_count": result.catalog_count,
                },
            ),
        )

    @_vault_app.command("lint")
    def vault_lint_cmd(
        ctx: typer.Context,
        strict: bool = typer.Option(False, "--strict"),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        outcome = _run_lint(ctx, strict, command="vault.lint")
        payload = outcome.payload["data"] if isinstance(outcome.payload, dict) else {}
        _finish_command(
            ctx,
            outcome,
            fmt,
            log_event=lint_event("vault.lint", payload, strict=strict),
        )

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
            _finish_maintain(
                ctx,
                CommandOutcome(
                    payload={
                        "ok": False,
                        "doctor": doctor_payload,
                    },
                    text=_doctor_text(doctor_payload),
                    command="vault.maintain",
                    status="invalid",
                    exit_code=1,
                ),
                fmt,
                log_event=change_event(
                    "vault.maintain",
                    "Blocked vault maintenance",
                    summary=_doctor_text(doctor_payload),
                    status="invalid",
                    exit_code=1,
                    metadata={"reason": "doctor_failed"},
                ),
            )
        if not accept_covered:
            delta_payload, delta_errors = source_delta(vault)
            if delta_errors:
                _finish_maintain(
                    ctx,
                    CommandOutcome(
                        payload={"ok": False, "errors": delta_errors},
                        text="\n".join(delta_errors),
                        command="vault.maintain",
                        status="error",
                        exit_code=1,
                        errors=tuple(delta_errors),
                    ),
                    fmt,
                    log_event=change_event(
                        "vault.maintain",
                        "Failed vault maintenance",
                        summary="\n".join(delta_errors),
                        status="error",
                        exit_code=1,
                        metadata={"reason": "source_delta_error"},
                    ),
                )
            assert delta_payload is not None
            if int(str(delta_payload["actionable_count"])) > 0:
                _finish_maintain(
                    ctx,
                    CommandOutcome(
                        payload={
                            "ok": False,
                            "reason": "actionable_source_delta",
                            "delta": delta_payload,
                        },
                        text="actionable source delta",
                        command="vault.maintain",
                        status="actionable",
                        exit_code=2,
                        next_action="repair_required",
                    ),
                    fmt,
                    log_event=change_event(
                        "vault.maintain",
                        "Blocked vault maintenance",
                        summary="actionable source delta",
                        counts={
                            "actionable": int(str(delta_payload["actionable_count"]))
                        },
                        status="actionable",
                        exit_code=2,
                        metadata={"reason": "actionable_source_delta"},
                    ),
                )
        result = build_vault(vault)
        lint_errors = lint_vault(vault)
        source_scan_payload(vault, update=True, accept_covered=accept_covered)
        source_lint_errors = source_lint(vault)
        audit_findings = audit_vault(vault)
        from ..source_delta import source_coverage_report

        coverage = source_coverage_report(vault)
        lint_ok = not lint_errors
        source_lint_ok = not source_lint_errors
        links_ok = True  # links check runs in lint
        agents_ok = agents_md_up_to_date(vault)
        audit_ok = not audit_findings
        overall_ok = lint_ok and source_lint_ok and agents_ok and audit_ok
        payload = {
            "doctor_ok": True,
            "source_lint_ok": source_lint_ok,
            "lint_ok": lint_ok,
            "links_ok": links_ok,
            "agents_ok": agents_ok,
            "audit_ok": audit_ok,
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
        failed_checks = []
        if not lint_ok:
            failed_checks.append("lint")
        if not source_lint_ok:
            failed_checks.append("source_lint")
        if not agents_ok:
            failed_checks.append("agents")
        if not audit_ok:
            failed_checks.append("audit")
        payload["failed_checks"] = failed_checks
        next_action = "maintain_clean_vault" if overall_ok else "repair_required"
        text = "maintain passed" if overall_ok else "maintain failed"
        exit_code = 0 if overall_ok else 1
        if not overall_ok and fmt != "json":
            text = "\n".join(lint_errors + source_lint_errors + audit_findings)
        _finish_maintain(
            ctx,
            CommandOutcome(
                payload=payload,
                text=text,
                command="vault.maintain",
                status="clean" if overall_ok else "invalid",
                exit_code=exit_code,
                next_action=next_action,
            ),
            fmt,
            log_event=change_event(
                "vault.maintain",
                "Ran vault maintenance",
                summary=(
                    "Built catalog, linted vault, scanned sources, "
                    "checked audit findings."
                ),
                counts={
                    "updated_source_count": result.updated_source_count,
                    "catalog_count": result.catalog_count,
                    "source_total": coverage["total"],
                    "source_covered": coverage["covered"],
                    "actionable": coverage["total"] - coverage["covered"],
                },
                metadata={"note": log or ""},
                status="clean" if overall_ok else "invalid",
                exit_code=exit_code,
            ),
        )
