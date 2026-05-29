from __future__ import annotations

import json
import re
from collections.abc import Mapping

import yaml

from .errors import UsageError

FRONTMATTER_ORDER = [
    "title",
    "Title",
    "Author",
    "Reference",
    "ContentType",
    "Created",
    "Processed",
    "tags",
    "topics",
    "status",
    "created",
    "updated",
    "sources",
    "source_count",
    "aliases",
]


def split_frontmatter(text: str) -> tuple[dict[str, object], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    # Handle empty frontmatter: "---\n---\n..."
    if end == -1 and text.startswith("---\n", 4):
        end = 3
    if end == -1:
        raise UsageError("invalid frontmatter block: missing closing ---")
    block = text[4:end]
    body = text[end + 5 :]
    return parse_frontmatter_block(block), body


class WikiMasonSafeLoader(yaml.SafeLoader):
    pass


# Remove implicit timestamp resolver so ISO dates stay as strings.
for _ch, _resolvers in list(WikiMasonSafeLoader.yaml_implicit_resolvers.items()):
    WikiMasonSafeLoader.yaml_implicit_resolvers[_ch] = [
        (tag, regexp)
        for tag, regexp in _resolvers
        if tag != "tag:yaml.org,2002:timestamp"
    ]


_MUSTACHE_RE = re.compile(r"\{\{.*?\}\}")


def parse_frontmatter_block(block: str) -> dict[str, object]:
    # Wrap mustache template placeholders in quotes so PyYAML treats them as strings.
    safe_block = _MUSTACHE_RE.sub(lambda m: repr(m.group(0)), block)
    parsed = yaml.load(safe_block, Loader=WikiMasonSafeLoader)
    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        raise UsageError("frontmatter must be a mapping")
    return dict(parsed)


def canonical_json(data: Mapping[str, object]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def dump_frontmatter(data: Mapping[str, object]) -> str:
    return render_frontmatter(data)


def render_frontmatter_value(value: object, *, list_indent: str = "  ") -> str:
    if isinstance(value, list):
        if not value:
            return "[]"
        return "\n" + "\n".join(
            f"{list_indent}- {_render_scalar(item)}" for item in value
        )
    return _render_scalar(value)


def render_frontmatter(data: Mapping[str, object]) -> str:
    ordered_keys = [key for key in FRONTMATTER_ORDER if key in data] + sorted(
        key for key in data if key not in FRONTMATTER_ORDER
    )
    lines = ["---"]
    for key in ordered_keys:
        value = data[key]
        if isinstance(value, list):
            if not value:
                lines.append(f"{key}: []")
                continue
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {_render_scalar(item)}")
            continue
        lines.append(f"{key}: {_render_scalar(value)}")
    lines.append("---")
    return "\n".join(lines)


def update_frontmatter(text: str, updates: Mapping[str, object]) -> str:
    data, body = split_frontmatter(text)
    data.update(dict(updates))
    body = body.lstrip("\n")
    return (
        f"{render_frontmatter(data)}\n\n{body}"
        if body
        else f"{render_frontmatter(data)}\n"
    )


def _render_scalar(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    text = str(value)
    if text == "":
        return '""'
    if _needs_quotes(text):
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return text


def _needs_quotes(value: str) -> bool:
    if value != value.strip():
        return True
    if any(char in value for char in [":", "#", "[", "]"]):
        return True
    if value.lower() in {"true", "false", "null", "none"}:
        return True
    return False
