from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .config import load_runtime_config
from .errors import UsageError
from .frontmatter import split_frontmatter
from .link_format import format_link, normalize_internal_link_target
from .page_profiles import (
    logical_ref_to_relpath,
    render_page_text,
    split_page_text,
    update_page_text,
)
from .paths import (
    kind_to_folder,
    path_match_key,
    rel_to_vault,
    resolve_path_in_vault,
    slugify_title,
    source_md_files,
)
from .schema import load_vault_schema, note_kind
from .storage import write_text_atomic
from .templates import (
    TemplateContext,
    packaged_template_for_kind,
    render_template,
    template_path,
)
from .text import parse_json_list_or_none, parse_list_or_json


@dataclass(frozen=True)
class NoteScaffold:
    path: Path
    content: str
    kind: str
    title: str
    status: str
    sources: tuple[str, ...]
    related: tuple[str, ...]
    allow_incomplete: bool


def new_note(
    vault: Path,
    kind: str,
    title: str,
    sources: list[str],
    related: list[str] | None = None,
    status: str = "seed",
    summary: str = "Short summary.",
    body: str | None = None,
    body_file: str | None = None,
    path: str | None = None,
    dry_run: bool = False,
    allow_incomplete: bool = False,
) -> NoteScaffold:
    schema = load_vault_schema(vault)
    config = load_runtime_config(vault)
    kind_config = note_kind(schema, kind)
    related_list = related or []
    if not related_list and not allow_incomplete:
        raise UsageError("note new requires --related or --allow-incomplete")
    target = _note_target_path(vault, kind=kind, title=title, path=path, config=config)
    target.parent.mkdir(parents=True, exist_ok=True)
    note_path = rel_to_vault(vault, target)
    today = date.today().isoformat()
    normalized_sources = tuple(resolve_source_path(vault, source) for source in sources)
    normalized_related = tuple(
        normalize_related_path(vault, rel_path) for rel_path in related_list
    )
    content = render_note_content(
        vault=vault,
        kind=kind,
        title=title,
        summary=summary,
        created=today,
        updated=today,
        status=status,
        sources=list(normalized_sources),
        related=list(normalized_related),
        body=body,
        body_file=body_file,
        allow_incomplete=allow_incomplete,
        template_name=kind_config.template,
        note_path=note_path,
    )
    if not dry_run:
        write_text_atomic(target, content)
    return NoteScaffold(
        path=target,
        content=content,
        kind=kind,
        title=title,
        status=status,
        sources=normalized_sources,
        related=normalized_related,
        allow_incomplete=allow_incomplete,
    )


def render_note_content(
    *,
    vault: Path,
    kind: str,
    title: str,
    summary: str,
    created: str,
    updated: str,
    status: str,
    sources: list[str],
    related: list[str],
    body: str | None,
    body_file: str | None,
    allow_incomplete: bool,
    template_name: str | None = None,
    note_path: str | None = None,
) -> str:
    schema = load_vault_schema(vault)
    config = load_runtime_config(vault)
    kind_config = note_kind(schema, kind)
    default_data = {
        "tags": [kind_config.tag],
        "topics": [],
        "status": status,
        "created": created,
        "updated": updated,
        "sources": sources,
        "source_count": len(sources),
        "aliases": [],
    }
    if body and body_file:
        raise UsageError("use only one of --body or --body-file")
    if body is not None:
        return _finalize_rendered_note(
            body.rstrip() + "\n",
            default_data,
            config=config,
        )
    if body_file:
        return _finalize_rendered_note(
            Path(body_file).read_text(encoding="utf-8").rstrip() + "\n",
            default_data,
            config=config,
        )
    template_text = _load_note_template(
        vault, template_name or kind_config.template, kind
    )
    context = TemplateContext(
        title=title,
        slug=slugify_title(title),
        kind=kind,
        status=status,
        summary=summary,
        sources=tuple(sources),
        related=tuple(related),
        topics=(),
        aliases=(),
        now=datetime.fromisoformat(f"{created}T00:00:00"),
        link_config=config.links,
        source_path=note_path,
    )
    rendered = render_template(template_text, context)
    return _finalize_rendered_note(rendered, default_data, config=config)


