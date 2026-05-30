"""Source command group."""

from __future__ import annotations

from pathlib import Path

import typer

from ..cli_helpers import _delta_text, _exit_emit, _vault_from_ctx
from ..cli_output import result_payload
from ..frontmatter import split_frontmatter
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


def register_source(app: typer.Typer) -> None:
    _source_app = typer.Typer(help="Raw source management.")
    app.add_typer(_source_app, name="source")

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
        _exit_emit(payload, str(raw["path"]), fmt)

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
            result = _source_result(
                command="source.verify",
                status="invalid",
                data={"errors": errors},
                exit_code=1,
            )
            _exit_emit(
                result,
                "\n".join(errors),
                fmt,
                exit_code=1,
            )
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
        _exit_emit(result, text, fmt, exit_code=exit_code)

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
        _exit_emit(payload, text, fmt)

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
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        payload, errors = source_scan_payload(
            vault, update=update, accept_covered=accept_covered
        )
        if errors:
            result = _source_result(
                command="source.scan",
                status="invalid",
                data={"errors": errors},
                exit_code=1,
            )
            _exit_emit(
                result,
                "\n".join(errors),
                fmt,
                exit_code=1,
            )
        assert payload is not None
        result = _source_result(
            command="source.scan",
            status="changed" if update else "clean",
            data=payload,
        )
        _exit_emit(result, str(len(payload["records"])), fmt)

    @_source_app.command("delta")
    def source_delta_cmd(
        ctx: typer.Context,
        check: bool = typer.Option(False, "--check", help="Exit 2 when actionable."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        payload, errors = source_delta(vault)
        if errors:
            result = _source_result(
                command="source.delta",
                status="invalid",
                data={"errors": errors},
                exit_code=1,
            )
            _exit_emit(
                result,
                "\n".join(errors),
                fmt,
                exit_code=1,
            )
        assert payload is not None
        text = _delta_text(payload["delta"])
        actionable = int(str(payload["actionable_count"])) > 0
        exit_code = 2 if check and actionable else 0
        result = _source_result(
            command="source.delta",
            status="actionable" if actionable else "clean",
            data=payload,
            exit_code=exit_code,
        )
        _exit_emit(result, text, fmt, exit_code=exit_code)

    @_source_app.command("coverage")
    def source_coverage_cmd(
        ctx: typer.Context,
        path: str = typer.Argument(None, help="Optional path filter."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        report = source_coverage_report(vault, path_arg=path)
        payload = _source_result(command="source.coverage", status="clean", data=report)
        _exit_emit(payload, f"{report['covered']}/{report['total']}", fmt)

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
        _exit_emit(
            payload,
            "\n".join(errors) if errors else "source manifest clean",
            fmt,
            exit_code=1 if errors else 0,
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
        from ..source_scan import source_resolve_report

        vault = _vault_from_ctx(ctx)
        command = "source.read"
        # Try exact path first, then fuzzy resolve.
        exact = vault / query
        if exact.exists() and exact.is_file():
            resolved_rel = rel_to_vault(vault, exact)
        else:
            report = source_resolve_report(vault, query, limit=5)
            matches = report.get("matches", [])
            exact_matches = [m for m in matches if m.get("match") == "exact"]
            if len(exact_matches) == 1:
                resolved_rel = str(exact_matches[0]["path"])
            elif len(matches) == 1 or first:
                resolved_rel = matches[0]["path"]
            elif len(matches) > 1:
                payload = _source_result(
                    command=command,
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
                )
                _exit_emit(
                    payload,
                    "source query matched multiple candidates; "
                    "use exact path or --first",
                    fmt,
                    exit_code=1,
                )
            else:
                resolved_rel = resolve_source_path(vault, query)
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
        payload = _source_result(command=command, status="clean", data=raw)
        text = (
            f"Path: {resolved_rel}\n{preview}" if preview else f"Path: {resolved_rel}"
        )
        _exit_emit(payload, text, fmt)
