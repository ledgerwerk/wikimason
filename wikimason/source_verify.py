"""Source verify, rehash, frontmatter migration, and lint."""

from __future__ import annotations

from pathlib import Path

from .constants import SOURCE_MANIFEST, SOURCE_SCHEMA_VERSION
from .frontmatter import split_frontmatter
from .paths import source_md_files
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


def source_verify(vault: Path) -> dict[str, object]:
    """Verify raw-source state against manifest."""
    manifest, load_errors = load_source_manifest(vault)
    coverage_map, weak_sources = build_source_coverage_map(vault)
    existing = {p.relative_to(vault).as_posix(): p for p in source_md_files(vault)}
    findings: list[dict[str, object]] = []
    status = "valid"
    exit_code = 0

    seen_content: dict[str, str] = {}
    for key, row in manifest.items():
        path = str(row.get("path", ""))
        sid = str(row.get("source_id", ""))
        present = bool(row.get("present", True))
        file_path = existing.get(path)

        if present and file_path is None:
            findings.append(
                {
                    "source_id": sid,
                    "path": path,
                    "issue": "file_missing",
                    "detail": "marked present but file not found",
                }
            )
            if exit_code < 4:
                exit_code = 4
            continue

        if not present and file_path is not None:
            findings.append(
                {
                    "source_id": sid,
                    "path": path,
                    "issue": "file_reappeared",
                    "detail": "marked removed but file exists",
                }
            )
            if exit_code < 4:
                exit_code = 4
            continue

        if file_path is None:
            continue

        expected = raw_record(
            vault, file_path, coverage_map, old_record=row, timestamp=now_iso()
        )
        expected_body = str(expected.get("body_sha256", ""))
        current_body = str(row.get("body_sha256", ""))
        expected_meta = str(expected.get("metadata_sha256", ""))
        current_meta = str(row.get("metadata_sha256", ""))

        if current_body and current_body != expected_body:
            findings.append(
                {
                    "source_id": sid,
                    "path": path,
                    "issue": "content_changed",
                    "detail": "body hash mismatch",
                }
            )
            if exit_code < 1:
                exit_code = 1
            status = "content_changed"

        if current_meta and current_meta != expected_meta:
            findings.append(
                {
                    "source_id": sid,
                    "path": path,
                    "issue": "metadata_changed",
                    "detail": "metadata hash mismatch",
                }
            )
            if exit_code < 2:
                exit_code = 2
            if status == "valid":
                status = "metadata_invalid"

        content_hash = str(expected.get("content_sha256", ""))
        if content_hash and content_hash in seen_content:
            findings.append(
                {
                    "source_id": sid,
                    "path": path,
                    "issue": "duplicate_content",
                    "detail": f"same content_sha256 as {seen_content[content_hash]}",
                }
            )
            if exit_code < 3:
                exit_code = 3
            status = "duplicate"
        if content_hash:
            seen_content[content_hash] = sid

        orig = str(row.get("original_filename", ""))
        if orig and file_path.name != orig:
            findings.append(
                {
                    "source_id": sid,
                    "path": path,
                    "issue": "renamed",
                    "detail": f"original_filename={orig}, current={file_path.name}",
                }
            )

    status = status if findings else "valid"
    return {
        "status": status,
        "exit_code": exit_code,
        "findings": findings,
        "manifest_errors": load_errors,
        "weak_sources": weak_sources,
    }


def source_rehash(vault: Path, accept_covered: bool = False) -> dict[str, object]:
    """Recompute manifest hashes from current raw-source files."""
    payload, errors = source_scan_payload(
        vault, update=True, accept_covered=accept_covered
    )
    return {
        "updated": len(payload["records"]) if payload else 0,
        "errors": errors,
        "records": payload["records"] if payload else [],
    }


def source_migrate_frontmatter(vault: Path) -> dict[str, object]:
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
            sid = generate_source_id(body)
            wb = _build_wm_fields(
                source_id=sid,
                captured_at=now_iso(),
                original_filename=path.name,
                current_filename=path.name,
            )
            path.write_text(embed_wikimason_metadata(text, wb), encoding="utf-8")
            migrated.append(path.relative_to(vault).as_posix())
        except Exception as exc:
            errors.append(f"{path.relative_to(vault).as_posix()}: {exc}")

    return {"migrated": migrated, "errors": errors, "count": len(migrated)}


def source_lint(vault: Path) -> list[str]:
    records, errors = load_source_manifest(vault)
    coverage_map, weak_sources = build_source_coverage_map(vault)
    existing_raw = {p.relative_to(vault).as_posix(): p for p in source_md_files(vault)}

    for weak in weak_sources:
        errors.append(
            f"weak source in {weak['wiki_path']}: {weak['source']} ({weak['reason']})"
        )

    for key, row in records.items():
        sid = str(row.get("source_id", ""))
        path = str(row.get("path", ""))
        missing = manifest_required_fields() - set(row.keys())
        for field in sorted(missing):
            errors.append(f"{SOURCE_MANIFEST}: {sid or path}: missing field {field}")
        if row.get("schema_version") != SOURCE_SCHEMA_VERSION:
            errors.append(f"{SOURCE_MANIFEST}: {sid or path}: schema_version mismatch")
        if not sid:
            errors.append(f"{SOURCE_MANIFEST}: {path}: missing source_id")

        present = bool(row.get("present", True))
        raw_path = existing_raw.get(path)
        if present and raw_path is None:
            errors.append(
                f"{SOURCE_MANIFEST}: {sid or path}: marked present but file missing"
            )
            continue
        if not present and raw_path is not None:
            errors.append(
                f"{SOURCE_MANIFEST}: {sid or path}: marked removed but file exists"
            )
            continue
        if raw_path is None:
            continue
        expected = raw_record(
            vault, raw_path, coverage_map, old_record=row, timestamp=now_iso()
        )
        for field in ("body_sha256", "metadata_sha256"):
            if row.get(field) != expected.get(field):
                errors.append(f"{SOURCE_MANIFEST}: {sid or path}: {field} mismatch")

        row_coverage = row.get("coverage", [])
        if not isinstance(row_coverage, list):
            errors.append(f"{SOURCE_MANIFEST}: {sid or path}: coverage is not a list")
            row_coverage = []
        expected_coverage = expected.get("coverage", [])
        if sorted(str(v) for v in row_coverage) != sorted(
            str(v) for v in expected_coverage
        ):
            errors.append(f"{SOURCE_MANIFEST}: {sid or path}: coverage mismatch")
        expected_status = "covered" if expected_coverage else "missing"
        if row.get("coverage_status") != expected_status:
            errors.append(f"{SOURCE_MANIFEST}: {sid or path}: coverage_status mismatch")

    for rel_path, path_obj in sorted(existing_raw.items()):
        found = False
        for row in records.values():
            if str(row.get("path", "")) == rel_path:
                found = True
                break
        if not found:
            errors.append(f"{SOURCE_MANIFEST}: missing record for {rel_path}")

    return sorted(set(errors))
