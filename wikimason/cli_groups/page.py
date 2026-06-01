"""Page command group."""

from __future__ import annotations

from pathlib import Path

import typer

from ..cli_helpers import (
    CommandOutcome,
    _finish_command,
    _run_note_create,
    _vault_from_ctx,
)
from ..cli_output import emit
from ..errors import UsageError
from ..files import delete_file, move_file, read_file, write_file
from ..log_events import change_event
from ..paths import rel_to_vault


def register_page(app: typer.Typer) -> None:
    _page_app = typer.Typer(help="Page operations.")
    app.add_typer(_page_app, name="page")

    @_page_app.command("create")
    def page_create_cmd(
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
            command="page.create",
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
                "page.create",
                "Created page",
                summary=f"{title} ({kind})",
                paths=(str(data.get("path", "")),),
                metadata={"kind": kind, "dry_run": str(dry_run).lower()},
                status="clean" if dry_run else "changed",
            ),
        )

    @_page_app.command("show")
    def page_show_cmd(
        ctx: typer.Context,
        path: str = typer.Argument(..., help="Page path."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        content = read_file(vault, path)
        payload = {"path": path, "content": content}
        raise typer.Exit(emit(payload, content, fmt))

    @_page_app.command("update")
    def page_update_cmd(
        ctx: typer.Context,
        path: str = typer.Argument(..., help="Page path."),
        content: str | None = typer.Option(None, "--content", help="New full content."),
        body_file: str | None = typer.Option(
            None,
            "--body-file",
            help="Replace body with file, preserving frontmatter.",
        ),
        body: str | None = typer.Option(
            None,
            "--body",
            help="Replace body with text, preserving frontmatter.",
        ),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        from ..config import load_runtime_config
        from ..notes import normalize_note
        from ..page_profiles import render_page_text, split_page_text
        from ..paths import resolve_path_in_vault

        vault = _vault_from_ctx(ctx)
        if body_file is not None:
            # Body-only update: preserve frontmatter, replace body
            new_body = Path(body_file).read_text(encoding="utf-8").rstrip() + "\n"
            config = load_runtime_config(vault)
            target_path = resolve_path_in_vault(vault, path)
            text = target_path.read_text(encoding="utf-8")
            data, _ = split_page_text(text, config=config)
            updated = render_page_text(data, new_body, config=config)
            target_path.write_text(updated, encoding="utf-8")
            # Run normalization
            normalize_note(vault, path, fix=True)
            payload = {
                "path": path,
                "frontmatter_preserved": True,
                "body_changed": True,
            }
        elif body is not None:
            config = load_runtime_config(vault)
            target_path = resolve_path_in_vault(vault, path)
            text = target_path.read_text(encoding="utf-8")
            data, _ = split_page_text(text, config=config)
            updated = render_page_text(data, body.rstrip() + "\n", config=config)
            target_path.write_text(updated, encoding="utf-8")
            normalize_note(vault, path, fix=True)
            payload = {
                "path": path,
                "frontmatter_preserved": True,
                "body_changed": True,
            }
        elif content is not None:
            target = write_file(vault, path, content=content, overwrite=True)
            payload = {
                "path": rel_to_vault(vault, target),
                "frontmatter_preserved": False,
                "body_changed": True,
            }
        else:
            raise UsageError("page update requires --content, --body-file, or --body")
        _finish_command(
            ctx,
            CommandOutcome(
                payload=payload,
                text=str(payload["path"]),
                command="page.update",
                status="changed",
            ),
            fmt,
            log_event=change_event(
                "page.update",
                "Updated page",
                summary="Updated page content while preserving page structure.",
                paths=(str(payload["path"]),),
            ),
        )

    @_page_app.command("move")
    def page_move_cmd(
        ctx: typer.Context,
        old: str = typer.Argument(..., help="Old path."),
        new: str = typer.Argument(..., help="New path."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        target = move_file(vault, old, new)
        payload = {"path": rel_to_vault(vault, target)}
        _finish_command(
            ctx,
            CommandOutcome(
                payload=payload,
                text=payload["path"],
                command="page.move",
                status="changed",
            ),
            fmt,
            log_event=change_event(
                "page.move",
                "Moved page",
                summary=f"{old} -> {new}",
                paths=(payload["path"],),
            ),
        )

    @_page_app.command("delete")
    def page_delete_cmd(
        ctx: typer.Context,
        path: str = typer.Argument(..., help="Page path."),
        permanent: bool = typer.Option(False, "--permanent"),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        result = delete_file(vault, path, permanent=permanent)
        payload = {"result": result}
        _finish_command(
            ctx,
            CommandOutcome(
                payload=payload,
                text=result,
                command="page.delete",
                status="changed",
            ),
            fmt,
            log_event=change_event(
                "page.delete",
                "Deleted page",
                summary=result,
                paths=(path,),
                metadata={"permanent": str(permanent).lower()},
            ),
        )
