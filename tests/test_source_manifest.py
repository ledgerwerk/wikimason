from __future__ import annotations

import json
from pathlib import Path

from wikimason.build import build_vault
from wikimason.frontmatter import split_frontmatter, update_frontmatter
from wikimason.scaffold import init_vault
from wikimason.sources import (
    SOURCE_REQUIRED_FIELDS,
    embed_wikimason_metadata,
    extract_wikimason_metadata,
    generate_source_id,
    source_delta,
    source_rehash,
    source_scan,
    source_verify,
)


def _setup(vault: Path) -> None:
    init_vault(vault, demo=True)
    build_vault(vault)
    source_scan(vault, update=True, accept_covered=True)


def _manifest_rows(vault: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in (vault / "Schema/source-manifest.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]


def test_source_scan_writes_full_schema(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _setup(vault)
    row = _manifest_rows(vault)[0]
    assert SOURCE_REQUIRED_FIELDS <= set(row.keys())


def test_source_scan_preserves_first_seen(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _setup(vault)
    first = _manifest_rows(vault)[0]["first_seen_at"]
    source_scan(vault, update=True, accept_covered=False)
    second = _manifest_rows(vault)[0]["first_seen_at"]
    assert first == second


def test_covered_source_appears_in_covered_delta(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _setup(vault)
    payload, _ = source_delta(vault)
    assert payload is not None
    assert payload["actionable_count"] == 0
    assert payload["delta"]["covered"]


def test_body_edit_is_content_changed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _setup(vault)
    src = vault / "Raw/Sources/wikimason-demo-source.md"
    src.write_text(src.read_text(encoding="utf-8") + "\nbody edit\n", encoding="utf-8")
    payload, _ = source_delta(vault)
    assert payload is not None
    changed = [row["path"] for row in payload["delta"]["content_changed"]]
    assert "Raw/Sources/wikimason-demo-source.md" in changed


def test_frontmatter_edit_is_metadata_changed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _setup(vault)
    src = vault / "Raw/Sources/wikimason-demo-source.md"
    src.write_text(
        update_frontmatter(
            src.read_text(encoding="utf-8"), {"Author": "Updated Author"}
        ),
        encoding="utf-8",
    )
    payload, _ = source_delta(vault)
    assert payload is not None
    changed = [row["path"] for row in payload["delta"]["metadata_changed"]]
    assert "Raw/Sources/wikimason-demo-source.md" in changed


def test_new_source_is_new_and_missing_coverage(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _setup(vault)
    (vault / "Raw/Sources/new-source.md").write_text(
        (
            '---\nTitle: New Source\nAuthor: ""\nReference: ""\n'
            "ContentType:\n  - note\n"
            "Created: 2026-01-01\n"
            "Processed: false\n"
            "tags:\n  - source\n---\n\n# New Source\n"
        ),
        encoding="utf-8",
    )
    payload, _ = source_delta(vault)
    assert payload is not None
    new_paths = [row["path"] for row in payload["delta"]["new"]]
    missing_paths = [row["path"] for row in payload["delta"]["missing_coverage"]]
    assert "Raw/Sources/new-source.md" in new_paths
    assert "Raw/Sources/new-source.md" in missing_paths


def test_deleted_source_is_removed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _setup(vault)
    (vault / "Raw/Sources/wikimason-demo-source.md").unlink()
    payload, _ = source_delta(vault)
    assert payload is not None
    removed_paths = [row["path"] for row in payload["delta"]["removed"]]
    assert "Raw/Sources/wikimason-demo-source.md" in removed_paths


def test_non_raw_source_reference_is_weak(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _setup(vault)
    concept = vault / "Wiki/Concepts/compiled-knowledge.md"
    concept.write_text(
        update_frontmatter(
            concept.read_text(encoding="utf-8"),
            {"sources": ["[[Wiki/Topics/wikimason]]"], "source_count": 1},
        ),
        encoding="utf-8",
    )
    payload, _ = source_delta(vault)
    assert payload is not None
    assert any(item["reason"] == "non_raw_source" for item in payload["weak_sources"])


def test_generate_source_id_has_expected_format(tmp_path: Path) -> None:
    sid = generate_source_id("hello world")
    assert sid.startswith("src_")
    parts = sid.split("_")
    assert len(parts) == 3
    assert len(parts[1]) == 8  # YYYYMMDD
    assert len(parts[2]) == 12  # sha256 prefix


def test_extract_wikimason_metadata_uses_wm_prefix() -> None:
    metadata = {
        "wm_source_id": "src_20260529_abc123",
        "wm_kind": "raw-source",
        "Title": "Normal title",
    }
    block = extract_wikimason_metadata(metadata)
    assert block is not None
    assert block["wm_kind"] == "raw-source"
    assert block["wm_source_id"] == "src_20260529_abc123"
    assert "Title" not in block


def test_extract_wikimason_metadata_none_when_missing() -> None:
    assert extract_wikimason_metadata({"Title": "Hello"}) is None


def test_embed_wikimason_metadata_roundtrip(tmp_path: Path) -> None:
    text = "---\nTitle: Test\n---\n\nBody content"
    fields = {"wm_kind": "raw-source", "wm_source_id": "src_20260529_def456"}
    updated = embed_wikimason_metadata(text, fields)
    metadata, body = split_frontmatter(updated)
    extracted = extract_wikimason_metadata(metadata)
    assert extracted is not None
    assert extracted["wm_source_id"] == "src_20260529_def456"


def test_source_verify_returns_expected_structure(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=True)
    result = source_verify(vault)
    assert "status" in result
    assert "exit_code" in result
    assert "findings" in result


def test_source_rehash_updates_records(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=True)
    result = source_rehash(vault)
    assert "updated" in result
    assert result["updated"] >= 1
    assert "errors" in result


def test_manifest_record_has_source_id(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=True)
    source_scan(vault, update=True, accept_covered=True)
    rows = _manifest_rows(vault)
    for row in rows:
        assert "source_id" in row
        assert row["source_id"].startswith("src_")
        assert "original_filename" in row
        assert "content_sha256" in row
        assert "source_kind" in row


def test_source_scan_decodes_literal_unicode_escape_in_coverage_map(
    tmp_path: Path,
) -> None:
    from conftest import write_source_rel

    vault = tmp_path / "vault"
    init_vault(vault)
    source_rel = write_source_rel(vault, "Agent Harness Engineering \u2013 O'Reilly.md")

    note = vault / "Wiki/Topics/escaped-source.md"
    note.write_text(
        """---
tags:
  - topic
topics: []
status: active
created: 2026-05-29
updated: 2026-05-29
sources:
  - Raw/Sources/Agent Harness Engineering \\u2013 O'Reilly.md
source_count: 1
aliases: []
---

# Escaped Source

## Related

-

## Sources

- [[Raw/Sources/Agent Harness Engineering \\u2013 O'Reilly.md]]
""",
        encoding="utf-8",
    )

    from wikimason.source_scan import source_scan_payload

    payload, _ = source_scan_payload(vault, update=False)
    assert payload is not None
    assert payload["weak_sources"] == []
    records = {row["path"]: row for row in payload["records"]}
    assert records[source_rel]["coverage"] == ["Wiki/Topics/escaped-source.md"]
