"""Review queue CLI group."""

from __future__ import annotations

import typer

from ..cli_helpers import _exit_emit, _vault_from_ctx
from ..review import (
    ReviewItem,
    add_review_item,
    find_review_item,
    load_review_queue,
    resolve_review_item,
)


def _review_item_text(item: ReviewItem) -> str:
    return "\n".join(
        [
            f"review_id: {item.review_id}",
            f"created_at: {item.created_at}",
            f"kind: {item.kind}",
            f"source_id: {item.source_id}",
            f"title: {item.title}",
            f"detail: {item.detail}",
            f"suggested_actions: {item.suggested_actions}",
            f"status: {item.status}",
        ]
    )


def register_review(app: typer.Typer) -> None:
    _review_app = typer.Typer(help="Review queue operations.")
    app.add_typer(_review_app, name="review")

    @_review_app.command("list")
    def review_list_cmd(
        ctx: typer.Context,
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        items = load_review_queue(vault)
        payload = [item.__dict__ for item in items]
        text = "\n".join(
            f"{item.review_id} [{item.status}] {item.title}" for item in items
        )
        _exit_emit(payload, text or "(no review items)", fmt)

    @_review_app.command("show")
    def review_show_cmd(
        ctx: typer.Context,
        review_id: str = typer.Argument(..., help="Review ID."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        item = find_review_item(vault, review_id)
        if item is None:
            _exit_emit(
                {"ok": False, "review_id": review_id, "error": "review item not found"},
                f"review item not found: {review_id}",
                fmt,
                exit_code=1,
            )
        _exit_emit(item.__dict__, _review_item_text(item), fmt)

    @_review_app.command("resolve")
    def review_resolve_cmd(
        ctx: typer.Context,
        review_id: str = typer.Argument(..., help="Review ID."),
        status: str = typer.Option(
            ..., "--status", help="New status: accepted, skipped, or done."
        ),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        if status not in {"accepted", "skipped", "done"}:
            raise typer.BadParameter("status must be accepted, skipped, or done")
        vault = _vault_from_ctx(ctx)
        updated = resolve_review_item(vault, review_id, status)
        if updated is None:
            _exit_emit(
                {"ok": False, "review_id": review_id, "error": "review item not found"},
                f"review item not found: {review_id}",
                fmt,
                exit_code=1,
            )
        _exit_emit(updated.__dict__, f"resolved {review_id} -> {status}", fmt)

    @_review_app.command("add")
    def review_add_cmd(
        ctx: typer.Context,
        kind: str = typer.Option(
            ...,
            "--kind",
            help="Review kind: create_page, merge_conflict, research_gap, source_conflict, unsafe_secret.",  # noqa: E501
        ),
        title: str = typer.Option(..., "--title", help="Short human-readable title."),
        detail: str = typer.Option("", "--detail", help="Why this needs judgment."),
        source_id: str = typer.Option("", "--source-id", help="Related source ID."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        item = ReviewItem.new(
            kind=kind,
            source_id=source_id,
            title=title,
            detail=detail,
        )
        add_review_item(vault, item)
        _exit_emit(item.__dict__, f"added {item.review_id}", fmt)
