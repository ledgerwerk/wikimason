from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from .context import resolve_context


@dataclass
class CliState:
    env: str | None
    config_path: Path | None
    vault: Path | None


def resolve_vault(state: CliState) -> Path:
    return resolve_context_from_state(state, emit_diagnostics=True).root


def resolve_context_from_state(state: CliState, *, emit_diagnostics: bool):
    context = resolve_context(
        vault=str(state.vault) if state.vault else None,
        env=state.env,
        config_path=str(state.config_path) if state.config_path else None,
    )
    if emit_diagnostics:
        for diagnostic in context.diagnostics:
            print(diagnostic, file=sys.stderr)
    return context
