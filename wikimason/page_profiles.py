from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .config import WikiMasonConfig, load_runtime_config
from .errors import UsageError
from .frontmatter import render_frontmatter, split_frontmatter
from .text import parse_list_or_json

_HEADING_RE = re.compile(r"^(#{1,6})\s+.+$")
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*]|\d+\.)\s+.+$")
_PROPERTY_LINE_RE = re.compile(r"^- ([^:\n]+)::\s*(.*)$")
_OUTLINE_LINE_RE = re.compile(r"^(?P<indent>(?:  )*)-(?: (?P<content>.*))?$")
_LOGSEQ_LIST_FIELDS = {"aliases", "sources", "tags", "topics"}


def normalize_logical_ref(value: str) -> str:
    raw = value.replace("\\", "/").strip()
    if raw.endswith(".md"):
        raw = raw[:-3]
    normalized = posixpath.normpath(raw)
    if normalized in {"", "."}:
        raise UsageError("page reference must not be empty")
    if normalized.startswith("../") or normalized == "..":
        raise UsageError("page reference must stay inside the wiki")
    if normalized.startswith("/"):
        normalized = normalized.lstrip("/")
    segments = normalized.split("/")
    if any(segment in {"", ".", ".."} for segment in segments):
        raise UsageError(f"invalid page reference: {value}")
    return normalized


@dataclass(frozen=True)
class PageRef:
    logical_path: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "logical_path", normalize_logical_ref(self.logical_path)
        )

    @property
    def segments(self) -> tuple[str, ...]:
        return tuple(self.logical_path.split("/"))


@dataclass(frozen=True)
class _OutlineBlock:
    depth: int
    content: str


class PageProfile(Protocol):
    @property
    def name(self) -> str: ...

    def logical_to_relpath(self, ref: PageRef) -> str: ...

    def relpath_to_ref(self, relpath: str) -> PageRef | None: ...

    def split_text(self, text: str) -> tuple[dict[str, Any], str]: ...

    def render_text(self, metadata: dict[str, Any], body: str) -> str: ...

    def update_text(self, text: str, updates: dict[str, Any]) -> str: ...


@dataclass(frozen=True)
class YamlPageProfile:
    name: str
    pages_dir: str

    def logical_to_relpath(self, ref: PageRef) -> str:
        logical = ref.logical_path
        return f"{logical}.md"

    def relpath_to_ref(self, relpath: str) -> PageRef | None:
        normalized = relpath.replace("\\", "/")
        if not normalized.endswith(".md"):
            return None
        return PageRef(normalized.removesuffix(".md"))

    def split_text(self, text: str) -> tuple[dict[str, Any], str]:
        return split_frontmatter(text)

    def render_text(self, metadata: dict[str, Any], body: str) -> str:
        clean_body = body.lstrip("\n")
        if clean_body:
            return f"{render_frontmatter(metadata)}\n\n{clean_body.rstrip()}\n"
        return f"{render_frontmatter(metadata)}\n"

    def update_text(self, text: str, updates: dict[str, Any]) -> str:
        data, body = self.split_text(text)
        merged = dict(data)
        merged.update(updates)
        return self.render_text(merged, body)


