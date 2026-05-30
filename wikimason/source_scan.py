"""Source scan and record construction."""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path
from typing import Any

from .constants import SOURCE_SCHEMA_VERSION
from .frontmatter import split_frontmatter, update_frontmatter
from .link_format import normalize_internal_link_target
from .paths import rel_to_vault, source_md_files
from .schema import compiled_prefixes, load_vault_schema
from .source_manifest import load_source_manifest, write_source_manifest
from .source_metadata import (
    _build_wm_fields,
    _guess_mime,
    embed_wikimason_metadata,
    extract_wikimason_metadata,
    generate_source_id,
    is_binary_source,
    now_iso,
    raw_source_fields,
    read_sidecar,
    sha256_text,
    sidecar_path,
    write_sidecar,
)


def _record_content_inputs(path: Path) -> dict[str, Any]:
    from .frontmatter import canonical_json

    metadata: dict[str, Any] = {}
    body = ""
    wm_block: dict[str, Any] | None = None

    if is_binary_source(path):
        source_kind = "binary"
        raw_bytes = path.read_bytes()
        full_sha = sha256_text(raw_bytes.hex())
        content_sha256 = full_sha
        body_sha256 = full_sha
        metadata_sha256 = sha256_text(canonical_json({}))
        wm_block = read_sidecar(sidecar_path(path))
    else:
        source_kind = "text"
        text = path.read_text(encoding="utf-8")
        full_sha = sha256_text(text)
        metadata, body = split_frontmatter(text)
        wm_block = extract_wikimason_metadata(metadata)
        content_sha256 = sha256_text(body)
        body_sha256 = content_sha256
        metadata_sha256 = sha256_text(canonical_json(metadata))

    return {
        "source_kind": source_kind,
        "content_sha256": content_sha256,
        "body_sha256": body_sha256,
        "metadata_sha256": metadata_sha256,
        "full_sha": full_sha,
        "metadata": metadata,
        "body": body,
        "wm_block": wm_block,
    }


def _record_identity_fields(
    path: Path,
    *,
    prior: dict[str, Any],
    source_kind: str,
    wm_block: dict[str, Any] | None,
    body: str,
) -> dict[str, str]:
    if wm_block:
        source_id = str(wm_block.get("source_id", ""))
        original_filename = str(wm_block.get("original_filename", path.name))
        orig_source_kind = str(wm_block.get("source_kind", source_kind))
        mime_type = str(wm_block.get("mime_type", _guess_mime(path)))
        hash_algorithm = str(wm_block.get("hash_algorithm", "sha256"))
        hash_scope = str(wm_block.get("hash_scope", "body_without_frontmatter"))
    else:
        source_id = str(prior.get("source_id", ""))
        original_filename = str(prior.get("original_filename", path.name))
        orig_source_kind = source_kind
        mime_type = _guess_mime(path)
        hash_algorithm = "sha256"
        hash_scope = "body_without_frontmatter"

    if not source_id:
        if source_kind == "text":
            source_id = generate_source_id(body)
        else:
            source_id = generate_source_id(path.name + str(path.stat().st_size))

    return {
        "source_id": source_id,
        "original_filename": original_filename,
        "orig_source_kind": orig_source_kind,
        "mime_type": mime_type,
        "hash_algorithm": hash_algorithm,
        "hash_scope": hash_scope,
    }


def _covered_hashes(
    prior: dict[str, Any],
    *,
    accept_covered: bool,
    coverage: list[str],
    content_sha256: str,
    body_sha256: str,
    metadata_sha256: str,
) -> tuple[str, str, str]:
    covered_sha256 = str(prior.get("covered_sha256", "") or "")
    covered_body_sha256 = str(prior.get("covered_body_sha256", "") or "")
    covered_metadata_sha256 = str(prior.get("covered_metadata_sha256", "") or "")
    if accept_covered and coverage:
        covered_sha256 = content_sha256
        covered_body_sha256 = body_sha256
        covered_metadata_sha256 = metadata_sha256
    return covered_sha256, covered_body_sha256, covered_metadata_sha256


