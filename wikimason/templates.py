from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .config import LinkConfig
from .errors import UsageError
from .frontmatter import render_frontmatter_value
from .link_format import format_link, normalize_internal_link_target
from .note_types import display_type_for_kind

TEMPLATE_RE = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")

SOURCE_TEMPLATE = """---
type: Source
Title: "{{title}}"
Author: ""
Reference: ""
ContentType:
  - note
Created: {{date}}
Processed: false
tags:
  - source
---

# {{title}}

Short source summary.

## Notes

-
"""

TOPIC_TEMPLATE = """---
type: {{type}}
tags:
  - topic
topics: {{topics_yaml}}
status: {{status}}
created: {{date}}
updated: {{date}}
sources: {{sources_yaml}}
source_count: {{source_count}}
aliases: {{aliases_yaml}}
---

# {{title}}

{{summary}}

## Scope

Define the topic boundary.

## Related

{{related_links}}

## Sources

{{sources_links}}
"""

CONCEPT_TEMPLATE = """---
type: {{type}}
tags:
  - concept
topics: {{topics_yaml}}
status: {{status}}
created: {{date}}
updated: {{date}}
sources: {{sources_yaml}}
source_count: {{source_count}}
aliases: {{aliases_yaml}}
---

# {{title}}

{{summary}}

## Details

Explain the concept in one place without duplicating raw source text.

## Related

{{related_links}}

## Sources

{{sources_links}}
"""

ENTITY_TEMPLATE = """---
type: {{type}}
tags:
  - entity
topics: {{topics_yaml}}
status: {{status}}
created: {{date}}
updated: {{date}}
sources: {{sources_yaml}}
source_count: {{source_count}}
aliases: {{aliases_yaml}}
---

# {{title}}

{{summary}}

## Details

Describe the entity and why it matters to the wiki.

## Related

{{related_links}}

## Sources

{{sources_links}}
"""

PROJECT_TEMPLATE = """---
type: {{type}}
tags:
  - project
topics: {{topics_yaml}}
status: {{status}}
created: {{date}}
updated: {{date}}
sources: {{sources_yaml}}
source_count: {{source_count}}
aliases: {{aliases_yaml}}
---

# {{title}}

{{summary}}

## Status

Current state and next actions.

## Related

{{related_links}}

## Sources

{{sources_links}}
"""

LOG_TEMPLATE = """---
type: {{type}}
tags:
  - log
topics: {{topics_yaml}}
status: {{status}}
created: {{date}}
updated: {{date}}
sources: {{sources_yaml}}
source_count: {{source_count}}
aliases: {{aliases_yaml}}
---

# {{title}}

{{summary}}

## Details

-

## Related

{{related_links}}

## Sources

{{sources_links}}
"""

PACKAGED_TEMPLATES = {
    "source-note.md": SOURCE_TEMPLATE,
    "topic-note.md": TOPIC_TEMPLATE,
    "concept-note.md": CONCEPT_TEMPLATE,
    "entity-note.md": ENTITY_TEMPLATE,
    "project-note.md": PROJECT_TEMPLATE,
    "log-note.md": LOG_TEMPLATE,
}


@dataclass(frozen=True)
class TemplateContext:
    title: str
    slug: str
    kind: str
    status: str
    summary: str
    sources: tuple[str, ...]
    related: tuple[str, ...]
    topics: tuple[str, ...]
    aliases: tuple[str, ...]
    now: datetime
    link_config: LinkConfig | None = None
    source_path: str | None = None


def packaged_template(name: str) -> str:
    normalized = _normalized_template_slug(name)
    file_name = normalized if normalized.endswith(".md") else f"{normalized}.md"
    try:
        return PACKAGED_TEMPLATES[file_name]
    except KeyError as exc:
        raise UsageError(f"unknown packaged template: {name}") from exc


def packaged_template_for_kind(kind: str) -> str:
    return packaged_template(f"{kind}-note.md")


def resolve_template(text: str, title: str, **values: str) -> str:
    now = datetime.now()
    context = TemplateContext(
        title=title,
        slug=values.get("slug", ""),
        kind=values.get("kind", ""),
        status=values.get("status", ""),
        summary=values.get("summary", ""),
        sources=(),
        related=(),
        topics=(),
        aliases=(),
        now=now,
        link_config=None,
        source_path=None,
    )
    return render_template(text, context, extra_values=values)


