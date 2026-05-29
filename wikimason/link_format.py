from __future__ import annotations

import posixpath
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from .config import LinkConfig
from .page_profiles import default_logical_ref_for_path
from .wikilinks import WIKILINK_RE, normalize_wikilink_name

MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)")
INLINE_CODE_RE = re.compile(r"`[^`]+`")
_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")


@dataclass(frozen=True)
class ParsedLink:
    raw: str
    style: str
    query: str
    target_path: str | None
    label: str | None
    fragment: str | None
    start: int
    end: int



def iter_link_scan_lines(text: str) -> Iterator[tuple[int, str]]:
    """Yield (line_number, line_text) skipping fenced code blocks and inline code spans.

    Lines inside fenced code blocks (triple backticks or tildes) are
    excluded entirely.  Inline backtick spans within non-fenced lines
    are replaced with empty strings so that links inside them are
    invisible to link extractors.
    """
    in_fence = False
    fence_char = ""
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        fence_match = _FENCE_RE.match(stripped)
        if fence_match:
            if not in_fence:
                in_fence = True
                fence_char = fence_match.group(1)[0]
                continue
            else:
                if (
                    stripped[0] == fence_char
                    and len(stripped.lstrip(fence_char)) == 0
                ):
                    in_fence = False
                    fence_char = ""
                continue
        if in_fence:
            continue
        # Strip inline code spans
        cleaned = INLINE_CODE_RE.sub("", raw_line)
        yield line_number, cleaned

def default_link_label(target_path: str) -> str:
    logical = default_logical_ref_for_path(target_path)
    normalized = (
        logical or target_path.replace("\\", "/").removesuffix(".md")
    ).replace("\\", "/")
    return Path(normalized).name.replace("-", " ")


def format_link(
    link_config: LinkConfig,
    target_path: str,
    *,
    label: str | None = None,
    source_path: str | Path | None = None,
    fragment: str | None = None,
) -> str:
    normalized_target = _normalize_path_text(target_path)
    rendered_target = _render_target(
        normalized_target, target_mode=link_config.target, source_path=source_path
    )
    if fragment:
        rendered_target = f"{rendered_target}#{fragment}"
    rendered_label = label or default_link_label(normalized_target)
    return link_config.template.format(target=rendered_target, label=rendered_label)


def normalize_internal_link_target(
    value: str, *, source_path: str | Path | None = None
) -> str | None:
    parsed = parse_link_value(value, source_path=source_path)
    if parsed.target_path:
        return parsed.target_path
    if parsed.query:
        return _canonicalize_target(parsed.query, source_path=source_path)
    return None


def parse_link_value(
    value: str, *, source_path: str | Path | None = None
) -> ParsedLink:
    raw = value.strip()
    if raw.startswith("[[") and raw.endswith("]]"):
        query, label, fragment = _split_target_and_label(normalize_wikilink_name(raw))
        return ParsedLink(
            raw=raw,
            style="wikilink",
            query=query,
            target_path=_canonicalize_target(query, source_path=source_path),
            label=label,
            fragment=fragment,
            start=0,
            end=len(raw),
        )
    markdown = MARKDOWN_LINK_RE.fullmatch(raw)
    if markdown:
        label = markdown.group(1).strip() or None
        target, fragment = _split_markdown_target(markdown.group(2))
        return ParsedLink(
            raw=raw,
            style="markdown",
            query=target,
            target_path=_canonicalize_target(target, source_path=source_path),
            label=label,
            fragment=fragment,
            start=0,
            end=len(raw),
        )
    fragment = None
    query = raw
    if "#" in raw:
        query, fragment = raw.split("#", 1)
    return ParsedLink(
        raw=raw,
        style="plain",
        query=query.strip(),
        target_path=_canonicalize_target(query, source_path=source_path),
        label=None,
        fragment=fragment.strip() if fragment else None,
        start=0,
        end=len(raw),
    )


def extract_internal_links(
    text: str, *, vault: Path, source_path: str | Path | None = None
) -> list[ParsedLink]:
    matches: list[ParsedLink] = []
    for match in WIKILINK_RE.finditer(text):
        query, label, fragment = _split_target_and_label(
            normalize_wikilink_name(match.group(0))
        )
        matches.append(
            ParsedLink(
                raw=match.group(0),
                style="wikilink",
                query=query,
                target_path=_canonicalize_target(query, source_path=source_path),
                label=label,
                fragment=fragment,
                start=match.start(),
                end=match.end(),
            )
        )
    for match in MARKDOWN_LINK_RE.finditer(text):
        target, fragment = _split_markdown_target(match.group(2))
        canonical = _canonicalize_target(target, source_path=source_path)
        if canonical is None:
            continue
        matches.append(
            ParsedLink(
                raw=match.group(0),
                style="markdown",
                query=target,
                target_path=canonical,
                label=match.group(1).strip() or None,
                fragment=fragment,
                start=match.start(),
                end=match.end(),
            )
        )
    matches.sort(key=lambda item: item.start)
    return matches


