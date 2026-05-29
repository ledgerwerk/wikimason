from __future__ import annotations

from typing import Any

from rapidfuzz import fuzz, process, utils
from typer.core import TyperGroup


class FuzzyCommandGroup(TyperGroup):
    def get_command(self, ctx: Any, cmd_name: str) -> Any:
        command = super().get_command(ctx, cmd_name)
        if command is not None:
            return command

        matches = process.extract(
            cmd_name,
            list(self.commands),
            scorer=fuzz.WRatio,
            processor=utils.default_process,
            limit=3,
        )
        suggestions = [name for name, score, _ in matches if score >= 65]
        if suggestions:
            ctx.fail(
                f"No such command: {cmd_name}\n\n"
                f"Did you mean: {', '.join(suggestions)}?"
            )
        return None
