"""Source verify, rehash, frontmatter migration, and lint."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .constants import SOURCE_MANIFEST, SOURCE_SCHEMA_VERSION
from .frontmatter import split_frontmatter
from .paths import rel_to_vault, source_md_files
from .source_manifest import load_source_manifest
from .source_metadata import (
    _build_wm_fields,
    embed_wikimason_metadata,
    extract_wikimason_metadata,
    generate_source_id,
    is_binary_source,
    manifest_required_fields,
    now_iso,
)
from .source_scan import build_source_coverage_map, raw_record, source_scan_payload


def _finding(source_id: str, path: str, issue: str, detail: str) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "path": path,
        "issue": issue,
        "detail": detail,
    }


def _verify_presence(
    *,
    source_id: str,
    path: str,
    present: bool,
    file_path: Path | None,
) -> tuple[list[dict[str, Any]], int, bool]:
    if present and file_path is None:
        return [
            _finding(source_id, path, "file_missing", "marked present but file not found")
        ], 4, True
    if not present and file_path is not None:
        return [
            _finding(source_id, path, "file_reappeared", "marked removed but file exists")
        ], 4, True
    if file_path is None:
        return [], 0, True
    return [], 0, False


def _verify_hash_changes(
    *,
    source_id: str,
    path: str,
    row: dict[str, Any],
    expected: dict[str, Any],
) -> tuple[list[dict[str, Any]], int, bool, bool]:
    findings: list[dict[str, Any]] = []
    exit_code = 0
    content_changed = False
    metadata_changed = False

    expected_body = str(expected.get("body_sha256", ""))
    current_body = str(row.get("body_sha256", ""))
    expected_meta = str(expected.get("metadata_sha256", ""))
    current_meta = str(row.get("metadata_sha256", ""))

    if current_body and current_body != expected_body:
        findings.append(_finding(source_id, path, "content_changed", "body hash mismatch"))
        exit_code = max(exit_code, 1)
        content_changed = True
    if current_meta and current_meta != expected_meta:
        findings.append(_finding(source_id, path, "metadata_changed", "metadata hash mismatch"))
        exit_code = max(exit_code, 2)
        metadata_changed = True
    return findings, exit_code, content_changed, metadata_changed


def _verify_duplicate(
    *,
    source_id: str,
    path: str,
    expected: dict[str, Any],
    seen_content: dict[str, str],
) -> tuple[list[dict[str, Any]], int, bool, str]:
    content_hash = str(expected.get("content_sha256", ""))
    if content_hash and content_hash in seen_content:
        return [
            _finding(
                source_id,
                path,
                "duplicate_content",
                f"same content_sha256 as {seen_content[content_hash]}",
            )
        ], 3, True, content_hash
    return [], 0, False, content_hash


def _verify_rename(
    *,
    source_id: str,
    path: str,
    row: dict[str, Any],
    file_path: Path,
) -> list[dict[str, Any]]:
    original_filename = str(row.get("original_filename", ""))
    if original_filename and file_path.name != original_filename:
        return [
            _finding(
                source_id,
                path,
                "renamed",
                f"original_filename={original_filename}, current={file_path.name}",
            )
        ]
    return []


def _verify_manifest_row(
    vault: Path,
    row: dict[str, Any],
    *,
    existing: dict[str, Path],
    coverage_map: dict[str, list[str]],
    seen_content: dict[str, str],
) -> tuple[list[dict[str, Any]], int, bool, bool, bool, str, str]:
    findings: list[dict[str, Any]] = []
    path = str(row.get("path", ""))
    source_id = str(row.get("source_id", ""))
    present = bool(row.get("present", True))
    file_path = existing.get(path)

    presence_findings, presence_exit, stop = _verify_presence(
        source_id=source_id,
        path=path,
        present=present,
        file_path=file_path,
    )
    findings.extend(presence_findings)
    if stop:
        return findings, presence_exit, False, False, False, "", source_id
    assert file_path is not None

    expected = raw_record(vault, file_path, coverage_map, old_record=row, timestamp=now_iso())

    hash_findings, hash_exit, content_changed, metadata_changed = _verify_hash_changes(
        source_id=source_id,
        path=path,
        row=row,
        expected=expected,
    )
    findings.extend(hash_findings)

    duplicate_findings, duplicate_exit, duplicate_found, content_hash = _verify_duplicate(
        source_id=source_id,
        path=path,
        expected=expected,
        seen_content=seen_content,
    )
    findings.extend(duplicate_findings)
    findings.extend(
        _verify_rename(source_id=source_id, path=path, row=row, file_path=file_path)
    )

    row_exit_code = max(presence_exit, hash_exit, duplicate_exit)
    return (
        findings,
        row_exit_code,
        content_changed,
        metadata_changed,
        duplicate_found,
        content_hash,
        source_id,
    )


def source_verify(vault: Path) -> dict[str, Any]:
    """Verify raw-source state against manifest."""
    manifest, load_errors = load_source_manifest(vault)
    coverage_map, weak_sources = build_source_coverage_map(vault)
    existing = {rel_to_vault(vault, p): p for p in source_md_files(vault)}

    findings: list[dict[str, Any]] = []
    status = "valid"
    exit_code = 0
    seen_content: dict[str, str] = {}

    for row in manifest.values():
        (
            row_findings,
            row_exit_code,
            row_content_changed,
            row_metadata_changed,
            row_duplicate,
            content_hash,
            source_id,
        ) = _verify_manifest_row(
            vault,
            row,
            existing=existing,
            coverage_map=coverage_map,
            seen_content=seen_content,
        )
        findings.extend(row_findings)
        exit_code = max(exit_code, row_exit_code)

        if row_content_changed:
            status = "content_changed"
        if row_metadata_changed and status == "valid":
            status = "metadata_invalid"
        if row_duplicate:
            status = "duplicate"
        if content_hash:
            seen_content[content_hash] = source_id

    status = status if findings else "valid"
    return {
        "status": status,
        "exit_code": exit_code,
        "findings": findings,
        "manifest_errors": load_errors,
        "weak_sources": weak_sources,
    }


def source_rehash(vault: Path, accept_covered: bool = False) -> dict[str, Any]:
    """Recompute manifest hashes from current raw-source files."""
    payload, errors = source_scan_payload(
        vault, update=True, accept_covered=accept_covered
    )
    return {
        "updated": len(payload["records"]) if payload else 0,
        "errors": errors,
        "records": payload["records"] if payload else [],
    }


def source_migrate_frontmatter(vault: Path) -> dict[str, Any]:
    """Migrate legacy raw-source frontmatter to the wikimason-namespaced format."""
    migrated: list[str] = []
    errors: list[str] = []
    existing = sorted((vault / "Raw/Sources").rglob("*.md"))

    for path in existing:
        if is_binary_source(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
            metadata, body = split_frontmatter(text)
            if extract_wikimason_metadata(metadata) is not None:
                continue
            source_id = generate_source_id(body)
            wb = _build_wm_fields(
                source_id=source_id,
                captured_at=now_iso(),
                original_filename=path.name,
                current_filename=path.name,
            )
            path.write_text(embed_wikimason_metadata(text, wb), encoding="utf-8")
            migrated.append(rel_to_vault(vault, path))
        except Exception as exc:
            errors.append(f"{rel_to_vault(vault, path)}: {exc}")

    return {"migrated": migrated, "errors": errors, "count": len(migrated)}


def _lint_manifest_row(
    vault: Path,
    row: dict[str, Any],
    *,
    coverage_map: dict[str, list[str]],
    existing_raw: dict[str, Path],
) -> list[str]:
    errors: list[str] = []
    source_id = str(row.get("source_id", ""))
    path = str(row.get("path", ""))

    missing = manifest_required_fields() - set(row.keys())
    for field in sorted(missing):
        errors.append(f"{SOURCE_MANIFEST}: {source_id or path}: missing field {field}")
    if row.get("schema_version") != SOURCE_SCHEMA_VERSION:
        errors.append(f"{SOURCE_MANIFEST}: {source_id or path}: schema_version mismatch")
    if not source_id:
        errors.append(f"{SOURCE_MANIFEST}: {path}: missing source_id")

    present = bool(row.get("present", True))
    raw_path = existing_raw.get(path)
    if present and raw_path is None:
        errors.append(f"{SOURCE_MANIFEST}: {source_id or path}: marked present but file missing")
        return errors
    if not present and raw_path is not None:
        errors.append(f"{SOURCE_MANIFEST}: {source_id or path}: marked removed but file exists")
        return errors
    if raw_path is None:
        return errors

    expected = raw_record(vault, raw_path, coverage_map, old_record=row, timestamp=now_iso())
    for field in ("body_sha256", "metadata_sha256"):
        if row.get(field) != expected.get(field):
            errors.append(f"{SOURCE_MANIFEST}: {source_id or path}: {field} mismatch")

    row_coverage = row.get("coverage", [])
    if not isinstance(row_coverage, list):
        errors.append(f"{SOURCE_MANIFEST}: {source_id or path}: coverage is not a list")
        row_coverage = []
    expected_coverage = expected.get("coverage", [])
    if sorted(str(value) for value in row_coverage) != sorted(
        str(value) for value in expected_coverage
    ):
        errors.append(f"{SOURCE_MANIFEST}: {source_id or path}: coverage mismatch")
    expected_status = "covered" if expected_coverage else "missing"
    if row.get("coverage_status") != expected_status:
        errors.append(f"{SOURCE_MANIFEST}: {source_id or path}: coverage_status mismatch")

    return errors


def _lint_missing_manifest_records(
    records: dict[str, dict[str, Any]], existing_raw: dict[str, Path]
) -> list[str]:
    errors: list[str] = []
    for rel_path in sorted(existing_raw):
        found = any(str(row.get("path", "")) == rel_path for row in records.values())
        if not found:
            errors.append(f"{SOURCE_MANIFEST}: missing record for {rel_path}")
    return errors


def source_lint(vault: Path) -> list[str]:
    records, errors = load_source_manifest(vault)
    coverage_map, weak_sources = build_source_coverage_map(vault)
    existing_raw = {rel_to_vault(vault, p): p for p in source_md_files(vault)}

    for weak in weak_sources:
        errors.append(
            f"weak source in {weak['wiki_path']}: {weak['source']} ({weak['reason']})"
        )

    for row in records.values():
        errors.extend(
            _lint_manifest_row(
                vault,
                row,
                coverage_map=coverage_map,
                existing_raw=existing_raw,
            )
        )

    errors.extend(_lint_missing_manifest_records(records, existing_raw))
    return sorted(set(errors))