def extract_internal_link_targets(
    text: str, *, vault: Path, source_path: str | Path | None = None
) -> list[str]:
    targets: list[str] = []
    seen: set[str] = set()
    for link in extract_internal_links(text, vault=vault, source_path=source_path):
        target = link.target_path or link.query
        if target in seen:
            continue
        seen.add(target)
        targets.append(target)
    return targets


def has_internal_links(
    text: str, *, vault: Path, source_path: str | Path | None = None
) -> bool:
    return bool(extract_internal_links(text, vault=vault, source_path=source_path))


def link_candidate_keys(
    value: str | ParsedLink, *, source_path: str | Path | None = None
) -> set[str]:
    parsed = (
        value
        if isinstance(value, ParsedLink)
        else parse_link_value(value, source_path=source_path)
    )
    raw = parsed.target_path or parsed.query
    if not raw:
        return set()
    no_ext = raw.removesuffix(".md")
    candidates = {
        raw,
        no_ext,
        f"{no_ext}.md",
        Path(no_ext).name,
        Path(no_ext).name.lower(),
        raw.lower(),
        no_ext.lower(),
    }
    return {candidate for candidate in candidates if candidate}


def link_resolves(link: str, targets: set[str]) -> bool:
    """Return True if *link* resolves to any key in *targets*."""
    return bool(link_candidate_keys(link) & targets)


def _split_target_and_label(value: str) -> tuple[str, str | None, str | None]:
    target = value
    label = None
    if "|" in target:
        target, label = target.split("|", 1)
        label = label.strip() or None
    fragment = None
    if "#" in target:
        target, fragment = target.split("#", 1)
    elif "^" in target:
        target, fragment = target.split("^", 1)
    return target.strip(), label, fragment.strip() if fragment else None


def _split_markdown_target(value: str) -> tuple[str, str | None]:
    target = value.strip()
    if " " in target and (target.endswith('"') or target.endswith("')")):
        target = target.rsplit(" ", 1)[0]
    fragment = None
    if "#" in target:
        target, fragment = target.split("#", 1)
    return target.strip(), fragment.strip() if fragment else None


def _canonicalize_target(
    value: str, *, source_path: str | Path | None = None
) -> str | None:
    from .paths import decode_unicode_escape_literals

    raw = decode_unicode_escape_literals(value.strip()).replace("\\", "/")
    if not raw or raw.startswith("#"):
        return None
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", raw):
        return None
    if raw.startswith("//"):
        return None
    if raw.startswith("/"):
        normalized = posixpath.normpath(raw.lstrip("/"))
    elif _looks_vault_relative(raw):
        normalized = posixpath.normpath(raw)
    elif "/" in raw or raw.endswith(".md"):
        source_rel = _source_rel(source_path)
        base = posixpath.dirname(source_rel) if source_rel else ""
        normalized = posixpath.normpath(posixpath.join(base, raw))
    else:
        normalized = raw
    if normalized in {".", ""} or normalized.startswith("../"):
        return None
    if normalized.endswith("/"):
        return None
    if "." in Path(normalized).name and not normalized.endswith(".md"):
        return None
    if not normalized.endswith(".md"):
        normalized = f"{normalized}.md"
    return _normalize_path_text(normalized)


def _render_target(
    target_path: str, *, target_mode: str, source_path: str | Path | None = None
) -> str:
    normalized = _normalize_path_text(target_path)
    if target_mode == "path_no_ext":
        logical = default_logical_ref_for_path(normalized)
        return logical if logical is not None else normalized.removesuffix(".md")
    if target_mode == "relative_md":
        source_rel = _source_rel(source_path)
        if source_rel:
            start = posixpath.dirname(source_rel) or "."
            return posixpath.relpath(normalized, start=start)
        return normalized
    return normalized


def _normalize_path_text(value: str) -> str:
    normalized = posixpath.normpath(value.replace("\\", "/"))
    if normalized == ".":
        return ""
    return normalized


def _source_rel(value: str | Path | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, Path):
        return value.as_posix()
    return value.replace("\\", "/")


def _looks_vault_relative(value: str) -> bool:
    return value.startswith(
        (
            "Wiki/",
            "Raw/",
            "Schema/",
            "_templates/",
            ".obsidian/",
            "pages/",
            "journals/",
            "logseq/",
            ".logseq/",
        )
    )
