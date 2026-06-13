"""Source manifest load/write."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from ledgercore.errors import JsonStoreError
from ledgercore.jsonl import load_jsonl_object_map, write_jsonl_objects

from .constants import SOURCE_MANIFEST


def _format_issue(label: str, issue: object) -> str:
    line = getattr(issue, "line", "?")
    code = getattr(issue, "code", "invalid")
    message = getattr(issue, "message", str(issue))
    return f"{label} line {line}: {code}: {message}"


def load_source_manifest(vault: Path) -> tuple[dict[str, dict[str, object]], list[str]]:
    """Load the source manifest from ``Schema/source-manifest.jsonl``.

    Returns ``(records_dict, error_list)`` where ``error_list`` is a list of
    plain ``str`` items, preserving WikiMason's historical return shape.
    Parsing/validation is delegated to ledgercore.
    """
    manifest_path = vault / SOURCE_MANIFEST
    try:
        result = load_jsonl_object_map(
            manifest_path,
            key="path",
            label="source manifest",
            missing="empty",
            comments=True,
            skip_blank=True,
            duplicate_keys="last",
            require_string_key=True,
        )
    except JsonStoreError as exc:
        return {}, [str(exc)]

    records: dict[str, dict[str, object]] = OrderedDict()
    for path, row in result.rows_by_key.items():
        records[path] = row
    errors = [_format_issue("manifest", issue) for issue in result.issues]
    return records, errors


def write_source_manifest(vault: Path, records: dict[str, dict[str, object]]) -> None:
    """Write the source manifest to ``Schema/source-manifest.jsonl``.

    Uses ledgercore's compact, deterministic, atomic JSONL writer. Note this
    emits compact JSON (``{"a":1}``) rather than the previous spaced form; the
    content round-trips identically and tests compare parsed content.
    """
    manifest_path = vault / SOURCE_MANIFEST
    write_jsonl_objects(manifest_path, records.values(), atomic=True)
