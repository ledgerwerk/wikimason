from __future__ import annotations

import re
from pathlib import Path

from .config import load_runtime_config
from .lint_credentials import check_credentials
from .lint_links import kind_for_lint, validate_body_links, validate_field_links
from .page_profiles import relpath_to_logical_ref, split_page_text
from .schema import (
    allowed_tags,
    compiled_required_fields,
    load_vault_schema,
    valid_statuses,
)

_LOGSEQ_PROPERTY_RE = re.compile(r"^- [^:\n]+::\s*")


def lint_file(
    vault: Path,
    path: Path,
    link_targets: set[str],
    seen_names: dict[str, set[str]],
    findings: list,
    *,
    strict: bool,
) -> None:
    from .lint import LintFinding

    schema = load_vault_schema(vault)
    config = load_runtime_config(vault)
    rel = path.relative_to(vault).as_posix()
    logical_ref = relpath_to_logical_ref(rel, vault=vault) or rel.removesuffix(".md")
    logical_path = Path(logical_ref)
    folder = logical_path.parent.as_posix()
    normalized = logical_path.name.lower()
    folder_names = seen_names.setdefault(folder, set())
    if normalized in folder_names:
        findings.append(
            LintFinding(
                path=rel,
                line=None,
                code="duplicate_filename",
                message="duplicate normalized filename in folder",
            )
        )
    folder_names.add(normalized)
    text = path.read_text(encoding="utf-8")

    # Credential scan for all files
    check_credentials(text, rel, findings)

    # Profile-aware dispatch
    is_logseq = config.profile_config.property_style == "logseq"
    is_obsidian = config.profile == "obsidian"

    if is_logseq:
        # Run Logseq-specific block-format checks
        check_logseq_profile(rel, text, findings)

    # Parse properties via the profile-aware splitter (works for both Logseq and YAML)
    data, body = split_page_text(text, vault=vault, config=config)

    if is_obsidian:
        check_obsidian_profile(rel, text, data, findings)

    # Run shared schema checks for all profiles (including Logseq)
    _validate_page_contract(
        vault,
        rel,
        data,
        body,
        link_targets,
        findings,
        strict=strict,
        schema=schema,
    )


def _validate_page_contract(
    vault: Path,
    rel: str,
    data: dict[str, object],
    body: str,
    link_targets: set[str],
    findings: list,
    *,
    strict: bool,
    schema,
) -> None:
    """Shared schema-driven page contract checks for all profiles."""
    from .lint import LintFinding

    if not data:
        findings.append(
            LintFinding(
                path=rel,
                line=1,
                code="missing_frontmatter",
                message="missing frontmatter or properties",
            )
        )
        return

    required = compiled_required_fields(schema)
    for field in required:
        if field not in data:
            findings.append(
                LintFinding(
                    path=rel,
                    line=None,
                    code="missing_field",
                    message=f"missing field {field}",
                )
            )

    tags = data.get("tags", [])
    if not isinstance(tags, list) or not tags:
        findings.append(
            LintFinding(
                path=rel,
                line=None,
                code="missing_field",
                message="tags must be a non-empty list",
            )
        )
    else:
        for tag in tags:
            if str(tag) not in allowed_tags(schema):
                findings.append(
                    LintFinding(
                        path=rel,
                        line=None,
                        code="unknown_tag",
                        message=f"unknown tag {tag}",
                    )
                )

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

    status = str(data.get("status", ""))
    if status not in valid_statuses(schema):
        findings.append(
            LintFinding(
                path=rel,
                line=None,
                code="invalid_status",
                message=f"invalid status {status}",
            )
        )

    source_count = data.get("source_count", 0)
    try:
        source_count_num = int(source_count)
    except (TypeError, ValueError):
        source_count_num = -1
    if source_count_num != len(sources):
        findings.append(
            LintFinding(
                path=rel,
                line=None,
                code="source_count_mismatch",
                message="source_count mismatch",
            )
        )

    validate_field_links(vault, rel, data, link_targets, findings)
    validate_body_links(
        vault,
        rel,
        body,
        link_targets,
        findings,
        status,
        strict=strict,
        schema=schema,
        kind=kind_for_lint(schema, rel, data),
    )


def check_logseq_profile(rel: str, text: str, findings: list) -> None:
    """Logseq-specific block-format checks."""
    from .lint import LintFinding

    lines = text.splitlines()
    if not lines:
        findings.append(
            LintFinding(path=rel, line=1, code="empty_file", message="empty file")
        )
        return
    in_properties = True
    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped and in_properties:
            continue
        if in_properties and _LOGSEQ_PROPERTY_RE.match(line):
            continue
        if in_properties and stripped:
            in_properties = False
        if (
            stripped
            and not any(stripped.startswith(p) for p in ("-", "```", "#"))
            and not stripped == "---"
        ):
            findings.append(
                LintFinding(
                    path=rel,
                    line=i,
                    code="logseq_block_format",
                    message="line does not start with Logseq block marker (-), heading (#), or code fence (```)",
                )
            )


def check_obsidian_profile(
    rel: str, text: str, data: dict[str, object], findings: list
) -> None:
    """Obsidian-specific lint checks."""
    from .lint import LintFinding

    for line_number, line in enumerate(text.splitlines(), start=1):
        if _LOGSEQ_PROPERTY_RE.match(line.strip()):
            findings.append(
                LintFinding(
                    path=rel,
                    line=line_number,
                    code="logseq_property_in_obsidian",
                    message="Logseq property:: style metadata in Obsidian profile",
                )
            )
            break
