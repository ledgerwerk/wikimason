"""Links command group."""

from __future__ import annotations

import typer

from ..cli_helpers import _run_row_command, _vault_from_ctx
from ..cli_output import emit, result_payload
from ..files import resolve_existing_path
from ..links import (
    backlinks,
    check_links,
    deadend_notes,
    normalize_links,
    orphan_notes,
    outgoing_links,
    render_link_findings_json,
    render_link_matches_json,
    render_link_normalization_json,
    resolve_link_matches,
    unresolved_links,
)


def register_links(app: typer.Typer) -> None:
    _links_app = typer.Typer(help="Link operations.")
    app.add_typer(_links_app, name="links")

    @_links_app.command("resolve")
    def links_resolve_cmd(
        ctx: typer.Context,
        query: str = typer.Argument(..., help="Link query."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        matches = resolve_link_matches(vault, query)
        payload = {"query": query, "matches": render_link_matches_json(matches)}
        text = "\n".join(match.wikilink for match in matches)
        raise typer.Exit(emit(payload, text, fmt))

    @_links_app.command("check")
    def links_check_cmd(
        ctx: typer.Context,
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        findings = check_links(vault)
        raw = {"findings": render_link_findings_json(findings)}
        text = "\n".join(
            f"{finding.path}:{finding.line}: unresolved {finding.link}"
            for finding in findings
        )
        payload = result_payload(
            command="links.check",
            status="clean" if not findings else "invalid",
            data=raw,
            exit_code=1 if findings else 0,
        )
        raise typer.Exit(
            emit(payload, text or "links clean", fmt, exit_code=1 if findings else 0)
        )

    @_links_app.command("normalize")
    def links_normalize_cmd(
        ctx: typer.Context,
        path: str = typer.Argument(..., help="Note path."),
        fix: bool = typer.Option(False, "--fix"),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        result = normalize_links(vault, path, fix=fix)
        payload = render_link_normalization_json(result)
        text = f"{result.path}: {'changed' if result.changed else 'clean'}"
        raise typer.Exit(emit(payload, text, fmt))

    @_links_app.command("outgoing")
    def links_outgoing_cmd(
        ctx: typer.Context,
        path: str = typer.Argument(..., help="Note path."),
        total: bool = typer.Option(False, "--total"),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        rows = outgoing_links(resolve_existing_path(vault, path))
        if total:
            raise typer.Exit(emit({"total": len(rows)}, str(len(rows)), fmt))
        raise typer.Exit(emit(rows, "\n".join(rows), fmt))

    @_links_app.command("backlinks")
    def links_backlinks_cmd(
        ctx: typer.Context,
        path: str = typer.Argument(..., help="Note path."),
        total: bool = typer.Option(False, "--total", "--counts"),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        rows = backlinks(vault, path)
        if total:
            raise typer.Exit(emit({"total": len(rows)}, str(len(rows)), fmt))
        raise typer.Exit(emit(rows, "\n".join(rows), fmt))

    @_links_app.command("unresolved")
    def links_unresolved_cmd(
        ctx: typer.Context,
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        _run_row_command(ctx, unresolved_links, fmt)

    @_links_app.command("orphans")
    def links_orphans_cmd(
        ctx: typer.Context,
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        _run_row_command(ctx, orphan_notes, fmt)

    @_links_app.command("deadends")
    def links_deadends_cmd(
        ctx: typer.Context,
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        _run_row_command(ctx, deadend_notes, fmt)
