from __future__ import annotations

from pathlib import Path
from typing import Any

from .link_format import (
    extract_internal_links,
    has_internal_links,
    link_resolves,
    normalize_internal_link_target,
)
from .links import resolve_best_wikilink
from .schema import (
    incomplete_allowed_statuses,
    note_kind_for_path,
    required_sections,
)


def validate_field_links(
    vault: Path,
    rel: str,
    data: dict,
    link_targets: set[str],
    findings: list,
) -> None:
    from .lint import LintFinding

    topics = data.get("topics", [])
    if not isinstance(topics, list):
        findings.append(
            LintFinding(
                path=rel,
                line=None,
                code="missing_field",
                message="topics must be a list",
            )
        )
        topics = []
    sources = data.get("sources", [])
    if not isinstance(sources, list):
        findings.append(
            LintFinding(
                path=rel,
                line=None,
                code="missing_field",
                message="sources must be a list",
            )
        )
        sources = []
    for topic in topics:
        if not link_resolves(str(topic), link_targets):
            findings.append(
                LintFinding(
                    path=rel,
                    line=None,
                    code="unresolved_topic_link",
                    message=f"unresolved topic link {topic}",
                    suggestion=normalize_internal_link_target(str(topic)),
                )
            )
    for source in sources:
        source_text = str(source)
        if not source_text.startswith("Raw/") and "Raw/" not in source_text:
            findings.append(
                LintFinding(
                    path=rel,
                    line=None,
                    code="unresolved_source_link",
                    message=f"non-raw source link {source}",
                )
            )
        if not link_resolves(source_text, link_targets):
            findings.append(
                LintFinding(
                    path=rel,
                    line=None,
                    code="unresolved_source_link",
                    message=f"unresolved source link {source}",
                    suggestion=normalize_internal_link_target(source_text),
                )
            )


def validate_body_links(
    vault: Path,
    rel: str,
    body: str,
    link_targets: set[str],
    findings: list[Any],
    status: str,
    *,
    strict: bool,
    schema: Any,
    kind: str | None,
) -> None:
    from .lint import LintFinding

    required = required_sections(schema, kind) if kind else ("Related", "Sources")
    for heading in required:
        if f"## {heading}" in body:
            continue
        findings.append(
            LintFinding(
                path=rel,
                line=None,
                code=f"missing_{heading.lower().replace(' ', '_')}_section",
                message=f"missing ## {heading} section",
            )
        )
    related_required = strict or status not in incomplete_allowed_statuses(schema)
    if "## Related" in body:
        related_block = _section_block(body, "Related")
        if related_required and not has_internal_links(
            related_block, vault=vault, source_path=rel
        ):
            findings.append(
                LintFinding(
                    path=rel,
                    line=_body_line(body, "## Related"),
                    code="empty_related_section",
                    message="## Related must include at least one internal link",
                )
            )
    for line_number, line in enumerate(body.splitlines(), start=1):
        for link in extract_internal_links(line, vault=vault, source_path=rel):
            if link_resolves(link.query, link_targets):
                continue
            findings.append(
                LintFinding(
                    path=rel,
                    line=line_number,
                    code="unresolved_body_link",
                    message=f"unresolved body link {link.query}",
                    suggestion=resolve_best_wikilink(
                        vault, link.query, source_path=rel
                    ),
                )
            )


def _section_block(body: str, heading: str) -> str:
    lines = body.splitlines()
    capture = False
    out: list[str] = []
    header = f"## {heading}".lower()
    for line in lines:
        if line.strip().lower() == header:
            capture = True
            continue
        if capture and line.startswith("#"):
            break
        if capture:
            out.append(line)
    return "\n".join(out)


def _body_line(body: str, needle: str) -> int | None:
    for index, line in enumerate(body.splitlines(), start=1):
        if line.strip() == needle:
            return index
    return None


def kind_for_lint(schema: Any, rel: str, data: dict[str, Any]) -> str | None:
    by_path = note_kind_for_path(schema, rel)
    if by_path is not None:
        return by_path
    tags = data.get("tags", [])
    if isinstance(tags, list):
        for tag in tags:
            for name, config in schema.note_kinds.items():
                if str(tag) == config.tag:
                    return str(name)
    return None