def render_template(
    text: str,
    context: TemplateContext,
    *,
    extra_values: dict[str, str] | None = None,
) -> str:
    values = _template_values(context)
    if extra_values:
        values.update(extra_values)

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            return match.group(0)
        value = values[key]
        if "\n" not in value or value.startswith("\n"):
            return value
        line_start = text.rfind("\n", 0, match.start()) + 1
        indent = " " * (match.start() - line_start)
        first, *rest = value.splitlines()
        return "\n".join([first, *[(indent + line) if line else line for line in rest]])

    return TEMPLATE_RE.sub(replace, text)


def template_path(vault: Path, name: str) -> Path:
    base = (vault / "_templates").resolve()
    slug = _normalized_template_slug(name).removesuffix(".md")
    if not slug:
        raise UsageError("template name cannot be empty")
    candidates: list[Path] = []
    for candidate_name in (f"{slug}.md", f"{slug}-note.md"):
        candidate = base / candidate_name
        resolved = candidate.resolve()
        try:
            resolved.relative_to(base)
        except ValueError as exc:
            raise UsageError(f"template path escapes _templates: {name}") from exc
        candidates.append(resolved)
        if resolved.exists():
            return resolved
    return candidates[-1]


def list_templates(vault: Path) -> list[str]:
    return sorted(path.stem for path in (vault / "_templates").glob("*.md"))


def read_template_file(vault: Path, name: str) -> str:
    path = template_path(vault, name)
    if not path.exists():
        raise UsageError(f"template not found: {name}")
    return path.read_text(encoding="utf-8")


def render_template_file(vault: Path, name: str, title: str = "") -> str:
    now = datetime.now()
    return render_template(
        read_template_file(vault, name),
        TemplateContext(
            title=title,
            slug=_normalized_template_slug(title),
            kind="",
            status="",
            summary="",
            sources=(),
            related=(),
            topics=(),
            aliases=(),
            now=now,
            link_config=None,
            source_path=None,
        ),
    )


def _normalized_template_slug(name: str) -> str:
    return name.strip().lower().replace(" ", "-")


def _template_values(context: TemplateContext) -> dict[str, str]:
    return {
        "type": display_type_for_kind(context.kind) if context.kind else "",
        "title": context.title,
        "slug": context.slug,
        "kind": context.kind,
        "date": context.now.date().isoformat(),
        "time": context.now.strftime("%H:%M"),
        "datetime": context.now.isoformat(timespec="seconds"),
        "summary": context.summary,
        "status": context.status,
        "sources_yaml": render_frontmatter_value(list(context.sources)),
        "sources_links": _bullet_links_with_context(
            context.sources,
            link_config=context.link_config,
            source_path=context.source_path,
        ),
        "related_yaml": render_frontmatter_value(list(context.related)),
        "related_links": _bullet_links_with_context(
            context.related,
            link_config=context.link_config,
            source_path=context.source_path,
        ),
        "topics_yaml": render_frontmatter_value(list(context.topics)),
        "aliases_yaml": render_frontmatter_value(list(context.aliases)),
        "source_count": str(len(context.sources)),
    }


def _bullet_links(values: tuple[str, ...]) -> str:
    if not values:
        return "-"
    return "\n".join(f"- {_as_link(value)}" for value in values)


def _bullet_links_with_context(
    values: tuple[str, ...],
    *,
    link_config: LinkConfig | None,
    source_path: str | None,
) -> str:
    if not values:
        return "-"
    return "\n".join(
        f"- {_as_link(value, link_config=link_config, source_path=source_path)}"
        for value in values
    )


def _as_link(
    path: str, *, link_config: LinkConfig | None = None, source_path: str | None = None
) -> str:
    normalized = (normalize_internal_link_target(path) or path).replace("\\", "/")
    if link_config is None:
        target = normalized.removesuffix(".md")
        label = Path(target).name.replace("-", " ")
        return f"[[{target}|{label}]]"
    return format_link(link_config, normalized, source_path=source_path)