@dataclass(frozen=True)
class LogseqPageProfile:
    name: str
    pages_dir: str
    namespace_separator: str

    def logical_to_relpath(self, ref: PageRef) -> str:
        if any(self.namespace_separator in segment for segment in ref.segments):
            raise UsageError(
                f"logical page reference cannot contain {self.namespace_separator!r}"
            )
        stem = self.namespace_separator.join(ref.segments)
        return f"{self.pages_dir}/{stem}.md"

    def relpath_to_ref(self, relpath: str) -> PageRef | None:
        normalized = relpath.replace("\\", "/")
        prefix = f"{self.pages_dir}/"
        if not normalized.startswith(prefix) or not normalized.endswith(".md"):
            return None
        stem = normalized[len(prefix) :].removesuffix(".md")
        if not stem:
            return None
        parts = [part for part in stem.split(self.namespace_separator) if part]
        if not parts:
            return None
        return PageRef("/".join(parts))

    def split_text(self, text: str) -> tuple[dict[str, Any], str]:
        lines = text.splitlines()
        metadata: dict[str, Any] = {}
        index = 0
        while index < len(lines):
            line = lines[index]
            stripped = line.strip()
            if not stripped and not metadata:
                index += 1
                continue
            match = _PROPERTY_LINE_RE.fullmatch(line)
            if match is None:
                break
            key = match.group(1).strip()
            metadata[key] = _parse_logseq_property(key, match.group(2).strip())
            index += 1
        body = _logseq_blocks_to_markdown(lines[index:])
        return metadata, body

    def render_text(self, metadata: dict[str, Any], body: str) -> str:
        property_lines = _render_logseq_properties(metadata)
        body_lines = _markdown_to_logseq_blocks(body)
        parts: list[str] = []
        if property_lines:
            parts.extend(property_lines)
        if property_lines and body_lines:
            parts.append("")
        parts.extend(body_lines)
        return ("\n".join(parts).rstrip() + "\n") if parts else ""

    def update_text(self, text: str, updates: dict[str, Any]) -> str:
        data, body = self.split_text(text)
        merged = dict(data)
        merged.update(updates)
        return self.render_text(merged, body)


def profile_for_config(config: WikiMasonConfig) -> PageProfile:
    if config.profile_config.property_style == "logseq":
        return LogseqPageProfile(
            name=config.profile,
            pages_dir=config.profile_config.pages_dir,
            namespace_separator=config.profile_config.namespace_separator,
        )
    return YamlPageProfile(
        name=config.profile, pages_dir=config.profile_config.pages_dir
    )


def profile_for_vault(
    vault: Path, config: WikiMasonConfig | None = None
) -> PageProfile:
    return profile_for_config(config or load_runtime_config(vault))


def split_page_text(
    text: str, *, config: WikiMasonConfig | None = None, vault: Path | None = None
) -> tuple[dict[str, Any], str]:
    active_config = _require_config(config=config, vault=vault)
    return profile_for_config(active_config).split_text(text)


def render_page_text(
    metadata: dict[str, Any],
    body: str,
    *,
    config: WikiMasonConfig | None = None,
    vault: Path | None = None,
) -> str:
    active_config = _require_config(config=config, vault=vault)
    return profile_for_config(active_config).render_text(metadata, body)


def update_page_text(
    text: str,
    updates: dict[str, Any],
    *,
    config: WikiMasonConfig | None = None,
    vault: Path | None = None,
) -> str:
    active_config = _require_config(config=config, vault=vault)
    return profile_for_config(active_config).update_text(text, updates)


def logical_ref_to_relpath(
    logical_ref: str,
    *,
    config: WikiMasonConfig | None = None,
    vault: Path | None = None,
) -> str:
    active_config = _require_config(config=config, vault=vault)
    return profile_for_config(active_config).logical_to_relpath(PageRef(logical_ref))


def relpath_to_logical_ref(
    relpath: str,
    *,
    config: WikiMasonConfig | None = None,
    vault: Path | None = None,
) -> str | None:
    active_config = _require_config(config=config, vault=vault)
    ref = profile_for_config(active_config).relpath_to_ref(relpath)
    if ref is None:
        return None
    return ref.logical_path


def default_logical_ref_for_path(relpath: str) -> str | None:
    normalized = relpath.replace("\\", "/")
    if not normalized.endswith(".md"):
        return None
    if normalized.startswith("pages/"):
        stem = normalized[len("pages/") :].removesuffix(".md")
        return "/".join(part for part in stem.split("___") if part)
    return normalized.removesuffix(".md")


def _require_config(
    *, config: WikiMasonConfig | None, vault: Path | None
) -> WikiMasonConfig:
    if config is not None:
        return config
    if vault is None:
        raise UsageError("page profile helpers require config or vault")
    return load_runtime_config(vault)


def _parse_logseq_property(name: str, value: str) -> object:
    if name in _LOGSEQ_LIST_FIELDS:
        return parse_list_or_json(value)
    return value


