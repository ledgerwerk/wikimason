from __future__ import annotations

from dataclasses import dataclass

from .command_specs import COMMAND_SPECS, CommandSpec


@dataclass(frozen=True)
class CommandInfo:
    """Lightweight public view of a CommandSpec for search/suggestions."""

    path: tuple[str, ...]
    summary: str
    legacy_aliases: tuple[tuple[str, ...], ...] = ()
    agent_safe: bool = True
    json_output: bool = False

    @classmethod
    def from_spec(cls, spec: CommandSpec) -> CommandInfo:
        return cls(
            path=spec.path,
            summary=spec.summary,
            legacy_aliases=spec.legacy_aliases,
            agent_safe=spec.agent_safe,
            json_output=spec.json_output,
        )


# Derived from the single canonical source.
_COMMAND_INFOS: list[CommandInfo] = [CommandInfo.from_spec(s) for s in COMMAND_SPECS]

# Also register alias-forwarding entries for each legacy alias.
_alias_infos: list[CommandInfo] = []
for spec in COMMAND_SPECS:
    for legacy in spec.legacy_aliases:
        _alias_infos.append(
            CommandInfo(
                path=legacy,
                summary=f"Alias for {' '.join(spec.path)}.",
                legacy_aliases=(),
                agent_safe=spec.agent_safe,
                json_output=spec.json_output,
            )
        )

COMMAND_REGISTRY: tuple[CommandInfo, ...] = tuple(_COMMAND_INFOS + _alias_infos)


def find_command_by_path(path: tuple[str, ...]) -> CommandInfo | None:
    for info in COMMAND_REGISTRY:
        if info.path == path:
            return info
    return None


def find_command_by_alias(alias: tuple[str, ...]) -> CommandInfo | None:
    for info in COMMAND_REGISTRY:
        if alias in info.legacy_aliases:
            return info
    return None


def all_command_paths() -> list[str]:
    return [" ".join(info.path) for info in COMMAND_REGISTRY if not info.legacy_aliases]
