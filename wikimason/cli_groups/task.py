"""Task command group."""

from __future__ import annotations

import typer

from ..cli_helpers import CommandOutcome, _finish_command, _vault_from_ctx
from ..cli_output import emit
from ..daily import daily_note_path
from ..files import resolve_existing_path
from ..log_events import change_event
from ..tasks import list_task_lines, list_tasks, set_task_status, write_task_status


def register_task(app: typer.Typer) -> None:
    _task_app = typer.Typer(help="Task operations.")
    app.add_typer(_task_app, name="task")

    @_task_app.command("list")
    def task_list_cmd(
        ctx: typer.Context,
        daily: bool = typer.Option(False, "--daily"),
        path: str | None = typer.Option(None, "--path"),
        todo: bool = typer.Option(False, "--todo"),
        done: bool = typer.Option(False, "--done"),
        verbose: bool = typer.Option(False, "--verbose"),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        if daily:
            paths = [daily_note_path(vault)]
        elif path is not None:
            paths = [resolve_existing_path(vault, path)]
        else:
            paths = sorted(vault.rglob("*.md"))
        status_filter = "todo" if todo else ("done" if done else None)
        rows = list_task_lines(
            paths, status_filter=status_filter, verbose=verbose, vault=vault
        )
        raise typer.Exit(emit(rows, "\n".join(rows), fmt))

    @_task_app.command("toggle")
    def task_toggle_cmd(
        ctx: typer.Context,
        path: str = typer.Argument(..., help="File path."),
        line: int = typer.Argument(..., help="Line number."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        target = resolve_existing_path(vault, path)
        text = target.read_text(encoding="utf-8")
        current = next(
            (status for line_num, status, _ in list_tasks(text) if line_num == line),
            " ",
        )  # noqa: E501
        next_status = "x" if current == " " else " "
        write_task_status(target, line, next_status)
        rel_path = str(target.relative_to(vault))
        _finish_command(
            ctx,
            CommandOutcome(
                payload={"ok": True, "path": rel_path, "line": line, "status": next_status},
                text="ok",
                command="task.toggle",
                status="changed",
            ),
            fmt,
            log_event=change_event(
                "task.toggle",
                "Toggled task item",
                summary=f"{rel_path}:{line}",
                paths=(rel_path,),
                metadata={"line": line, "status": next_status},
            ),
        )

    @_task_app.command("set")
    def task_set_cmd(
        ctx: typer.Context,
        path: str = typer.Argument(..., help="File path."),
        line: int = typer.Argument(..., help="Line number."),
        status: str = typer.Option(..., "--status", help="Task status."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        target = resolve_existing_path(vault, path)
        text = target.read_text(encoding="utf-8")
        target.write_text(set_task_status(text, line, status), encoding="utf-8")
        rel_path = str(target.relative_to(vault))
        _finish_command(
            ctx,
            CommandOutcome(
                payload={"ok": True, "path": rel_path, "line": line, "status": status},
                text="ok",
                command="task.set",
                status="changed",
            ),
            fmt,
            log_event=change_event(
                "task.set",
                "Set task item status",
                summary=f"{rel_path}:{line}",
                paths=(rel_path,),
                metadata={"line": line, "status": status},
            ),
        )