def _apply_legacy_fields(
    record: dict[str, Any],
    *,
    prior: dict[str, Any],
    source_kind: str,
    metadata: dict[str, Any],
    path: Path,
    full_sha: str,
) -> None:
    from .source_metadata import _LEGACY_EXTRA_FIELDS

    if prior:
        for field in _LEGACY_EXTRA_FIELDS:
            if field in prior:
                record[field] = prior[field]
    if not record.get("source_title"):
        if source_kind == "text":
            source_fields = raw_source_fields(metadata)
            record["source_title"] = source_fields["source_title"] or path.stem
        else:
            record["source_title"] = path.stem
    if not record.get("sha256"):
        record["sha256"] = full_sha


def _base_record(
    *,
    source_id: str,
    rel_path: str,
    original_filename: str,
    content_sha256: str,
    body_sha256: str,
    metadata_sha256: str,
    size_bytes: int,
    source_kind: str,
    mime_type: str,
    hash_algorithm: str,
    hash_scope: str,
    first_seen_at: str,
    last_scanned_at: str,
    covered_sha256: str,
    covered_body_sha256: str,
    covered_metadata_sha256: str,
    coverage: list[str],
    coverage_status: str,
) -> dict[str, Any]:
    return {
        "schema_version": SOURCE_SCHEMA_VERSION,
        "source_id": source_id,
        "path": rel_path,
        "original_filename": original_filename,
        "content_sha256": content_sha256,
        "body_sha256": body_sha256,
        "metadata_sha256": metadata_sha256,
        "size_bytes": size_bytes,
        "source_kind": source_kind,
        "mime_type": mime_type,
        "hash_algorithm": hash_algorithm,
        "hash_scope": hash_scope,
        "first_seen_at": first_seen_at,
        "last_scanned_at": last_scanned_at,
        "covered_sha256": covered_sha256,
        "covered_body_sha256": covered_body_sha256,
        "covered_metadata_sha256": covered_metadata_sha256,
        "coverage": coverage,
        "coverage_status": coverage_status,
        "present": True,
        "removed_at": "",
    }


def raw_record(
    vault: Path,
    path: Path,
    coverage_map: dict[str, list[str]],
    old_record: dict[str, Any] | None = None,
    timestamp: str | None = None,
    accept_covered: bool = False,
) -> dict[str, Any]:
    rel = rel_to_vault(vault, path)
    coverage = sorted(set(coverage_map.get(rel, [])))
    coverage_status = "covered" if coverage else "missing"
    now = timestamp or now_iso()
    prior = old_record or {}

    content_inputs = _record_content_inputs(path)
    identity = _record_identity_fields(
        path,
        prior=prior,
        source_kind=content_inputs["source_kind"],
        wm_block=content_inputs["wm_block"],
        body=content_inputs["body"],
    )
    covered_sha256, covered_body_sha256, covered_metadata_sha256 = _covered_hashes(
        prior,
        accept_covered=accept_covered,
        coverage=coverage,
        content_sha256=content_inputs["content_sha256"],
        body_sha256=content_inputs["body_sha256"],
        metadata_sha256=content_inputs["metadata_sha256"],
    )

    record = _base_record(
        source_id=identity["source_id"],
        rel_path=rel,
        original_filename=identity["original_filename"],
        content_sha256=content_inputs["content_sha256"],
        body_sha256=content_inputs["body_sha256"],
        metadata_sha256=content_inputs["metadata_sha256"],
        size_bytes=path.stat().st_size,
        source_kind=identity["orig_source_kind"],
        mime_type=identity["mime_type"],
        hash_algorithm=identity["hash_algorithm"],
        hash_scope=identity["hash_scope"],
        first_seen_at=str(prior.get("first_seen_at") or now),
        last_scanned_at=now,
        covered_sha256=covered_sha256,
        covered_body_sha256=covered_body_sha256,
        covered_metadata_sha256=covered_metadata_sha256,
        coverage=coverage,
        coverage_status=coverage_status,
    )
    _apply_legacy_fields(
        record,
        prior=prior,
        source_kind=content_inputs["source_kind"],
        metadata=content_inputs["metadata"],
        path=path,
        full_sha=content_inputs["full_sha"],
    )
    return record


