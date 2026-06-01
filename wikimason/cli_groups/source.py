"""Source command group."""

from __future__ import annotations

from pathlib import Path

import typer

from ..cli_helpers import CommandOutcome, _delta_text, _exit_emit, _finish_command, _vault_from_ctx
from ..cli_output import result_payload
from ..frontmatter import split_frontmatter
from ..log_events import audit_event, change_event, lint_event, source_event
from ..notes import resolve_source_path
from ..paths import rel_to_vault, source_md_files
from ..sources import (
    load_source_manifest,
    source_add,
    source_coverage_report,
    source_delta,
    source_lint,
    source_rehash,
    source_resolve_report,
    source_scan_payload,
)


def _source_result(
    *,
    command: str,
    status: str,
    data: object,
    exit_code: int = 0,
) -> dict[str, object]:
    return result_payload(
        command=command,
        status=status,
        data=data,
        exit_code=exit_code,
    )


def _emit_errors(
    command: str,
    errors: list[str],
    fmt: str,
) -> None:
    result = _source_result(
        command=command,
        status="invalid",
        data={"errors": errors},
        exit_code=1,
    )
    _exit_emit(result, "\n".join(errors), fmt, exit_code=1)


def _compact_delta_data(payload: dict) -> dict:
    delta = payload["delta"]
    compact_actionable: dict[str, list[dict]] = {}
    for key in (
        "new",
        "content_changed",
        "metadata_changed",
        "missing_coverage",
    ):
        rows = delta.get(key, [])
        if rows:
            compact_actionable[key] = [
                {
                    "path": r["path"],
                    "source_id": r.get("source_id", ""),
                    "title": r.get("title", ""),
                }
                for r in rows
            ]
    return {
        "actionable_count": payload["actionable_count"],
        "counts": {
            "new": len(delta.get("new", [])),
            "content_changed": len(delta.get("content_changed", [])),
            "metadata_changed": len(delta.get("metadata_changed", [])),
            "missing_coverage": len(delta.get("missing_coverage", [])),
            "removed": len(delta.get("removed", [])),
            "renamed": len(delta.get("renamed", [])),
            "covered": len(delta.get("covered", [])),
        },
        "actionable": compact_actionable,
        "weak_sources": payload.get("weak_sources", []),
    }


def _resolve_source_query(
    vault: Path,
    query: str,
    first: bool,
    fmt: str,
) -> str | None:
    """Resolve query to a relative vault path, or emit error and return None."""
    from ..source_scan import source_resolve_report as _resolve_report

    exact = vault / query
    if exact.exists() and exact.is_file():
        return rel_to_vault(vault, exact)

    report = _resolve_report(vault, query, limit=5)
    matches = report.get("matches", [])
    exact_matches = [m for m in matches if m.get("match") == "exact"]
    if len(exact_matches) == 1:
        return str(exact_matches[0]["path"])
    if matches and (len(matches) == 1 or first):
        return str(matches[0]["path"])
    if len(matches) > 1:
        _exit_emit(
            _source_result(
                command="source.read",
                status="ambiguous",
                data={
                    "query": query,
                    "matches": matches,
                    "message": (
                        "source query matched multiple candidates; "
                        "use exact path or --first"
                    ),
                },
                exit_code=1,
            ),
            "source query matched multiple candidates; use exact path or --first",
            fmt,
            exit_code=1,
        )
    return resolve_source_path(vault, query)


