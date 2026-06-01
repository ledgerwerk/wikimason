"""Note command group."""

from __future__ import annotations

import typer

from ..cli_helpers import CommandOutcome, _finish_command, _run_note_create, _vault_from_ctx
from ..cli_output import print_findings_payload, result_payload
from ..links import normalize_links, render_link_normalization_json
from ..lint import lint_note_payload
from ..log_events import change_event
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
        body: str | None = typer.Option(None, "--body", help="Body text."),
        body_file: str | None = typer.Option(None, "--body-file", help="Body file."),
        path: str | None = typer.Option(None, "--path", help="Explicit target path."),
        dry_run: bool = typer.Option(False, "--dry-run"),
        print_note: bool = typer.Option(False, "--print", help="Print rendered note."),
        allow_incomplete: bool = typer.Option(False, "--allow-incomplete"),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        outcome = _run_note_create(
            ctx,
            command="note.new",
            kind=kind,
            title=title,
            source=source,
            related=related,
            status=status,
            summary=summary,
            body=body,
            body_file=body_file,
            path=path,
            dry_run=dry_run,
            print_note=print_note,
            allow_incomplete=allow_incomplete,
        )
        data = outcome.payload["data"] if isinstance(outcome.payload, dict) else {}
        _finish_command(
            ctx,
            outcome,
            fmt,
            log_event=change_event(
                "note.new",
                "Created note",
                summary=f"{title} ({kind})",
                paths=(str(data.get("path", "")),),
                metadata={"kind": kind, "dry_run": str(dry_run).lower()},
                status="clean" if dry_run else "changed",
            ),
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
            print_findings_payload(
                payload,
                success_text="note lint passed",
                fmt=fmt,
                command="note.validate",
            )
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
        event = None
        if fix:
            event = change_event(
                "note.normalize",
                "Normalized note",
                summary=text,
                paths=(str(note_result["path"]),),
                metadata={"links_changed": str(link_result.changed).lower()},
            )
        wrapped = result_payload(
            command="note.normalize",
            status="changed" if fix and (note_result["changed"] or link_result.changed) else "clean",
            data=payload,
        )
        wrapped.update(payload)
        _finish_command(
            ctx,
            CommandOutcome(
                payload=wrapped,
                text=text,
                command="note.normalize",
                status="changed" if fix and (note_result["changed"] or link_result.changed) else "clean",
            ),
            fmt,
            log_event=event,
        )
