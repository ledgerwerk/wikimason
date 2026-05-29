"""Note command group."""

from __future__ import annotations

import typer

from ..cli_helpers import _run_note_create, _vault_from_ctx
from ..cli_output import emit, print_findings_payload
from ..links import normalize_links, render_link_normalization_json
from ..lint import lint_note_payload
from ..notes import normalize_note
from ..paths import resolve_path_in_vault


def register_note(app: typer.Typer) -> None:
    _note_app = typer.Typer(help="Note operations.")
    app.add_typer(_note_app, name="note")

    @_note_app.command("new")
    def note_new_cmd(
        ctx: typer.Context,
        kind: str = typer.Option(..., "--kind", help="Note kind."),
        title: str = typer.Option(..., "--title", help="Title."),
        source: list[str] = typer.Option([], "--source", help="Source paths."),
        related: list[str] = typer.Option([], "--related", help="Related paths."),
        status: str = typer.Option("seed", "--status", help="Status."),
        summary: str = typer.Option("Short summary.", "--summary", help="Summary."),
        body_file: str | None = typer.Option(None, "--body-file", help="Body file."),
        allow_incomplete: bool = typer.Option(False, "--allow-incomplete"),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        _run_note_create(
            ctx,
            kind=kind,
            title=title,
            source=source,
            related=related,
            status=status,
            summary=summary,
            body_file=body_file,
            allow_incomplete=allow_incomplete,
            fmt=fmt,
        )

    @_note_app.command("validate")
    def note_validate_cmd(
        ctx: typer.Context,
        path: str = typer.Argument(..., help="Note path."),
        strict: bool = typer.Option(False, "--strict"),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        note_path = resolve_path_in_vault(vault, path)
        payload = lint_note_payload(vault, note_path, strict=strict)
        raise typer.Exit(
            print_findings_payload(payload, success_text="note lint passed", fmt=fmt)
        )

    @_note_app.command("normalize")
    def note_normalize_cmd(
        ctx: typer.Context,
        path: str = typer.Argument(..., help="Note path."),
        fix: bool = typer.Option(False, "--fix"),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        note_result = normalize_note(vault, path, fix=fix)
        link_result = normalize_links(vault, path, fix=fix)
        payload = {
            "note": note_result,
            "links": render_link_normalization_json(link_result),
        }
        text = (
            f"{note_result['path']}: normalized"
            if note_result["changed"] or link_result.changed
            else f"{note_result['path']}: clean"
        )
        raise typer.Exit(emit(payload, text, fmt))