def _note_target_path(
    vault: Path,
    *,
    kind: str,
    title: str,
    path: str | None,
    config: Any,
) -> Path:
    schema = load_vault_schema(vault)
    expected_folder = kind_to_folder(kind, schema=schema).rstrip("/")
    if path is None:
        slug = slugify_title(title)
        logical_ref = f"{expected_folder}/{slug}"
        return vault / logical_ref_to_relpath(logical_ref, config=config)

    requested = normalize_internal_link_target(path) or path
    rel = requested.replace("\\", "/")
    if not rel.endswith(".md"):
        rel = f"{rel}.md"
    if not rel.startswith(f"{expected_folder}/"):
        raise UsageError(f"note kind '{kind}' requires path under {expected_folder}/")
    return resolve_path_in_vault(vault, rel)


def _load_note_template(vault: Path, name: str, kind: str) -> str:
    candidate = template_path(vault, name)
    if candidate.exists():
        return candidate.read_text(encoding="utf-8")
    return packaged_template_for_kind(kind)


CLI_AUTHORITATIVE_FIELDS = (
    "tags",
    "topics",
    "status",
    "created",
    "updated",
    "sources",
    "source_count",
    "aliases",
)


def _finalize_rendered_note(
    rendered: str, default_data: dict[str, Any], *, config: Any
) -> str:
    text = rendered.rstrip() + "\n"
    if text.startswith("---\n"):
        data, body = split_frontmatter(text)
    else:
        data, body = {}, text
    normalized = dict(data)

    # CLI-provided core metadata is authoritative over template defaults.
    # Templates may contain stale values (e.g. sources: [], status: active,
    # old dates) that must not override the CLI options.
    for key in CLI_AUTHORITATIVE_FIELDS:
        if key in default_data:
            normalized[key] = default_data[key]

    sources = normalized.get("sources", [])
    if not isinstance(sources, list):
        sources = list(default_data["sources"])
        normalized["sources"] = sources
    normalized["source_count"] = len(sources)
    body_text = body.lstrip() if body else ""
    return render_page_text(normalized, body_text, config=config)


def _extract_body_source_links(vault: Path, body: str) -> list[str]:
    """Parse internal links in body that point to raw source directories."""
    import re

    # Extract wiki-style links: [[path]] or [[path|display]]
    link_pattern = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
    links = link_pattern.findall(body)
    source_links: list[str] = []
    for link in links:
        cleaned = link.strip()
        if not cleaned:
            continue
        # Check if this looks like a source path
        if cleaned.startswith("Raw/Sources/") or cleaned.startswith("Raw/Files/"):
            try:
                resolved = resolve_source_path(vault, cleaned)
                if resolved not in source_links:
                    source_links.append(resolved)
            except UsageError:
                continue
    return source_links


def normalize_note(vault: Path, note_path: str, fix: bool = False) -> dict[str, Any]:
    path = resolve_path_in_vault(vault, note_path)
    if not path.exists():
        raise UsageError(f"note not found: {note_path}")
    config = load_runtime_config(vault)
    text = path.read_text(encoding="utf-8")
    data, body = split_page_text(text, config=config)
    sources = _normalize_sources_field(vault, data.get("sources", []))
    updates: dict[str, Any] = {}
    if sources != data.get("sources", []):
        updates["sources"] = sources
    if int(data.get("source_count", 0)) != len(sources):
        updates["source_count"] = len(sources)

    # P1 fix: infer source frontmatter from body links when sources is empty.
    body_source_links = _extract_body_source_links(vault, body)
    if not sources and body_source_links:
        updates["sources"] = body_source_links
        updates["source_count"] = len(body_source_links)

    changed = bool(updates)
    if changed and fix:
        write_text_atomic(path, update_page_text(text, updates, config=config))
    return {
        "path": rel_to_vault(vault, path),
        "changed": changed,
        "applied": changed and fix,
        "updates": updates,
        "body_has_related": "## Related" in body,
        "body_has_sources": "## Sources" in body,
        "body_source_links": body_source_links,
    }


def normalize_source_path(value: str) -> str:
    from .paths import decode_unicode_escape_literals

    decoded = decode_unicode_escape_literals(value)
    cleaned = (
        (normalize_internal_link_target(decoded) or decoded).replace("\\", "/").strip()
    )
    if not cleaned:
        raise UsageError("empty source path")
    if cleaned.endswith(".md"):
        normalized = cleaned
    else:
        normalized = f"{cleaned}.md"
    if not normalized.startswith("Raw/"):
        if normalized.startswith("Sources/"):
            normalized = f"Raw/{normalized}"
        elif "/" not in normalized:
            normalized = f"Raw/Sources/{normalized}"
    return normalized


