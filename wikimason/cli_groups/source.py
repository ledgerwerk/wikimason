"""Source command group."""

from __future__ import annotations

from pathlib import Path

import typer

from ..cli_helpers import _delta_text, _vault_from_ctx
from ..cli_output import emit
from ..frontmatter import split_frontmatter
from ..notes import resolve_source_path
from ..paths import rel_to_vault, source_md_files
from ..sources import (
    load_source_manifest,
    source_add,
    source_coverage_report,
    source_delta,
    source_lint,
    source_migrate_frontmatter,
    source_rehash,
    source_resolve_report,
    source_scan_payload,
)


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
        payload = {"path": rel_to_vault(vault, target)}
        raise typer.Exit(emit(payload, payload["path"], fmt))

    @_source_app.command("list")
    def source_list_cmd(
        ctx: typer.Context,
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        rows = [p.relative_to(vault).as_posix() for p in source_md_files(vault)]
        raise typer.Exit(emit(rows, "\n".join(rows), fmt))

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
        raise typer.Exit(emit(payload, source_path, fmt))

    @_source_app.command("verify")
    def source_verify_cmd(
        ctx: typer.Context,
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        payload, errors = source_delta(vault)
        if errors:
            print("\n".join(errors))
            raise typer.Exit(1)
        assert payload is not None
        text = _delta_text(payload["delta"])
        exit_code = 2 if int(str(payload["actionable_count"])) > 0 else 0
        raise typer.Exit(emit(payload, text, fmt, exit_code=exit_code))

    @_source_app.command("migrate-frontmatter")
    def source_migrate_frontmatter_cmd(
        ctx: typer.Context,
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        result = source_migrate_frontmatter(vault)
        text = (
            f"Migrated {result['count']} sources"
            if result["count"]
            else "No sources needed migration"
        )
        raise typer.Exit(emit(result, text, fmt))

    @_source_app.command("rehash")
    def source_rehash_cmd(
        ctx: typer.Context,
        accept_covered: bool = typer.Option(False, "--accept-covered"),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        result = source_rehash(vault, accept_covered=accept_covered)
        text = f"Updated {result['updated']} records"
        raise typer.Exit(emit(result, text, fmt))

    @_source_app.command("resolve")
    def source_resolve_cmd(
        ctx: typer.Context,
        query: str = typer.Argument(..., help="Query string."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        payload = source_resolve_report(vault, query)
        text = "\n".join(str(m["path"]) for m in payload["matches"]) or "no matches"
        raise typer.Exit(emit(payload, text, fmt))

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
            print("\n".join(errors))
            raise typer.Exit(1)
        assert payload is not None
        raise typer.Exit(emit(payload, str(len(payload["records"])), fmt))

    @_source_app.command("delta")
    def source_delta_cmd(
        ctx: typer.Context,
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        payload, errors = source_delta(vault)
        if errors:
            print("\n".join(errors))
            raise typer.Exit(1)
        assert payload is not None
        text = _delta_text(payload["delta"])
        exit_code = 2 if int(str(payload["actionable_count"])) > 0 else 0
        raise typer.Exit(emit(payload, text, fmt, exit_code=exit_code))

    @_source_app.command("coverage")
    def source_coverage_cmd(
        ctx: typer.Context,
        path: str = typer.Argument(None, help="Optional path filter."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        report = source_coverage_report(vault, path_arg=path)
        raise typer.Exit(emit(report, f"{report['covered']}/{report['total']}", fmt))

    @_source_app.command("lint")
    def source_lint_cmd(
        ctx: typer.Context,
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        errors = source_lint(vault)
        payload = {"ok": not errors, "errors": errors}
        raise typer.Exit(
            emit(
                payload,
                "\n".join(errors) if errors else "source manifest clean",
                fmt,
                exit_code=1 if errors else 0,
            )
        )