def register_source(app: typer.Typer) -> None:
    _source_app = typer.Typer(help="Raw source management.")
    app.add_typer(_source_app, name="source")

    @_source_app.command("add")
    def source_add_cmd(
        ctx: typer.Context,
        path: Path = typer.Argument(..., help="Source file to add."),
        move: bool = typer.Option(False, "--move", help="Move instead of copy."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        target = source_add(vault, path, move=move)
        raw = {"path": rel_to_vault(vault, target)}
        payload = _source_result(command="source.add", status="changed", data=raw)
        _finish_command(
            ctx,
            CommandOutcome(
                payload=payload,
                text=str(raw["path"]),
                command="source.add",
                status="changed",
            ),
            fmt,
            log_event=source_event(
                "source.add",
                "changed",
                str(raw["path"]),
                title="Added raw source",
                summary="Moved source into the vault." if move else "Copied source into the vault.",
                metadata={"move": str(move).lower()},
            ),
        )

    @_source_app.command("list")
    def source_list_cmd(
        ctx: typer.Context,
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        rows = [rel_to_vault(vault, p) for p in source_md_files(vault)]
        payload = _source_result(
            command="source.list",
            status="clean",
            data={"items": rows, "total": len(rows)},
        )
        _exit_emit(payload, "\n".join(rows), fmt)

    @_source_app.command("show")
    def source_show_cmd(
        ctx: typer.Context,
        path: str = typer.Argument(..., help="Source path."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        source_path = resolve_source_path(vault, path)
        manifest, errors = load_source_manifest(vault)
        text = (vault / source_path).read_text(encoding="utf-8")
        metadata, body = split_frontmatter(text)
        payload = {
            "path": source_path,
            "metadata": metadata,
            "body": body,
            "manifest_record": manifest.get(source_path),
            "manifest_errors": errors,
        }
        result = _source_result(
            command="source.show",
            status="clean",
            data=payload,
            exit_code=0 if not errors else 1,
        )
        _exit_emit(result, source_path, fmt, exit_code=0 if not errors else 1)

    @_source_app.command("verify")
    def source_verify_cmd(
        ctx: typer.Context,
        fmt: str = typer.Option("text", "--format", help="Output format."),
        strict: bool = typer.Option(
            False, "--strict", help="Fail on actionable drift."
        ),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        payload, errors = source_delta(vault)
        if errors:
            _emit_errors("source.verify", errors, fmt)
            return
        assert payload is not None
        text = _delta_text(payload["delta"])
        actionable = int(str(payload["actionable_count"])) > 0
        exit_code = 2 if actionable and strict else 0
        result = _source_result(
            command="source.verify",
            status="actionable" if actionable else "clean",
            data=payload,
            exit_code=exit_code,
        )
        _finish_command(
            ctx,
            CommandOutcome(
                payload=result,
                text=text,
                command="source.verify",
                status="actionable" if actionable else "clean",
                exit_code=exit_code,
            ),
            fmt,
            log_event=audit_event(
                "source.verify",
                "Verified source coverage",
                summary=text,
                counts={"actionable": int(str(payload["actionable_count"]))},
                status="actionable" if actionable else "clean",
                exit_code=exit_code,
            ),
        )

    @_source_app.command("rehash")
    def source_rehash_cmd(
        ctx: typer.Context,
        accept_covered: bool = typer.Option(False, "--accept-covered"),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        raw = source_rehash(vault, accept_covered=accept_covered)
        text = f"Updated {raw['updated']} records"
        payload = _source_result(command="source.rehash", status="changed", data=raw)
        _finish_command(
            ctx,
            CommandOutcome(
                payload=payload,
                text=text,
                command="source.rehash",
                status="changed",
            ),
            fmt,
            log_event=change_event(
                "source.rehash",
                "Rehashed source manifest",
                summary=text,
                counts={"updated": raw["updated"]},
                metadata={"accept_covered": str(accept_covered).lower()},
            ),
        )

    @_source_app.command("resolve")
    def source_resolve_cmd(
        ctx: typer.Context,
        query: str = typer.Argument(..., help="Query string."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        raw = source_resolve_report(vault, query)
        text = "\n".join(str(m["path"]) for m in raw["matches"]) or "no matches"
        payload = _source_result(
            command="source.resolve",
            status="clean" if raw["matches"] else "not_found",
            data=raw,
            exit_code=0 if raw["matches"] else 1,
        )
        _exit_emit(payload, text, fmt, exit_code=0 if raw["matches"] else 1)

    @_source_app.command("scan")
    def source_scan_cmd(
        ctx: typer.Context,
        update: bool = typer.Option(False, "--update"),
        accept_covered: bool = typer.Option(False, "--accept-covered"),
        details: bool = typer.Option(False, "--details", help="Include full records."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        payload, errors = source_scan_payload(
            vault, update=update, accept_covered=accept_covered
        )
        if errors:
            _emit_errors("source.scan", errors, fmt)
            return
        assert payload is not None
        if details:
            data = payload
        else:
            # Compact: counts only.
            records = payload.get("records", [])
            covered = sum(1 for r in records if r.get("coverage"))
            data = {
                "total": len(records),
                "covered": covered,
                "weak_sources": payload.get("weak_sources", []),
            }
        result = _source_result(
            command="source.scan",
            status="changed" if update else "clean",
            data=data,
        )
        event = None
        if update:
            event = change_event(
                "source.scan",
                "Scanned sources",
                summary="Updated source coverage during scan.",
                counts={
                    "total": len(payload["records"]),
                    "covered": sum(1 for r in payload.get("records", []) if r.get("coverage")),
                },
                metadata={"accept_covered": str(accept_covered).lower()},
            )
        _finish_command(
            ctx,
            CommandOutcome(
                payload=result,
                text=str(len(payload["records"])),
                command="source.scan",
                status="changed" if update else "clean",
            ),
            fmt,
            log_event=event,
        )

    @_source_app.command("delta")
    def source_delta_cmd(
        ctx: typer.Context,
        check: bool = typer.Option(False, "--check", help="Exit 2 when actionable."),
        details: bool = typer.Option(
            False, "--details", help="Include full record objects."
        ),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        payload, errors = source_delta(vault)
        if errors:
            _emit_errors("source.delta", errors, fmt)
            return
        assert payload is not None
        text = _delta_text(payload["delta"])
        actionable = int(str(payload["actionable_count"])) > 0
        exit_code = 2 if check and actionable else 0
        if details:
            data = payload
        else:
            data = _compact_delta_data(payload)
        result = _source_result(
            command="source.delta",
            status="actionable" if actionable else "clean",
            data=data,
            exit_code=exit_code,
        )
        _finish_command(
            ctx,
            CommandOutcome(
                payload=result,
                text=text,
                command="source.delta",
                status="actionable" if actionable else "clean",
                exit_code=exit_code,
            ),
            fmt,
            log_event=audit_event(
                "source.delta",
                "Computed source delta",
                summary=text,
                counts={"actionable": int(str(payload["actionable_count"]))},
                status="actionable" if actionable else "clean",
                exit_code=exit_code,
            ),
        )

    @_source_app.command("coverage")
    def source_coverage_cmd(
        ctx: typer.Context,
        path: str = typer.Argument(None, help="Optional path filter."),
        details: bool = typer.Option(False, "--details", help="Include full records."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        report = source_coverage_report(vault, path_arg=path)
        if details:
            data = report
        else:
            missing = [
                {"path": r["path"], "source_id": r.get("source_id", "")}
                for r in report.get("records", [])
                if not r.get("coverage")
            ]
            data = {
                "total": report["total"],
                "covered": report["covered"],
                "missing": report["total"] - report["covered"],
                "coverage_percent": report["coverage_percent"],
                "missing_sources": missing,
            }
        payload = _source_result(command="source.coverage", status="clean", data=data)
        text = f"{report['covered']}/{report['total']}"
        _finish_command(
            ctx,
            CommandOutcome(
                payload=payload,
                text=text,
                command="source.coverage",
                status="clean",
            ),
            fmt,
            log_event=audit_event(
                "source.coverage",
                "Checked source coverage",
                summary=f"Covered {report['covered']} of {report['total']} sources.",
                counts={
                    "covered": report["covered"],
                    "total": report["total"],
                },
            ),
        )

    @_source_app.command("lint")
    def source_lint_cmd(
        ctx: typer.Context,
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        errors = source_lint(vault)
        payload = _source_result(
            command="source.lint",
            status="clean" if not errors else "invalid",
            data={"errors": errors},
            exit_code=1 if errors else 0,
        )
        text = "\n".join(errors) if errors else "source manifest clean"
        _finish_command(
            ctx,
            CommandOutcome(
                payload=payload,
                text=text,
                command="source.lint",
                status="clean" if not errors else "invalid",
                exit_code=1 if errors else 0,
            ),
            fmt,
            log_event=lint_event(
                "source.lint",
                {"ok": not errors, "findings": errors, "exit_code": 1 if errors else 0},
            ),
        )

    @_source_app.command("read")
    def source_read_cmd(
        ctx: typer.Context,
        query: str = typer.Argument(..., help="Source path or search query."),
        lines: int | None = typer.Option(
            None, "--lines", "-n", help="Limit output to first N lines."
        ),
        first: bool = typer.Option(
            False, "--first", help="Allow first fuzzy match when query is ambiguous."
        ),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        resolved_rel = _resolve_source_query(vault, query, first, fmt)
        if resolved_rel is None:
            return
        full_path = vault / resolved_rel
        text = full_path.read_text(encoding="utf-8")
        metadata, body = split_frontmatter(text)
        content_lines = body.splitlines()
        preview = "\n".join(content_lines[:lines]) if lines else body
        raw = {
            "path": resolved_rel,
            "metadata": metadata,
            "content": preview,
            "total_lines": len(content_lines),
        }
        payload = _source_result(command="source.read", status="clean", data=raw)
        text = (
            f"Path: {resolved_rel}\n{preview}" if preview else f"Path: {resolved_rel}"
        )
        _exit_emit(payload, text, fmt)