def build_source_coverage_map(
    vault: Path,
) -> tuple[dict[str, list[str]], list[dict[str, str]]]:
    from .paths import decode_unicode_escape_literals, rel_to_vault

    prefixes = compiled_prefixes(load_vault_schema(vault))
    existing_raw = {rel_to_vault(vault, p) for p in source_md_files(vault)}
    coverage_map: dict[str, list[str]] = {}
    weak_sources: list[dict[str, str]] = []
    for note in sorted((vault / "Wiki").rglob("*.md")):
        rel_note = rel_to_vault(vault, note)
        if note.name == "index.md" or rel_note == "Wiki/log.md":
            continue
        if not any(rel_note.startswith(prefix) for prefix in prefixes):
            continue
        metadata, _ = split_frontmatter(note.read_text(encoding="utf-8"))
        sources = metadata.get("sources", [])
        if not isinstance(sources, list):
            continue
        for source in sources:
            src_text = str(source).strip()
            decoded = decode_unicode_escape_literals(src_text)
            cleaned = normalize_internal_link_target(decoded) or decoded
            normalized = cleaned if cleaned.endswith(".md") else f"{cleaned}.md"
            if not normalized.startswith("Raw/"):
                weak_sources.append(
                    {
                        "wiki_path": rel_note,
                        "source": src_text,
                        "reason": "non_raw_source",
                    }
                )
                continue
            normalized = normalized.replace("\\", "/")
            if normalized not in existing_raw:
                weak_sources.append(
                    {"wiki_path": rel_note, "source": src_text, "reason": "missing_raw"}
                )
                continue
            coverage_map.setdefault(normalized, []).append(rel_note)
    for source in coverage_map:
        coverage_map[source] = sorted(set(coverage_map[source]))
    weak_sources.sort(key=lambda row: (row["wiki_path"], row["source"], row["reason"]))
    return coverage_map, weak_sources


