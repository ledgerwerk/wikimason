from __future__ import annotations

import shlex
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

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
    coverage: dict[str, Any]
    actionable_count: int
    scope: str
    scoped_lint_ok: bool
    global_lint_ok: bool
    scoped_findings: list[str]
    global_findings: list[str]
    next_action: str


def ingest_status(vault: Path) -> dict[str, Any]:
    doctor = doctor_status(vault)
    lint_errors = lint_vault(vault)
    source_lint_errors = source_lint(vault)
    delta_payload, delta_errors = source_delta(vault)
    coverage = source_coverage_report(vault)
    actionable_count = (
        int(str(delta_payload["actionable_count"])) if delta_payload else 0
    )  # noqa: E501
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


def ingest_plan(vault: Path, source_args: list[str] | None = None) -> dict[str, Any]:
    requested = source_args or actionable_sources(vault)
    plans = [source_plan(vault, source) for source in requested]
    if len(plans) == 1:
        return plans[0]
    return {"plans": plans}


def ingest_finish(
    vault: Path,
    accept_covered: bool = False,
    *,
    scope: str = "changed",
    source: str | None = None,
) -> IngestFinishResult:
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
    actionable_count = (
        int(str(delta_payload["actionable_count"])) if delta_payload else 0
    )  # noqa: E501
    scoped_paths = _scoped_note_paths(vault, scope=scope, source=source)
    scoped_findings = _filter_lint_findings(lint_errors, scoped_paths, scope=scope)
    scoped_lint_ok = not scoped_findings
    global_findings = lint_errors
    global_lint_ok = not global_findings
    exit_code = 0
    if not (source_scan_ok and source_lint_ok and doctor_ok) or delta_errors:
        exit_code = 1
    elif not scoped_lint_ok:
        exit_code = 1
    elif not global_lint_ok:
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
        scope=scope,
        scoped_lint_ok=scoped_lint_ok,
        global_lint_ok=global_lint_ok,
        scoped_findings=scoped_findings,
        global_findings=global_findings,
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


def source_plan(vault: Path, source_arg: str) -> dict[str, Any]:
    path = normalize_source_argument(vault, source_arg)
    source_path = vault / path
    metadata, _ = split_frontmatter(source_path.read_text(encoding="utf-8"))
    title = str(
        metadata.get("Title") or metadata.get("title") or source_path.stem
    ).strip()
    slug = slugify_title(title)
    today = date.today().isoformat()
    commands = [
        _note_new_command(
            kind=note["kind"],
            title=str(note["title_hint"]),
            source=path,
            path_hint=str(note["path_hint"]),
        )
        for note in [
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
        ]
    ]
    validation_commands = [
        "wikimason links check --format json",
        "wikimason source scan --update --accept-covered --format json",
        "wikimason source coverage --format json",
        "wikimason ingest finish --accept-covered --format json",
    ]
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
        "commands": commands,
        "validation_commands": validation_commands,
    }


def doctor_status(vault: Path) -> dict[str, Any]:
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


def render_ingest_finish_json(result: IngestFinishResult) -> dict[str, Any]:
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


def _note_new_command(*, kind: str, title: str, source: str, path_hint: str) -> str:
    return " ".join(
        [
            "wikimason",
            "note",
            "new",
            "--kind",
            shlex.quote(kind),
            "--title",
            shlex.quote(title),
            "--source",
            shlex.quote(source),
            "--path",
            shlex.quote(path_hint),
            "--allow-incomplete",
            "--format",
            "json",
        ]
    )


def _scoped_note_paths(vault: Path, *, scope: str, source: str | None) -> set[str]:
    if scope == "all":
        return set()
    if source:
        sources = [normalize_source_argument(vault, source)]
    else:
        sources = actionable_sources(vault)
    if not sources:
        return set()

    matched: set[str] = set()
    for path in compiled_md_files(vault):
        rel = path.relative_to(vault).as_posix()
        metadata, _ = split_frontmatter(path.read_text(encoding="utf-8"))
        note_sources = metadata.get("sources", [])
        if not isinstance(note_sources, list):
            continue
        for note_source in note_sources:
            if str(note_source) in sources:
                matched.add(rel)
                break
    return matched


def _filter_lint_findings(
    findings: list[str], scoped_paths: set[str], *, scope: str
) -> list[str]:
    if scope == "all" or not scoped_paths:
        return list(findings)
    filtered: list[str] = []
    for finding in findings:
        path = finding.split(":", 1)[0]
        if path in scoped_paths:
            filtered.append(finding)
    return filtered
