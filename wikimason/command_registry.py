from __future__ import annotations

from dataclasses import dataclass

from .command_specs import COMMAND_SPECS, CommandSpec


@dataclass(frozen=True)
class CommandInfo:
    """Lightweight public view of a CommandSpec for search/suggestions."""

    path: tuple[str, ...]
    summary: str
    agent_safe: bool = True
    json_output: bool = False

    @classmethod
    def from_spec(cls, spec: CommandSpec) -> CommandInfo:
        return cls(
            path=spec.path,
            summary=spec.summary,
            agent_safe=spec.agent_safe,
            json_output=spec.json_output,
        )


COMMAND_REGISTRY: tuple[CommandInfo, ...] = tuple(
    CommandInfo.from_spec(s) for s in COMMAND_SPECS
)


def find_command_by_path(path: tuple[str, ...]) -> CommandInfo | None:
    for info in COMMAND_REGISTRY:
        if info.path == path:
            return info
    return None


def all_command_paths() -> list[str]:
    return [" ".join(info.path) for info in COMMAND_REGISTRY]
