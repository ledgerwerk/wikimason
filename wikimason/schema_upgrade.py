from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import load_runtime_config
from .note_types import expected_type_for_compiled_path, has_valid_type
from .page_profiles import split_page_text, update_page_text
from .paths import compiled_md_files, rel_to_vault
from .schema import load_vault_schema
from .storage import write_text_atomic


@dataclass(frozen=True)
class TypeMigrationResult:
    checked: int
    updated: int
    skipped: int
    updated_paths: tuple[str, ...]


def migrate_compiled_note_types(vault: Path) -> TypeMigrationResult:
    config = load_runtime_config(vault)
    schema = load_vault_schema(vault, config=config)
    checked = 0
    updated = 0
    skipped = 0
    updated_paths: list[str] = []

    for path in compiled_md_files(vault, schema=schema):
        checked += 1
        rel = rel_to_vault(vault, path)
        expected = expected_type_for_compiled_path(schema, rel)
        if expected is None:
            skipped += 1
            continue

        text = path.read_text(encoding="utf-8")
        data, _body = split_page_text(text, config=config)
        if has_valid_type(data.get("type")):
            continue

        write_text_atomic(
            path, update_page_text(text, {"type": expected}, config=config)
        )
        updated += 1
        updated_paths.append(rel)

    return TypeMigrationResult(
        checked=checked,
        updated=updated,
        skipped=skipped,
        updated_paths=tuple(updated_paths),
    )
