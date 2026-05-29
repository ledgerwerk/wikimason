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
from .paths import source_md_files
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


def raw_record(
    vault: Path,
    path: Path,
    coverage_map: dict[str, list[str]],
    old_record: dict[str, Any] | None = None,
    timestamp: str | None = None,
    accept_covered: bool = False,
) -> dict[str, Any]:
    """Build a manifest record for a source file."""
    from .frontmatter import canonical_json

    rel = path.relative_to(vault).as_posix()
    coverage = sorted(set(coverage_map.get(rel, [])))
    coverage_status = "covered" if coverage else "missing"
    now = timestamp or now_iso()
    prior = old_record or {}

    source_kind: str
    content_sha256: str
    body_sha256: str
    metadata_sha256: str
    full_sha: str
    wm_block: dict[str, Any] | None = None
    metadata: dict[str, Any] = {}
    body = ""

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

    covered_sha256 = str(prior.get("covered_sha256", "") or "")
    covered_body_sha256 = str(prior.get("covered_body_sha256", "") or "")
    covered_metadata_sha256 = str(prior.get("covered_metadata_sha256", "") or "")
    if accept_covered and coverage:
        covered_sha256 = content_sha256
        covered_body_sha256 = body_sha256
        covered_metadata_sha256 = metadata_sha256

    from .source_metadata import _LEGACY_EXTRA_FIELDS

    record: dict[str, Any] = {
        "schema_version": SOURCE_SCHEMA_VERSION,
        "source_id": source_id,
        "path": rel,
        "original_filename": original_filename,
        "content_sha256": content_sha256,
        "body_sha256": body_sha256,
        "metadata_sha256": metadata_sha256,
        "size_bytes": path.stat().st_size,
        "source_kind": orig_source_kind,
        "mime_type": mime_type,
        "hash_algorithm": hash_algorithm,
        "hash_scope": hash_scope,
        "first_seen_at": str(prior.get("first_seen_at") or now),
        "last_scanned_at": now,
        "covered_sha256": covered_sha256,
        "covered_body_sha256": covered_body_sha256,
        "covered_metadata_sha256": covered_metadata_sha256,
        "coverage": coverage,
        "coverage_status": coverage_status,
        "present": True,
        "removed_at": "",
    }

    if prior:
        for lf in _LEGACY_EXTRA_FIELDS:
            if lf in prior:
                record[lf] = prior[lf]
    if not record.get("source_title"):
        if source_kind == "text":
            sf = raw_source_fields(metadata if not is_binary_source(path) else {})
            record["source_title"] = sf["source_title"] or path.stem
        else:
            record["source_title"] = path.stem
    if not record.get("sha256"):
        record["sha256"] = full_sha

    return record


def build_source_coverage_map(
    vault: Path,
) -> tuple[dict[str, list[str]], list[dict[str, str]]]:
    prefixes = compiled_prefixes(load_vault_schema(vault))
    existing_raw = {p.relative_to(vault).as_posix() for p in source_md_files(vault)}
    coverage_map: dict[str, list[str]] = {}
    weak_sources: list[dict[str, str]] = []
    for note in sorted((vault / "Wiki").rglob("*.md")):
        rel_note = note.relative_to(vault).as_posix()
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
            cleaned = normalize_internal_link_target(src_text) or src_text
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


