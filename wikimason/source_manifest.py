"""Source manifest load/write."""

from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path

from .constants import SOURCE_MANIFEST


def load_source_manifest(vault: Path) -> tuple[dict[str, dict[str, object]], list[str]]:
    """Load the source manifest from ``Schema/source-manifest.jsonl``.

    Returns (records_dict, error_list).
    """
    manifest_path = vault / SOURCE_MANIFEST
    if not manifest_path.exists():
        return {}, []
    errors: list[str] = []
    records: dict[str, dict[str, object]] = OrderedDict()
    for line_no, line in enumerate(
        manifest_path.read_text(encoding="utf-8").splitlines(), 1
    ):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            errors.append(f"manifest line {line_no}: invalid JSON")
            continue
        if not isinstance(row, dict):
            errors.append(
                f"manifest line {line_no}: expected dict, got {type(row).__name__}"
            )
            continue
        path = row.get("path")
        if not path or not isinstance(path, str):
            errors.append(f"manifest line {line_no}: missing or invalid path")
            continue
        records[path] = row
    return records, errors


def write_source_manifest(vault: Path, records: dict[str, dict[str, object]]) -> None:
    """Write the source manifest to ``Schema/source-manifest.jsonl``."""
    manifest_path = vault / SOURCE_MANIFEST
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for record in records.values():
        lines.append(json.dumps(record, sort_keys=True, ensure_ascii=False))
    manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
