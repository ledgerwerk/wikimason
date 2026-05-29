"""Source delta, coverage reporting."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .source_manifest import load_source_manifest
from .source_scan import source_scan_payload


def source_delta(vault: Path) -> tuple[dict[str, Any] | None, list[str]]:
    payload, errors = source_scan_payload(vault, update=False, accept_covered=False)
    if payload is None:
        return None, errors
    old_manifest, manifest_errors = load_source_manifest(vault)
    errors.extend(manifest_errors)

    old_by_path: dict[str, dict[str, Any]] = {}
    old_by_sid: dict[str, dict[str, Any]] = {}
    for key, row in old_manifest.items():
        sid = str(row.get("source_id", ""))
        p = str(row.get("path", ""))
        if sid:
            old_by_sid[sid] = row
        if p:
            old_by_path[p] = row
        old_by_path[key] = row

    delta: dict[str, list[dict[str, Any]]] = {
        "new": [],
        "content_changed": [],
        "metadata_changed": [],
        "missing_coverage": [],
        "removed": [],
        "covered": [],
        "renamed": [],
    }
    actionable_paths: set[str] = set()

    for record in payload["records"]:
        sid = str(record["source_id"])
        path = str(record["path"])
        present = bool(record.get("present", True))
        prior = old_by_sid.get(sid) or old_by_path.get(path) or old_by_path.get(sid)

        if not prior or not bool(prior.get("present", True)):
            if present:
                delta["new"].append(record)
                actionable_paths.add(sid)
        if not present:
            delta["removed"].append(record)
            actionable_paths.add(sid)
            continue

        if prior is not None:
            prior_path = str(prior.get("path", ""))
            if (
                prior_path
                and prior_path != path
                and str(prior.get("source_id", "")) == sid
            ):
                delta["renamed"].append(record)
                actionable_paths.add(sid)
        coverage = record.get("coverage", [])
        if isinstance(coverage, list) and not coverage:
            delta["missing_coverage"].append(record)
            actionable_paths.add(sid)

        covered_body = str(record.get("covered_body_sha256", "") or "")
        covered_meta = str(record.get("covered_metadata_sha256", "") or "")
        current_body = str(record.get("body_sha256", ""))
        current_meta = str(record.get("metadata_sha256", ""))

        if covered_body and covered_body != current_body:
            delta["content_changed"].append(record)
            actionable_paths.add(sid)
        if covered_meta and covered_meta != current_meta:
            delta["metadata_changed"].append(record)
            actionable_paths.add(sid)
        if covered_body and covered_meta:
            if covered_body == current_body and covered_meta == current_meta:
                delta["covered"].append(record)

    for key in delta:
        delta[key] = sorted(
            delta[key], key=lambda row: str(row.get("path", row.get("source_id", "")))
        )
    actionable_count = len(actionable_paths)
    result = {
        "delta": delta,
        "weak_sources": payload["weak_sources"],
        "actionable_count": actionable_count,
        "exit_reason": "actionable_source_work" if actionable_count > 0 else "",
    }
    return result, errors


def source_coverage_report(vault: Path, path_arg: str | None = None) -> dict[str, Any]:
    payload, _ = source_scan_payload(vault, update=False, accept_covered=False)
    records = [] if payload is None else list(payload["records"])
    if path_arg:
        normalized = path_arg if path_arg.endswith(".md") else f"{path_arg}.md"
        records = [
            row
            for row in records
            if row.get("source_id") == path_arg or row.get("path") == normalized
        ]
    total = len(records)
    covered = sum(1 for row in records if row.get("coverage"))
    return {
        "covered": covered,
        "total": total,
        "records": records,
        "coverage_percent": 0 if total == 0 else round((covered / total) * 100, 2),
    }


def source_coverage(vault: Path) -> tuple[int, int]:
    report = source_coverage_report(vault)
    return int(str(report["covered"])), int(str(report["total"]))
