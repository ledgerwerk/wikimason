from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .catalog import extract_title
from .config import load_runtime_config
from .frontmatter import split_frontmatter
from .link_format import (
    ParsedLink,
    extract_internal_link_targets,
    extract_internal_links,
    format_link,
    link_candidate_keys,
)
from .page_profiles import render_page_text, split_page_text
from .paths import (
    build_link_targets,
    compiled_md_files,
    rel_to_vault,
    resolve_path_in_vault,
)


@dataclass(frozen=True)
class LinkMatch:
    path: str
    wikilink: str
    title: str
    kind: str
    score: int


@dataclass(frozen=True)
class LinkCheckFinding:
    path: str
    line: int
    link: str
    status: str
    suggestions: tuple[str, ...]


@dataclass(frozen=True)
class LinkNormalization:
    path: str
    changed: bool
    replacements: tuple[dict[str, Any], ...]
    applied: bool


def outgoing_links(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    vault = _vault_root_for(path)
    rel = path.relative_to(vault).as_posix()
    return sorted(
        set(extract_internal_link_targets(text, vault=vault, source_path=rel))
    )


def backlinks(vault: Path, target: str) -> list[str]:
    target_keys = link_candidate_keys(target)
    found: list[str] = []
    for p in sorted(vault.rglob("*.md")):
        rel = p.relative_to(vault).as_posix()
        names = extract_internal_links(
            p.read_text(encoding="utf-8"), vault=vault, source_path=rel
        )
        if any(link_candidate_keys(name) & target_keys for name in names):
            found.append(p.relative_to(vault).as_posix())
    return found


def unresolved_links(vault: Path) -> list[str]:
    all_md = sorted(vault.rglob("*.md"))
    link_targets = build_link_targets(vault)
    unresolved: set[str] = set()
    for path in all_md:
        rel = path.relative_to(vault).as_posix()
        for link in extract_internal_links(
            path.read_text(encoding="utf-8"), vault=vault, source_path=rel
        ):
            if not _link_resolves(link, link_targets):
                unresolved.add(link.query)
    return sorted(unresolved)


def orphan_notes(vault: Path) -> list[str]:
    all_md = sorted(vault.rglob("*.md"))
    incoming: dict[str, int] = {
        path.name.removesuffix(".md").lower(): 0 for path in all_md
    }
    for path in all_md:
        rel = path.relative_to(vault).as_posix()
        for link in extract_internal_links(
            path.read_text(encoding="utf-8"), vault=vault, source_path=rel
        ):
            key = Path(link.target_path or link.query).name.lower().removesuffix(".md")
            if key in incoming:
                incoming[key] += 1
    return sorted(key for key, count in incoming.items() if count == 0)


def deadend_notes(vault: Path) -> list[str]:
    rows: list[str] = []
    for path in sorted(vault.rglob("*.md")):
        rel = path.relative_to(vault).as_posix()
        if not extract_internal_links(
            path.read_text(encoding="utf-8"), vault=vault, source_path=rel
        ):
            rows.append(rel_to_vault(vault, path))
    return rows


def resolve_link_matches(vault: Path, query: str, limit: int = 10) -> list[LinkMatch]:
    raw = query.replace("\\", "/").strip()
    lower = raw.lower()
    config = load_runtime_config(vault)
    entries: dict[str, LinkMatch] = {}
    for entry in _iter_link_entries(vault):
        score = _score_link_entry(entry, raw, lower)
        if score <= 0:
            continue
        current = entries.get(entry["path"])
        match = LinkMatch(
            path=entry["path"],
            wikilink=format_link(config.links, entry["path"], label=entry["title"]),
            title=entry["title"],
            kind=entry["kind"],
            score=score,
        )
        if current is None or match.score > current.score:
            entries[match.path] = match
    matches = sorted(entries.values(), key=lambda row: (-row.score, row.path))
    return matches[:limit]


def resolve_best_wikilink(
    vault: Path, query: str, *, source_path: str | None = None
) -> str | None:
    matches = resolve_link_matches(vault, query, limit=2)
    if len(matches) != 1:
        return None
    if matches[0].score < 80:
        return None
    config = load_runtime_config(vault)
    return format_link(
        config.links, matches[0].path, label=matches[0].title, source_path=source_path
    )


def check_links(vault: Path) -> list[LinkCheckFinding]:
    findings: list[LinkCheckFinding] = []
    link_targets = build_link_targets(vault)
    for path in compiled_md_files(vault):
        rel = rel_to_vault(vault, path)
        lines = path.read_text(encoding="utf-8").splitlines()
        for line_number, line in enumerate(lines, start=1):
            for link in extract_internal_links(line, vault=vault, source_path=rel):
                raw_link = link.query
                if _link_resolves(link, link_targets):
                    continue
                suggestions = tuple(
                    entry.wikilink
                    for entry in resolve_link_matches(vault, raw_link, limit=3)
                    if entry.score >= 50
                )
                findings.append(
                    LinkCheckFinding(
                        path=rel,
                        line=line_number,
                        link=raw_link,
                        status="unresolved",
                        suggestions=suggestions,
                    )
                )
    return findings


def normalize_links(
    vault: Path, note_path: str, fix: bool = False
) -> LinkNormalization:
    config = load_runtime_config(vault)
    path = resolve_path_in_vault(vault, note_path)
    rel = rel_to_vault(vault, path)
    text = path.read_text(encoding="utf-8")
    data, body = split_page_text(text, config=config)
    replacements: list[dict[str, Any]] = []
    spans = extract_internal_links(body, vault=vault, source_path=rel)
    updated_parts: list[str] = []
    cursor = 0
    for link in spans:
        updated_parts.append(body[cursor : link.start])
        canonical = resolve_best_wikilink(vault, link.query, source_path=rel)
        if canonical is None or canonical == link.raw:
            updated_parts.append(link.raw)
        else:
            replacements.append({"from": link.raw, "to": canonical})
            updated_parts.append(canonical if fix else link.raw)
        cursor = link.end
    updated_parts.append(body[cursor:])
    updated_body = "".join(updated_parts)
    changed = bool(replacements)
    if fix and changed:
        path.write_text(
            render_page_text(data, updated_body, config=config), encoding="utf-8"
        )
    return LinkNormalization(
        path=rel,
        changed=changed,
        replacements=tuple(replacements),
        applied=fix and changed,
    )


def render_link_matches_json(matches: list[LinkMatch]) -> list[dict[str, Any]]:
    return [asdict(match) for match in matches]


def render_link_findings_json(
    findings: list[LinkCheckFinding],
) -> list[dict[str, Any]]:
    return [asdict(finding) for finding in findings]


def render_link_normalization_json(result: LinkNormalization) -> dict[str, Any]:
    return asdict(result)


def _iter_link_entries(vault: Path) -> Iterator[dict[str, Any]]:
    config = load_runtime_config(vault)
    pages_prefix = f"{config.profile_config.pages_dir}/"
    for path in sorted(vault.rglob("*.md")):
        rel = rel_to_vault(vault, path)
        text = path.read_text(encoding="utf-8")
        if rel.startswith(pages_prefix):
            data, body = split_page_text(text, config=config)
        else:
            data, body = split_frontmatter(text)
        title = extract_title(data, body, path)
        aliases = (
            [str(value) for value in data.get("aliases", [])]
            if isinstance(data.get("aliases", []), list)
            else []
        )
        yield {
            "path": rel,
            "stem": path.stem,
            "title": title,
            "kind": _infer_kind(rel),
            "aliases": aliases,
        }
    catalog = vault / "Wiki/catalog.jsonl"
    if not catalog.exists():
        return
    for line in catalog.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        catalog_path = str(row.get("path", ""))
        if not catalog_path:
            continue
        aliases = (
            [str(value) for value in row.get("aliases", [])]
            if isinstance(row.get("aliases", []), list)
            else []
        )
        yield {
            "path": catalog_path,
            "stem": Path(catalog_path).stem,
            "title": str(row.get("title", "") or Path(catalog_path).stem),
            "kind": str(row.get("kind", _infer_kind(catalog_path))),
            "aliases": aliases,
        }


def _score_link_entry(entry: dict[str, Any], raw: str, lower: str) -> int:
    from rapidfuzz import fuzz as rf_fuzz

    rel = str(entry["path"])
    rel_no_ext = rel.removesuffix(".md")
    stem = str(entry["stem"])
    title = str(entry["title"])
    aliases = [str(alias) for alias in entry["aliases"]]
    candidates = {rel, rel_no_ext, stem}
    if raw in candidates:
        return 100
    if lower in {value.lower() for value in candidates}:
        return 98
    if raw == title:
        return 96
    if lower == title.lower():
        return 94
    if raw in aliases:
        return 94
    if lower in {alias.lower() for alias in aliases}:
        return 92
    if lower in title.lower():
        return 75
    if any(lower in alias.lower() for alias in aliases):
        return 70
    if lower in stem.lower() or lower in rel_no_ext.lower():
        return 65
    # RapidFuzz fuzzy fallback
    best = max(
        rf_fuzz.WRatio(lower, rel_no_ext.lower()),
        rf_fuzz.WRatio(lower, stem.lower()),
        rf_fuzz.WRatio(lower, title.lower()),
        max((rf_fuzz.WRatio(lower, alias.lower()) for alias in aliases), default=0.0),
    )
    if best >= 55:
        return int(best)
    return 0


def _link_resolves(link: str | ParsedLink, targets: set[str]) -> bool:
    return bool(link_candidate_keys(link) & targets)


def _vault_root_for(path: Path) -> Path:
    for candidate in (path.parent, *path.parents):
        if (candidate / "wikimason.toml").exists() or (candidate / "Wiki").exists():
            return candidate
    raise ValueError(f"could not infer vault root for {path}")


def _infer_kind(path: str) -> str:
    if path.startswith("Wiki/Topics/"):
        return "topic"
    if path.startswith("Wiki/Concepts/"):
        return "concept"
    if path.startswith("Wiki/Entities/"):
        return "entity"
    if path.startswith("Wiki/Projects/"):
        return "project"
    if path.startswith("Wiki/Logs/"):
        return "log"
    if path.startswith("Raw/Sources/"):
        return "source"
    return "note"
