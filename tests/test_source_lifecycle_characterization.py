from __future__ import annotations

from pathlib import Path

from wikimason.build import build_vault
from wikimason.frontmatter import update_frontmatter
from wikimason.scaffold import init_vault
from wikimason.sources import (
    read_sidecar,
    sidecar_path,
    source_add,
    source_delta,
    source_scan,
    source_scan_payload,
    source_verify,
)


def _setup(vault: Path) -> None:
    init_vault(vault, demo=True)
    build_vault(vault)
    source_scan(vault, update=True, accept_covered=True)


def test_source_delta_covered_record_contract(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _setup(vault)

    payload, errors = source_delta(vault)
    assert errors == []
    assert payload is not None
    assert payload["actionable_count"] == 0
    assert payload["exit_reason"] == ""
    assert payload["delta"]["covered"]

    row = payload["delta"]["covered"][0]
    assert row["coverage_status"] == "covered"
    assert row["covered_body_sha256"] == row["body_sha256"]
    assert row["covered_metadata_sha256"] == row["metadata_sha256"]


def test_source_lifecycle_rename_contract(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _setup(vault)

    original = vault / "Raw/Sources/wikimason-demo-source.md"
    renamed = vault / "Raw/Sources/renamed-source.md"
    original.rename(renamed)

    payload, _ = source_delta(vault)
    assert payload is not None
    assert payload["actionable_count"] == 1
    assert payload["exit_reason"] == "actionable_source_work"
    assert [row["path"] for row in payload["delta"]["renamed"]] == [
        "Raw/Sources/renamed-source.md"
    ]
    assert payload["delta"]["removed"] == []

    verify = source_verify(vault)
    assert any(
        finding["issue"] == "file_missing"
        and finding["path"] == "Raw/Sources/wikimason-demo-source.md"
        for finding in verify["findings"]
    )


def test_source_lifecycle_removed_contract(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _setup(vault)

    removed_path = "Raw/Sources/wikimason-demo-source.md"
    (vault / removed_path).unlink()

    scan_payload, scan_errors = source_scan_payload(vault, update=False, accept_covered=False)
    assert scan_errors == []
    assert scan_payload is not None

    records_by_path = {row["path"]: row for row in scan_payload["records"]}
    removed_row = records_by_path[removed_path]
    assert removed_row["present"] is False
    assert removed_row["coverage_status"] == "removed"
    assert removed_row["removed_at"]

    delta_payload, _ = source_delta(vault)
    assert delta_payload is not None
    assert [row["path"] for row in delta_payload["delta"]["removed"]] == [removed_path]
    assert delta_payload["actionable_count"] == 1

    verify = source_verify(vault)
    assert any(
        finding["issue"] == "file_missing" and finding["path"] == removed_path
        for finding in verify["findings"]
    )


def test_source_lifecycle_weak_reference_contract(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _setup(vault)

    concept = vault / "Wiki/Concepts/compiled-knowledge.md"
    concept.write_text(
        update_frontmatter(
            concept.read_text(encoding="utf-8"),
            {
                "sources": ["Wiki/Topics/wikimason", "Raw/Sources/missing-source.md"],
                "source_count": 2,
            },
        ),
        encoding="utf-8",
    )

    delta_payload, _ = source_delta(vault)
    assert delta_payload is not None
    delta_reasons = sorted({item["reason"] for item in delta_payload["weak_sources"]})
    assert delta_reasons == ["missing_raw", "non_raw_source"]

    verify = source_verify(vault)
    verify_reasons = sorted({item["reason"] for item in verify["weak_sources"]})
    assert verify_reasons == delta_reasons


def test_binary_source_add_writes_sidecar_contract(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)

    external = tmp_path / "report.pdf"
    external.write_bytes(b"%PDF-1.4\ncharacterization test\n")

    target = source_add(vault, external, move=False)
    block = read_sidecar(sidecar_path(target))
    assert block is not None
    assert block["wm_source_kind"] == "binary"
    assert block["wm_hash_scope"] == "full_file_bytes"

    payload, errors = source_scan_payload(vault, update=False, accept_covered=False)
    assert errors == []
    assert payload is not None
    assert all(str(row["path"]).endswith(".md") for row in payload["records"])
