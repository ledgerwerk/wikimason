from __future__ import annotations

import json
from pathlib import Path

from wikimason.build import build_vault
from wikimason.frontmatter import update_frontmatter
from wikimason.scaffold import init_vault


def test_build_writes_indexes_and_catalog(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=True)
    result = build_vault(vault)
    assert result.catalog_count > 0
    assert (vault / "Wiki/index.md").exists()
    assert (vault / "Wiki/Topics/index.md").exists()
    assert (vault / "Wiki/Concepts/index.md").exists()
    rows = [
        json.loads(line)
        for line in (vault / "Wiki/catalog.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    first = rows[0]
    for key in ("status", "aliases", "topics", "sources", "summary"):
        assert key in first


def test_source_count_sync_updates_frontmatter(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=True)
    concept = vault / "Wiki/Concepts/compiled-knowledge.md"
    concept.write_text(
        update_frontmatter(concept.read_text(encoding="utf-8"), {"source_count": 99}),
        encoding="utf-8",
    )
    result = build_vault(vault)
    assert result.updated_source_count >= 1
    text = concept.read_text(encoding="utf-8")
    assert "source_count: 1" in text
