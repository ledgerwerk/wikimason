from pathlib import Path

import ledgercore

from wikimason.frontmatter import split_frontmatter, update_frontmatter
from wikimason.paths import ensure_inside_vault, normalize_path_text_for_matching
from wikimason.source_metadata import now_iso
from wikimason.storage import write_text_atomic


def test_required_ledgercore_facade_symbols_are_public() -> None:
    required = {
        "FrontMatterError",
        "JsonStoreError",
        "PathValidationError",
        "atomic_create_text",
        "atomic_write_text",
        "canonical_json",
        "decode_unicode_escape_literals",
        "dumps_json",
        "ensure_inside_base",
        "find_config_upwards",
        "front_matter_fingerprint",
        "load_json_object",
        "load_jsonl_object_map",
        "load_jsonl_objects",
        "normalize_path_text",
        "sha256_bytes",
        "sha256_text",
        "split_front_matter_text",
        "utc_now_iso",
        "write_json",
        "write_jsonl_objects",
    }
    assert required <= set(ledgercore.__all__)


def test_frontmatter_contract_survives_ledgercore_upgrade() -> None:
    data, body = split_frontmatter(
        "---\ncreated: 2026-01-01\ntitle: prefix {{ name }} suffix\n---\nBody\n"
    )
    assert data["created"] == "2026-01-01"
    assert data["title"] == "prefix {{ name }} suffix"
    assert body == "Body\n"

    updated = update_frontmatter(
        "---\ntitle: T\n---\n\nBody\n",
        {"x": "y"},
    )
    assert updated == "---\ntitle: T\nx: y\n---\n\nBody\n"


def test_atomic_write_remains_newline_preserving(tmp_path: Path) -> None:
    path = tmp_path / "example.md"
    write_text_atomic(path, "a\r\nb\r\n")
    assert path.read_bytes() == b"a\r\nb\r\n"


def test_wide_path_normalization_contract() -> None:
    assert normalize_path_text_for_matching("A\u2013B") == "A-B"


def test_path_containment_contract() -> None:
    vault = Path("/tmp/vault")
    assert (
        ensure_inside_vault(vault, vault / "pages/note.md")
        == vault / "pages/note.md"
    )


def test_utc_timestamp_contract() -> None:
    value = now_iso()
    assert value.endswith("Z")