def _index_old_records_by_path(
    old_records: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for key, row in old_records.items():
        path = str(row.get("path", ""))
        if path:
            indexed[path] = row
        indexed[key] = row
    return indexed


def _find_old_row_for_source(
    path: Path,
    *,
    vault: Path,
    old_by_path: dict[str, dict[str, Any]],
    old_records: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    rel = rel_to_vault(vault, path)
    old_row = old_by_path.get(rel)
    if old_row is not None:
        return old_row
    try:
        metadata, _ = split_frontmatter(path.read_text(encoding="utf-8"))
        wm = extract_wikimason_metadata(metadata)
        if wm and wm.get("source_id"):
            return old_records.get(str(wm["source_id"]))
    except Exception:
        return None
    return None


def _maybe_mark_processed(
    row: dict[str, Any],
    *,
    path: Path,
    update: bool,
    accept_covered: bool,
    vault: Path,
    coverage_map: dict[str, list[str]],
    old_row: dict[str, Any] | None,
    timestamp: str,
) -> dict[str, Any]:
    if not (update and accept_covered and row["coverage"]):
        return row
    data, _ = split_frontmatter(path.read_text(encoding="utf-8"))
    if bool(data.get("Processed", False)):
        return row
    path.write_text(
        update_frontmatter(path.read_text(encoding="utf-8"), {"Processed": True}),
        encoding="utf-8",
    )
    return raw_record(
        vault,
        path,
        coverage_map,
        old_record=old_row,
        timestamp=timestamp,
        accept_covered=accept_covered,
    )


def _maybe_embed_missing_wm_metadata(
    path: Path,
    *,
    source_id: str,
    timestamp: str,
) -> bool:
    if is_binary_source(path):
        return False
    try:
        metadata, _ = split_frontmatter(path.read_text(encoding="utf-8"))
        if extract_wikimason_metadata(metadata) is not None:
            return False
        wm_block = _build_wm_fields(
            source_id=source_id,
            captured_at=timestamp,
            original_filename=path.name,
            current_filename=path.name,
        )
        updated = embed_wikimason_metadata(path.read_text(encoding="utf-8"), wm_block)
        path.write_text(updated, encoding="utf-8")
        return True
    except Exception:
        return False


def _mark_removed_records(
    old_records: dict[str, dict[str, Any]],
    *,
    new_records: dict[str, dict[str, Any]],
    timestamp: str,
) -> None:
    present_paths = {str(row.get("path", "")) for row in new_records.values()}
    for old_key, old_row in old_records.items():
        old_path = str(old_row.get("path", ""))
        if old_path and old_path in present_paths:
            continue
        if old_key in new_records:
            continue
        old_sid = str(old_row.get("source_id", ""))
        if old_sid and old_sid in new_records:
            continue

        removed = dict(old_row)
        removed["schema_version"] = SOURCE_SCHEMA_VERSION
        removed["present"] = False
        removed["coverage_status"] = "removed"
        removed["removed_at"] = removed.get("removed_at") or timestamp
        removed["last_scanned_at"] = timestamp
        removed.setdefault("coverage", [])
        removed.setdefault("covered_sha256", "")
        removed.setdefault("covered_body_sha256", "")
        removed.setdefault("covered_metadata_sha256", "")
        new_records[old_key] = removed


def source_scan_payload(
    vault: Path, update: bool = False, accept_covered: bool = False
) -> tuple[dict[str, Any] | None, list[str]]:
    old_records, errors = load_source_manifest(vault)
    coverage_map, weak_sources = build_source_coverage_map(vault)
    timestamp = now_iso()
    new_records: dict[str, dict[str, Any]] = {}

    old_by_path = _index_old_records_by_path(old_records)
    for path in sorted((vault / "Raw/Sources").rglob("*.md")):
        old_row = _find_old_row_for_source(
            path,
            vault=vault,
            old_by_path=old_by_path,
            old_records=old_records,
        )
        row = raw_record(
            vault,
            path,
            coverage_map,
            old_record=old_row,
            timestamp=timestamp,
            accept_covered=accept_covered,
        )
        row = _maybe_mark_processed(
            row,
            path=path,
            update=update,
            accept_covered=accept_covered,
            vault=vault,
            coverage_map=coverage_map,
            old_row=old_row,
            timestamp=timestamp,
        )

        source_id = str(row["source_id"])
        new_records[source_id] = row
        if update and _maybe_embed_missing_wm_metadata(path, source_id=source_id, timestamp=timestamp):
            refreshed = raw_record(
                vault,
                path,
                coverage_map,
                old_record=old_row,
                timestamp=timestamp,
                accept_covered=accept_covered,
            )
            new_records[str(refreshed["source_id"])] = refreshed

    _mark_removed_records(old_records, new_records=new_records, timestamp=timestamp)
    if update:
        write_source_manifest(vault, new_records)
    payload = {
        "records": [new_records[key] for key in sorted(new_records)],
        "weak_sources": weak_sources,
    }
    return payload, errors


def source_scan(
    vault: Path, update: bool = False, accept_covered: bool = False
) -> list[dict[str, Any]]:
    payload, _ = source_scan_payload(
        vault, update=update, accept_covered=accept_covered
    )
    if payload is None:
        return []
    return list(payload["records"])


def _copy_or_move_source(source_path: Path, target: Path, *, move: bool) -> None:
    if move:
        shutil.move(str(source_path), target)
    else:
        shutil.copy2(source_path, target)


def _seed_binary_source(target: Path) -> None:
    raw_bytes = target.read_bytes()
    source_id = generate_source_id(target.name + str(target.stat().st_size))
    wm_block = _build_wm_fields(
        source_id=source_id,
        captured_at=now_iso(),
        original_filename=target.name,
        current_filename=target.name,
        source_kind="binary",
        mime_type=_guess_mime(target),
        byte_size=target.stat().st_size,
        content_sha256=sha256_text(raw_bytes.hex()),
        hash_scope="full_file_bytes",
    )
    write_sidecar(sidecar_path(target), wm_block)


def _seed_text_source(target: Path) -> None:
    text = target.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        source_id = generate_source_id(text)
        wm_block = _build_wm_fields(
            source_id=source_id,
            captured_at=now_iso(),
            original_filename=target.name,
            current_filename=target.name,
        )
        with_frontmatter = f"""---
wikimason: '{json.dumps(wm_block, sort_keys=True, ensure_ascii=False)}'
Title: "{target.stem}"
Author: ""
Reference: ""
ContentType:
  - note
Created: {date.today().isoformat()}
Processed: false
tags:
  - source
---

{text}"""
        target.write_text(with_frontmatter, encoding="utf-8")
        return

    metadata, body = split_frontmatter(text)
    if extract_wikimason_metadata(metadata) is not None:
        return
    source_id = generate_source_id(body)
    wm_block = _build_wm_fields(
        source_id=source_id,
        captured_at=now_iso(),
        original_filename=target.name,
        current_filename=target.name,
    )
    target.write_text(embed_wikimason_metadata(text, wm_block), encoding="utf-8")


def source_add(vault: Path, source_path: Path, move: bool = False) -> Path:
    """Copy or move a source file into Raw/Sources/, seeding frontmatter when needed."""
    target_dir = vault / "Raw/Sources"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source_path.name
    if target.exists():
        raise FileExistsError(f"source exists: {target}")

    _copy_or_move_source(source_path, target, move=move)
    if is_binary_source(target):
        _seed_binary_source(target)
        return target

    _seed_text_source(target)
    return target


def source_resolve_report(vault: Path, query: str, limit: int = 5) -> dict[str, Any]:
    """Resolve a query to source path candidates using fuzzy matching."""
    from .paths import path_match_key
    from .search import rank_candidates
    from .search_backends import SourceBackend

    query_key = path_match_key(query)
    if not query_key:
        return {"query": query, "matches": []}

    backend = SourceBackend(vault)
    candidates = backend.candidates(query)

    matches: list[dict[str, Any]] = []
    remaining: list[object] = []
    for candidate in candidates:
        ck = path_match_key(candidate.key)
        fields = candidate.fields
        rel_key = ck
        name_key = path_match_key(fields["name"])
        stem_key = path_match_key(fields["stem"])
        if query_key in {rel_key, name_key, stem_key}:
            matches.append({"path": candidate.path, "match": "exact", "score": 100.0})
        elif query_key in rel_key or query_key in name_key or query_key in stem_key:
            score = (
                max(
                    len(query_key) / max(len(rel_key), 1),
                    len(query_key) / max(len(name_key), 1),
                    len(query_key) / max(len(stem_key), 1),
                )
                * 100
            )
            matches.append(
                {"path": candidate.path, "match": "substring", "score": round(score, 1)}
            )
        else:
            remaining.append(candidate)

    if remaining:
        results = rank_candidates(query, remaining, limit=limit * 2, cutoff=55.0)  # type: ignore[arg-type]
        for result in results:
            matches.append(
                {
                    "path": result.candidate.path,
                    "match": "fuzzy",
                    "score": round(result.score, 1),
                }
            )

    matches.sort(key=lambda row: (-float(row["score"]), str(row["path"])))
    return {"query": query, "matches": matches[:limit]}