def find_source_path_matches(vault: Path, value: str) -> list[Path]:
    normalized = normalize_source_path(value)
    index = {rel_to_vault(vault, path): path for path in source_md_files(vault)}
    exact = index.get(normalized)
    if exact is not None:
        return [exact]
    wanted = path_match_key(normalized)
    matches = [path for rel, path in index.items() if path_match_key(rel) == wanted]
    if matches:
        return matches
    # Fallback: direct file check and directory listing for platforms
    # where Path.resolve() / rglob() may produce inconsistent paths.
    direct = vault / normalized
    if direct.is_file():
        return [direct]
    sources_dir = vault / "Raw/Sources"
    if sources_dir.is_dir():
        for f in sorted(sources_dir.iterdir()):
            if not f.is_file() or f.suffix != ".md":
                continue
            try:
                rel = f.relative_to(vault).as_posix()
            except ValueError:
                continue
            if path_match_key(rel) == wanted:
                matches.append(f)
    return matches


def suggest_source_paths(vault: Path, value: str, limit: int = 3) -> list[str]:
    from .search import rank_candidates
    from .search_backends import SourceBackend

    normalized = normalize_source_path(value)
    backend = SourceBackend(vault)
    candidates = backend.candidates(normalized)
    results = rank_candidates(normalized, candidates, limit=limit, cutoff=55.0)
    return [r.candidate.path or r.candidate.key for r in results][:limit]


def resolve_source_path(vault: Path, value: str) -> str:
    normalized = normalize_source_path(value)
    matches = find_source_path_matches(vault, normalized)
    if not matches:
        suggestions = suggest_source_paths(vault, normalized)
        if suggestions:
            raise UsageError(
                f"source path not found: {normalized}. suggestions: "
                f"{', '.join(suggestions)}"
            )
        raise UsageError(f"source path not found: {normalized}")
    if len(matches) > 1:
        candidates = ", ".join(rel_to_vault(vault, match) for match in matches)
        raise UsageError(
            f"ambiguous source path: {normalized}. candidates: {candidates}"
        )
    return rel_to_vault(vault, matches[0])


def normalize_related_path(vault: Path, value: str) -> str:
    from .paths import decode_unicode_escape_literals

    decoded = decode_unicode_escape_literals(value)
    cleaned = (normalize_internal_link_target(decoded) or decoded).replace("\\", "/")
    if not cleaned:
        raise UsageError("empty related path")
    if cleaned.startswith("Wiki/"):
        rel = cleaned if cleaned.endswith(".md") else f"{cleaned}.md"
        return rel
    candidate = resolve_path_in_vault(vault, cleaned)
    if candidate.exists():
        return rel_to_vault(vault, candidate)
    if cleaned.endswith(".md"):
        return cleaned
    return f"{cleaned}.md"


def related_body_lines(
    related: list[str],
    allow_incomplete: bool,
    *,
    vault: Path,
    source_path: str | None = None,
) -> str:
    config = load_runtime_config(vault)
    if related:
        return "\n".join(
            f"- {format_note_link(config.links, path, source_path=source_path)}"
            for path in related
        )
    if allow_incomplete:
        return "-"
    return ""


def source_body_lines(
    sources: list[str], *, vault: Path, source_path: str | None = None
) -> str:
    config = load_runtime_config(vault)
    if not sources:
        return "-"
    return "\n".join(
        f"- {format_note_link(config.links, path, source_path=source_path)}"
        for path in sources
    )


def format_note_link(
    link_config: Any, path: str, *, source_path: str | None = None
) -> str:  # noqa: E501
    normalized = (normalize_internal_link_target(path) or path).replace("\\", "/")
    return format_link(link_config, normalized, source_path=source_path)


def parse_multi_value(values: list[str]) -> list[str]:
    expanded: list[str] = []
    for value in values:
        expanded.extend(parse_list_or_json(value))
    return expanded


def parse_path_values(values: list[str]) -> list[str]:
    expanded: list[str] = []
    for value in values:
        stripped = value.strip()
        if not stripped:
            continue
        try:
            parsed = parse_json_list_or_none(stripped)
        except (json.JSONDecodeError, ValueError) as exc:
            raise UsageError(f"invalid JSON path list: {stripped}") from exc
        if parsed is not None:
            expanded.extend(item.strip() for item in parsed if item.strip())
            continue
        expanded.append(stripped)
    return expanded


def _normalize_sources_field(vault: Path, value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [resolve_source_path(vault, str(item)) for item in value]
