"""Lint facade.

Orchestration and public API. Implementation details live in:
  - lint_rules.py       -- per-page contract validation and profile-specific checks
  - lint_links.py       -- link field/body validation helpers
  - lint_credentials.py -- credential scanning
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from .lint_rules import lint_file as _lint_rules_lint_file
from .paths import build_link_targets, compiled_md_files

# ---------------------------------------------------------------------------
#  Public types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LintFinding:
    path: str
    line: int | None
    code: str
    message: str
    suggestion: str | None = None


# ---------------------------------------------------------------------------
#  Public API
# ---------------------------------------------------------------------------


def lint_paths(
    vault: Path, paths: list[Path], strict: bool = False
) -> list[LintFinding]:
    findings: list[LintFinding] = []
    link_targets = build_link_targets(vault)
    seen_names: dict[str, set[str]] = {}
    for path in sorted(paths):
        _lint_file(vault, path, link_targets, seen_names, findings, strict=strict)
    return findings


def lint_vault(vault: Path, strict: bool = False) -> list[str]:
    return render_lint_text(
        lint_paths(vault, list(compiled_md_files(vault)), strict=strict)
    )


def lint_payload(vault: Path, strict: bool = False) -> dict[str, object]:
    findings = lint_paths(vault, list(compiled_md_files(vault)), strict=strict)
    return {
        "ok": not findings,
        "strict": strict,
        "findings": [asdict(finding) for finding in findings],
    }


def lint_note_payload(
    vault: Path, path: Path, strict: bool = False
) -> dict[str, object]:
    findings = lint_paths(vault, [path], strict=strict)
    return {
        "ok": not findings,
        "strict": strict,
        "findings": [asdict(finding) for finding in findings],
    }


def render_lint_text(findings: list[LintFinding]) -> list[str]:
    lines: list[str] = []
    for finding in findings:
        prefix = f"{finding.path}:{finding.line}" if finding.line else finding.path
        base = f"{prefix}: {finding.message}"
        if finding.suggestion:
            base += f" (suggestion: {finding.suggestion})"
        lines.append(base)
    return lines


# ---------------------------------------------------------------------------
#  Internal
# ---------------------------------------------------------------------------


def _lint_file(
    vault: Path,
    path: Path,
    link_targets: set[str],
    seen_names: dict[str, set[str]],
    findings: list[LintFinding],
    *,
    strict: bool,
) -> None:
    """Delegate to lint_rules.lint_file for actual validation."""
    _lint_rules_lint_file(
        vault, path, link_targets, seen_names, findings, strict=strict
    )
