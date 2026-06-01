"""Context command group for WikiMason CLI."""

from __future__ import annotations

from pathlib import Path

import typer

from ..cli_helpers import _exit_emit, _vault_from_ctx
from ..context_export import (
    export_context,
    plan_context,
    plan_to_json,
    render_context_markdown,
)


def register_context(app: typer.Typer) -> None:
    _ctx_app = typer.Typer(help="Context export commands.")
    app.add_typer(_ctx_app, name="context")

    @_ctx_app.command("plan")
    def context_plan_cmd(
        ctx: typer.Context,
        query: str = typer.Argument(..., help="Topic query."),
        max_files: int = typer.Option(30, "--max-files", help="Max files to select."),
        max_bytes: int = typer.Option(250_000, "--max-bytes", help="Max total bytes."),
        max_tokens: int = typer.Option(
            60_000, "--max-tokens", help="Max estimated tokens."
        ),
        depth: int = typer.Option(1, "--depth", help="Link expansion depth."),
        include: str = typer.Option(
            "both", "--include", help="Include: wiki, sources, or both."
        ),
        include_indexes: bool = typer.Option(
            False, "--include-indexes", help="Include generated index pages."
        ),
        include_generated: bool = typer.Option(
            False, "--include-generated", help="Include generated files."
        ),
        include_binary: bool = typer.Option(
            False, "--include-binary", help="Include binary source metadata."
        ),
        min_score: float = typer.Option(0.0, "--min-score", help="Minimum score."),
        rebuild_index: bool = typer.Option(
            False, "--rebuild-index", help="Rebuild FTS index before selection."
        ),
        fmt: str = typer.Option("text", "--format", help="Output format."),
        source_closure: bool = typer.Option(
            True, "--source-closure", help="Check declared source closure."
        ),
        purpose: str = typer.Option(
            "chat", "--purpose", help="Export purpose: chat, search, audit."
        ),
        show_omitted: int = typer.Option(
            20, "--show-omitted", help="Max omitted candidates to show."
        ),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        plan = plan_context(
            vault,
            query,
            max_files=max_files,
            max_bytes=max_bytes,
            max_tokens=max_tokens,
            depth=depth,
            include=include,
            include_indexes=include_indexes,
            include_generated=include_generated,
            include_binary=include_binary,
            min_score=min_score,
            rebuild_index=rebuild_index,
            purpose=purpose,
            source_closure=source_closure,
            show_omitted=show_omitted,
        )
        if fmt == "json":
            payload = plan_to_json(plan)
            text = (
                f"{plan.selected_count} files selected, ~{plan.estimated_tokens} tokens"
            )
            _exit_emit(payload, text, fmt)
        else:
            md = render_context_markdown(vault, plan, show_omitted=show_omitted)
            _exit_emit({"plan": plan_to_json(plan)}, md, fmt)
        if fmt == "json":
            payload = plan_to_json(plan)
            text = (
                f"{plan.selected_count} files selected, ~{plan.estimated_tokens} tokens"
            )
            _exit_emit(payload, text, fmt)
        else:
            md = render_context_markdown(vault, plan)
            _exit_emit({"plan": plan_to_json(plan)}, md, fmt)

    @_ctx_app.command("export")
    def context_export_cmd(
        ctx: typer.Context,
        query: str = typer.Argument(..., help="Topic query."),
        output: Path | None = typer.Option(
            None, "--output", "-o", help="Output file path."
        ),
        print_out: bool = typer.Option(False, "--print", help="Write to stdout."),
        copy: bool = typer.Option(False, "--copy", help="Copy to clipboard."),
        max_files: int = typer.Option(30, "--max-files", help="Max files."),
        max_bytes: int = typer.Option(250_000, "--max-bytes", help="Max total bytes."),
        max_tokens: int = typer.Option(
            60_000, "--max-tokens", help="Max estimated tokens."
        ),
        depth: int = typer.Option(1, "--depth", help="Link expansion depth."),
        include: str = typer.Option(
            "both", "--include", help="Include: wiki, sources, or both."
        ),
        include_indexes: bool = typer.Option(
            False, "--include-indexes", help="Include generated index pages."
        ),
        include_generated: bool = typer.Option(
            False, "--include-generated", help="Include generated files."
        ),
        include_binary: bool = typer.Option(
            False, "--include-binary", help="Include binary source metadata."
        ),
        min_score: float = typer.Option(0.0, "--min-score", help="Minimum score."),
        rebuild_index: bool = typer.Option(
            False, "--rebuild-index", help="Rebuild FTS index before selection."
        ),
        allow_sensitive: bool = typer.Option(
            False,
            "--allow-sensitive",
            help="Proceed even if potential secrets found.",
        ),
        fmt: str = typer.Option("text", "--format", help="Output format."),
        source_closure: bool = typer.Option(
            True, "--source-closure", help="Check declared source closure."
        ),
        purpose: str = typer.Option(
            "chat", "--purpose", help="Export purpose: chat, search, audit."
        ),
        show_omitted: int = typer.Option(
            20, "--show-omitted", help="Max omitted candidates to show."
        ),
    ) -> None:
        vault = _vault_from_ctx(ctx)

        options = {
            "max_files": max_files,
            "max_bytes": max_bytes,
            "max_tokens": max_tokens,
            "depth": depth,
            "include": include,
            "include_indexes": include_indexes,
            "include_generated": include_generated,
            "include_binary": include_binary,
            "min_score": min_score,
            "rebuild_index": rebuild_index,
            "purpose": purpose,
            "source_closure": source_closure,
            "show_omitted": show_omitted,
        }

        plan = export_context(
            vault,
            query,
            output=output or Path("/dev/null"),
            allow_sensitive=allow_sensitive,
            **options,
        )
        md_text = render_context_markdown(vault, plan, show_omitted=show_omitted)

        if print_out:
            import sys

            sys.stdout.write(md_text)
            raise typer.Exit(0)

        if copy:
            from ..clipboard import copy_to_clipboard

            copy_to_clipboard(md_text)

        if output is not None:
            payload = {
                "output": str(output),
                "selected_count": plan.selected_count,
                "estimated_tokens": plan.estimated_tokens,
            }
            text = f"exported {plan.selected_count} files to {output}"
            _exit_emit(payload, text, fmt)
        else:
            raise typer.Exit(0)

    @_ctx_app.command("index")
    def context_index_cmd(
        ctx: typer.Context,
        rebuild: bool = typer.Option(
            False, "--rebuild", help="Force rebuild from scratch."
        ),
        fmt: str = typer.Option("text", "--format", help="Output format."),
    ) -> None:
        vault = _vault_from_ctx(ctx)
        from ..search_index import open_search_index

        idx = open_search_index(vault)
        if rebuild:
            result = idx.rebuild(vault)
        else:
            result = idx.index(vault)
        status = idx.status()
        idx.close()

        payload = {"status": status, "result": result}
        text = (
            f"indexed {result.get('total', 0)} documents"
            if result.get("ok")
            else f"index failed: {result.get('reason', 'unknown')}"
        )
        _exit_emit(payload, text, fmt)
