from __future__ import annotations

from .schema import VaultSchema, note_kind_for_path

_BUILTIN_TYPE_BY_KIND = {
    "topic": "Topic",
    "concept": "Concept",
    "entity": "Entity",
    "project": "Project",
    "log": "Log",
}


def display_type_for_kind(kind: str) -> str:
    return _BUILTIN_TYPE_BY_KIND.get(
        kind,
        kind.replace("-", " ").replace("_", " ").title(),
    )


def expected_type_for_compiled_path(schema: VaultSchema, rel_path: str) -> str | None:
    kind = note_kind_for_path(schema, rel_path)
    if kind is None:
        return None
    return display_type_for_kind(kind)


def has_valid_type(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())