def _render_logseq_properties(metadata: dict[str, Any]) -> list[str]:
    preferred = [
        "type",
        "title",
        "summary",
        "tags",
        "topics",
        "status",
        "created",
        "updated",
        "sources",
        "source_count",
        "aliases",
    ]
    rows: list[str] = []
    seen: set[str] = set()
    for key in [*preferred, *sorted(metadata)]:
        if key in seen or key not in metadata:
            continue
        seen.add(key)
        rows.append(f"- {key}:: {_render_logseq_property(metadata[key])}")
    return rows


def _render_logseq_property(value: object) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def _markdown_to_logseq_blocks(body: str) -> list[str]:
    if not body.strip():
        return []
    heading_levels: list[int] = []
    blocks: list[_OutlineBlock] = []
    lines = body.rstrip().splitlines()
    in_code = False
    code_parent_depth = 0
    for raw_line in lines:
        line = raw_line.rstrip()
        if in_code:
            blocks.append(_OutlineBlock(code_parent_depth + 1, raw_line))
            if raw_line.strip() == "```":
                in_code = False
            continue
        if not line:
            blocks.append(_OutlineBlock(len(heading_levels), ""))
            continue
        if _HEADING_RE.match(line):
            level = len(line) - len(line.lstrip("#"))
            while heading_levels and heading_levels[-1] >= level:
                heading_levels.pop()
            heading_levels.append(level)
            blocks.append(_OutlineBlock(len(heading_levels) - 1, line))
            continue
        if line.startswith("```"):
            code_parent_depth = len(heading_levels)
            blocks.append(_OutlineBlock(code_parent_depth, line))
            in_code = True
            continue
        if _LIST_ITEM_RE.match(raw_line):
            blocks.append(
                _OutlineBlock(
                    len(heading_levels) + _list_depth(raw_line), line.lstrip()
                )
            )
            continue
        blocks.append(_OutlineBlock(len(heading_levels), line))
    return [_render_outline_block(block) for block in blocks]


def _render_outline_block(block: _OutlineBlock) -> str:
    prefix = "  " * block.depth + "-"
    if block.content:
        return f"{prefix} {block.content}"
    return prefix


def _logseq_blocks_to_markdown(lines: list[str]) -> str:
    if not lines:
        return ""
    blocks = _parse_outline_blocks(lines)
    markdown_lines: list[str] = []
    heading_depth = 0
    in_code = False
    code_depth = 0
    for block in blocks:
        content = block.content
        if not content:
            markdown_lines.append("")
            continue
        if in_code:
            markdown_lines.append(content)
            if content.strip() == "```" and block.depth == code_depth + 1:
                in_code = False
            continue
        if _HEADING_RE.match(content):
            heading_depth = block.depth + 1
            markdown_lines.append(content)
            continue
        if content.startswith("```"):
            code_depth = block.depth
            markdown_lines.append(content)
            in_code = True
            continue
        if _LIST_ITEM_RE.match(content):
            indent = "  " * max(0, block.depth - heading_depth)
            markdown_lines.append(f"{indent}{content}")
            continue
        markdown_lines.append(content)
    return "\n".join(markdown_lines).rstrip() + "\n"


def _parse_outline_blocks(lines: list[str]) -> list[_OutlineBlock]:
    blocks: list[_OutlineBlock] = []
    for line in lines:
        if not line.strip():
            continue
        match = _OUTLINE_LINE_RE.fullmatch(line.expandtabs(2))
        if match is None:
            if blocks:
                previous = blocks[-1]
                blocks[-1] = _OutlineBlock(
                    depth=previous.depth,
                    content=f"{previous.content}\n{line}",
                )
            continue
        indent = match.group("indent") or ""
        content = match.group("content") or ""
        blocks.append(_OutlineBlock(depth=len(indent) // 2, content=content))
    return blocks


def _list_depth(line: str) -> int:
    stripped = line.lstrip(" ")
    return max(0, (len(line) - len(stripped)) // 2)
