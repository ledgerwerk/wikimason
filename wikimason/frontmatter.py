from __future__ import annotations

from collections.abc import Mapping

from ledgercore.errors import FrontMatterError
from ledgercore.frontmatter import split_front_matter_text
from ledgercore.jsonio import canonical_json as _canonical_json

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
    """Split YAML front matter from *text*.

    Delegates parsing to ledgercore so this module no longer imports ``yaml``
    directly and gains timestamp-safe loading plus mustache-placeholder quoting.
    Missing front matter returns ``({}, original_text)``. YAML timestamps are
    preserved as strings, and mustache ``{{ name }}`` placeholders are treated
    as strings anywhere in a value. ``FrontMatterError`` from ledgercore is
    converted to ``UsageError`` at this module boundary.
    """
    try:
        return split_front_matter_text(
            text,
            missing="empty",
            preserve_yaml_timestamps_as_strings=True,
            quote_template_placeholders="anywhere",
        )
    except FrontMatterError as exc:
        raise UsageError(str(exc)) from exc


def canonical_json(data: Mapping[str, object]) -> str:
    return _canonical_json(data)


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
    # Rendering stays WikiMason-local. It is pure string manipulation (no yaml
    # import) and encodes behavior tests rely on: key order via
    # FRONTMATTER_ORDER then sorted remaining keys, nested values rendered via
    # their str() repr, and the historical scalar quoting rules. ledgercore's
    # minimal renderer refuses nested mappings (e.g. ``Created: {date: ...}``
    # from source_scan.py) and its pyyaml style would change byte output, so
    # neither is a behavior-preserving drop-in here.
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
    # Do not delegate to ledgercore.update_front_matter_text(): it renders the
    # body immediately after the closing ``---``. WikiMason inserts a blank
    # line between the closing delimiter and the body, which is user-visible
    # and covered by existing behavior.
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
