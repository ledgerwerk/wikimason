"""Review queue CLI group."""

from __future__ import annotations

import json

import typer

from ..cli_helpers import _vault_from_ctx
from ..cli_output import emit
from ..review import (
    ReviewItem,
    add_review_item,
    find_review_item,
    load_review_queue,
    resolve_review_item,
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
        if fmt == "json":
            payload = [item.__dict__ for item in items]
            raise typer.Exit(emit(payload, json.dumps(payload, sort_keys=True), fmt))
        if not items:
            print("(no review items)")
            raise typer.Exit(0)
        for item in items:
            print(f"{item.review_id} [{item.status}] {item.title}")

    @_review_app.command("show")
    def review_show_cmd(
        ctx: typer.Context,
        review_id: str = typer.Argument(..., help="Review ID."),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        item = find_review_item(vault, review_id)
        if item is None:
            print(f"review item not found: {review_id}")
            raise typer.Exit(1)
        payload = item.__dict__
        if fmt == "json":
            raise typer.Exit(emit(payload, json.dumps(payload, sort_keys=True), fmt))
        print(f"review_id: {item.review_id}")
        print(f"created_at: {item.created_at}")
        print(f"kind: {item.kind}")
        print(f"source_id: {item.source_id}")
        print(f"title: {item.title}")
        print(f"detail: {item.detail}")
        print(f"suggested_actions: {item.suggested_actions}")
        print(f"status: {item.status}")

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
            print(f"review item not found: {review_id}")
            raise typer.Exit(1)
        payload = updated.__dict__
        if fmt == "json":
            raise typer.Exit(emit(payload, json.dumps(payload, sort_keys=True), fmt))
        print(f"resolved {review_id} -> {status}")

    @_review_app.command("add")
    def review_add_cmd(
        ctx: typer.Context,
        kind: str = typer.Option(
            ...,
            "--kind",
            help="Review kind: create_page, merge_conflict, research_gap, source_conflict, unsafe_secret.",
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
        payload = item.__dict__
        if fmt == "json":
            raise typer.Exit(emit(payload, json.dumps(payload, sort_keys=True), fmt))
        print(f"added {item.review_id}")
