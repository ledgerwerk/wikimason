from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from .build import build_vault
from .catalog import iter_catalog_entries
from .config import load_runtime_config
from .frontmatter import split_frontmatter
from .lint import lint_vault
from .notes import resolve_source_path
from .paths import compiled_md_files, slugify_title
from .sources import (
    source_coverage_report,
    source_delta,
    source_lint,
    source_scan_payload,
)


@dataclass(frozen=True)
class IngestFinishResult:
    ok: bool
    exit_code: int
    build_updated_source_count: int
    build_catalog_count: int
    lint_ok: bool
    source_scan_ok: bool
    source_lint_ok: bool
    doctor_ok: bool
    coverage: dict[str, object]
    actionable_count: int
    next_action: str


def ingest_status(vault: Path) -> dict[str, object]:
    doctor = doctor_status(vault)
    lint_errors = lint_vault(vault)
    source_lint_errors = source_lint(vault)
    delta_payload, delta_errors = source_delta(vault)
    coverage = source_coverage_report(vault)
    actionable_count = int(delta_payload["actionable_count"]) if delta_payload else 0
    next_action = _next_action(lint_errors, source_lint_errors, actionable_count)
    return {
        "doctor_ok": doctor["ok"],
        "lint_ok": not lint_errors,
        "source_lint_ok": not source_lint_errors,
        "catalog_count": sum(1 for _ in iter_catalog_entries(vault)),
        "sources": {
            "total": coverage["total"],
            "covered": coverage["covered"],
            "coverage_percent": coverage["coverage_percent"],
            "actionable_count": actionable_count,
        },
        "next_action": next_action,
        "doctor": doctor,
        "delta_errors": delta_errors,
    }


def ingest_plan(vault: Path, source_args: list[str] | None = None) -> dict[str, object]:
    requested = source_args or actionable_sources(vault)
    plans = [source_plan(vault, source) for source in requested]
    if len(plans) == 1:
        return plans[0]
    return {"plans": plans}


def ingest_finish(vault: Path, accept_covered: bool = False) -> IngestFinishResult:
    build_result = build_vault(vault)
    lint_errors = lint_vault(vault)
    scan_payload, scan_errors = source_scan_payload(
        vault, update=True, accept_covered=accept_covered
    )
    source_lint_errors = source_lint(vault)
    doctor = doctor_status(vault)
    coverage = source_coverage_report(vault)
    delta_payload, delta_errors = source_delta(vault)
    lint_ok = not lint_errors
    source_scan_ok = scan_payload is not None and not scan_errors
    source_lint_ok = not source_lint_errors
    doctor_ok = doctor["ok"]
    actionable_count = int(delta_payload["actionable_count"]) if delta_payload else 0
    exit_code = 0
    if (
        not (lint_ok and source_scan_ok and source_lint_ok and doctor_ok)
        or delta_errors
    ):
        exit_code = 1
    elif actionable_count > 0:
        exit_code = 2
    return IngestFinishResult(
        ok=exit_code == 0,
        exit_code=exit_code,
        build_updated_source_count=build_result.updated_source_count,
        build_catalog_count=build_result.catalog_count,
        lint_ok=lint_ok,
        source_scan_ok=source_scan_ok,
        source_lint_ok=source_lint_ok,
        doctor_ok=doctor_ok,
        coverage=coverage,
        actionable_count=actionable_count,
        next_action=_next_action(lint_errors, source_lint_errors, actionable_count),
    )


def actionable_sources(vault: Path) -> list[str]:
    payload, _ = source_delta(vault)
    if payload is None:
        return []
    ordered: list[str] = []
    seen: set[str] = set()
    for key in ("new", "content_changed", "metadata_changed", "missing_coverage"):
        for row in payload["delta"][key]:
            path = str(row["path"])
            if path in seen:
                continue
            seen.add(path)
            ordered.append(path)
    return ordered


def source_plan(vault: Path, source_arg: str) -> dict[str, object]:
    path = normalize_source_argument(vault, source_arg)
    source_path = vault / path
    metadata, _ = split_frontmatter(source_path.read_text(encoding="utf-8"))
    title = str(
        metadata.get("Title") or metadata.get("title") or source_path.stem
    ).strip()
    slug = slugify_title(title)
    today = date.today().isoformat()
    return {
        "source": path,
        "source_title": title,
        "recommended_notes": [
            {
                "kind": "topic",
                "title_hint": title,
                "path_hint": f"Wiki/Topics/{slug}.md",
            },
            {
                "kind": "concept",
                "title_hint": title,
                "path_hint": f"Wiki/Concepts/{slug}.md",
            },
            {
                "kind": "log",
                "title_hint": f"Initial {title} Ingest",
                "path_hint": f"Wiki/Logs/{today}-initial-{slug}-ingest.md",
            },
        ],
        "required_validations": [
            "wikimason vault build",
            "wikimason vault lint",
            "wikimason source scan --update --accept-covered",
            "wikimason source lint",
            "wikimason vault doctor",
            "wikimason source coverage --format json",
        ],
    }


def doctor_status(vault: Path) -> dict[str, object]:
    config = load_runtime_config(vault)
    pages_dir = config.profile_config.pages_dir
    source_lint_errors = source_lint(vault)
    lint_errors = lint_vault(vault)
    checks = [
        {
            "label": "Raw/Sources exists",
            "ok": (vault / "Raw/Sources").exists(),
            "required": True,
        },
        {
            "label": "Raw/Files exists",
            "ok": (vault / "Raw/Files").exists(),
            "required": True,
        },
        {
            "label": f"{pages_dir} exists",
            "ok": (vault / pages_dir).exists(),
            "required": True,
        },
        {"label": "Schema exists", "ok": (vault / "Schema").exists(), "required": True},
        {"label": "Python runtime", "ok": True, "required": True},
        {
            "label": "Raw source notes",
            "ok": any((vault / "Raw/Sources").glob("*.md")),
            "required": True,
        },
        {
            "label": "compiled Wiki notes",
            "ok": any(compiled_md_files(vault)),
            "required": True,
        },
        {
            "label": "Wiki/catalog.jsonl",
            "ok": (vault / "Wiki/catalog.jsonl").exists(),
            "required": False,
        },
        {"label": "source manifest", "ok": not source_lint_errors, "required": False},
        {"label": "compiled note lint", "ok": not lint_errors, "required": False},
    ]
    return {
        "ok": all(check["ok"] or not check["required"] for check in checks),
        "checks": checks,
    }


def render_ingest_finish_json(result: IngestFinishResult) -> dict[str, object]:
    return asdict(result)


def normalize_source_argument(vault: Path, source_arg: str) -> str:
    return resolve_source_path(vault, source_arg)


def _next_action(
    lint_errors: list[str], source_lint_errors: list[str], actionable_count: int
) -> str:
    if lint_errors:
        return "repair_compiled_notes"
    if actionable_count > 0:
        return "compile_missing_sources"
    if source_lint_errors:
        return "repair_source_manifest"
    return "maintain_clean_vault"