def source_scan_payload(
    vault: Path, update: bool = False, accept_covered: bool = False
) -> tuple[dict[str, Any] | None, list[str]]:
    old_records, errors = load_source_manifest(vault)
    coverage_map, weak_sources = build_source_coverage_map(vault)
    timestamp = now_iso()
    new_records: dict[str, dict[str, Any]] = {}

    old_by_path: dict[str, dict[str, Any]] = {}
    for key, row in old_records.items():
        p = str(row.get("path", ""))
        if p:
            old_by_path[p] = row
        old_by_path[key] = row

    for path in sorted((vault / "Raw/Sources").rglob("*.md")):
        rel = path.relative_to(vault).as_posix()
        old_row = old_by_path.get(rel)
        if old_row is None:
            try:
                meta, _ = split_frontmatter(path.read_text(encoding="utf-8"))
                wm = extract_wikimason_metadata(meta)
                if wm and wm.get("source_id"):
                    old_row = old_records.get(str(wm["source_id"]))
            except Exception:
                pass

        row = raw_record(
            vault,
            path,
            coverage_map,
            old_record=old_row,
            timestamp=timestamp,
            accept_covered=accept_covered,
        )
        sid = str(row["source_id"])
        if update and accept_covered and row["coverage"]:
            data, _ = split_frontmatter(path.read_text(encoding="utf-8"))
            if not bool(data.get("Processed", False)):
                path.write_text(
                    update_frontmatter(
                        path.read_text(encoding="utf-8"), {"Processed": True}
                    ),
                    encoding="utf-8",
                )
                row = raw_record(
                    vault,
                    path,
                    coverage_map,
                    old_record=old_row,
                    timestamp=timestamp,
                    accept_covered=accept_covered,
                )
        new_records[sid] = row

        if update and not is_binary_source(path):
            try:
                meta, body = split_frontmatter(path.read_text(encoding="utf-8"))
                if extract_wikimason_metadata(meta) is None:
                    wb = _build_wm_fields(
                        source_id=sid,
                        captured_at=timestamp,
                        original_filename=path.name,
                        current_filename=path.name,
                    )
                    updated = embed_wikimason_metadata(
                        path.read_text(encoding="utf-8"), wb
                    )
                    path.write_text(updated, encoding="utf-8")
                    row = raw_record(
                        vault,
                        path,
                        coverage_map,
                        old_record=old_row,
                        timestamp=timestamp,
                        accept_covered=accept_covered,
                    )
                    sid = str(row["source_id"])
                    new_records[sid] = row
            except Exception:
                pass
    for old_key, old_row in old_records.items():
        old_path = str(old_row.get("path", ""))
        if old_path and old_path in {
            str(r.get("path", "")) for r in new_records.values()
        }:
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


def source_add(vault: Path, source_path: Path, move: bool = False) -> Path:
    """Copy or move a source file into Raw/Sources/, seeding frontmatter when needed."""
    from .frontmatter import split_frontmatter

    target_dir = vault / "Raw/Sources"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source_path.name
    if target.exists():
        raise FileExistsError(f"source exists: {target}")
    if move:
        shutil.move(str(source_path), target)
    else:
        shutil.copy2(source_path, target)

    if is_binary_source(target):
        raw_bytes = target.read_bytes()
        sid = generate_source_id(target.name + str(target.stat().st_size))
        wb = _build_wm_fields(
            source_id=sid,
            captured_at=now_iso(),
            original_filename=target.name,
            current_filename=target.name,
            source_kind="binary",
            mime_type=_guess_mime(target),
            byte_size=target.stat().st_size,
            content_sha256=sha256_text(raw_bytes.hex()),
            hash_scope="full_file_bytes",
        )
        write_sidecar(sidecar_path(target), wb)
        return target

    txt = target.read_text(encoding="utf-8")
    if not txt.startswith("---\n"):
        sid = generate_source_id(txt)
        wb = _build_wm_fields(
            source_id=sid,
            captured_at=now_iso(),
            original_filename=target.name,
            current_filename=target.name,
        )
        with_fm = f"""---
wikimason: '{json.dumps(wb, sort_keys=True, ensure_ascii=False)}'
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

{txt}"""
        target.write_text(with_fm, encoding="utf-8")
    else:
        metadata, body = split_frontmatter(txt)
        if extract_wikimason_metadata(metadata) is None:
            sid = generate_source_id(body)
            wb = _build_wm_fields(
                source_id=sid,
                captured_at=now_iso(),
                original_filename=target.name,
                current_filename=target.name,
            )
            target.write_text(embed_wikimason_metadata(txt, wb), encoding="utf-8")
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
