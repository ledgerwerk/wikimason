"""Context export engine for WikiMason.

Selects relevant wiki pages and sources for a topic query, merges and ranks
them, then renders into a deterministic Markdown context file.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from .config import load_runtime_config
from .lint_credentials import check_credentials
from .page_profiles import split_page_text
from .paths import compiled_md_files, rel_to_vault, source_md_files

# ---------------------------------------------------------------------------
# Scoring weights
# ---------------------------------------------------------------------------

WEIGHTS: dict[str, float] = {
    "title_exact": 100,
    "title_fuzzy": 80,
    "path_fuzzy": 70,
    "alias": 75,
    "tag": 85,
    "topic": 85,
    "summary_fts": 65,
    "heading_fts": 70,
    "body_fts": 55,
    "source_filename": 75,
    "declared_source": 95,
    "outlink_depth_1": 35,
    "backlink_depth_1": 25,
}

# ---------------------------------------------------------------------------
# Exclusion patterns
# ---------------------------------------------------------------------------

_EXCLUDED_PREFIXES: tuple[str, ...] = (
    ".git/",
    ".wikimason/",
    ".obsidian/",
    "Wiki/catalog.jsonl",
    "Wiki/index.md",
)

_EXCLUDED_SUFFIXES: tuple[str, ...] = (
    "/index.md",
    "___index.md",
)


def _is_excluded(rel: str) -> bool:
    for prefix in _EXCLUDED_PREFIXES:
        if rel.startswith(prefix):
            return True
    if rel == "Wiki/index.md":
        return True
    for suffix in _EXCLUDED_SUFFIXES:
        if rel.endswith(suffix):
            return True
    return False


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ContextItem:
    path: str
    kind: Literal["page", "source", "file"]
    score: float
    reasons: tuple[str, ...]
    include: Literal["full", "summary", "metadata"] = "full"
    estimated_tokens: int = 0
    sha256: str = ""


@dataclass(frozen=True)
class ContextPlan:
    query: str
    items: tuple[ContextItem, ...]
    total_candidates: int
    selected_count: int
    estimated_tokens: int
    warnings: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def plan_context(
    vault: Path,
    query: str,
    *,
    max_files: int = 30,
    max_bytes: int = 250_000,
    max_tokens: int = 60_000,
    depth: int = 1,
    include: str = "both",
    rebuild_index: bool = False,
    min_score: float = 0.0,
    include_indexes: bool = False,
    include_generated: bool = False,
    include_binary: bool = False,
) -> ContextPlan:
    """Select relevant files for *query* and return a :class:`ContextPlan`."""
    # Optionally rebuild FTS index
    if rebuild_index:
        from .search_index import open_search_index

        idx = open_search_index(vault)
        idx.rebuild(vault)
        idx.close()

    # 1. Gather seed candidates from all backends
    seed_items_map: dict[str, _Candidate] = {}

    _merge_catalog_seeds(vault, query, seed_items_map)
    _merge_source_seeds(vault, query, seed_items_map)
    _merge_filename_seeds(vault, query, seed_items_map)
    _merge_fts_seeds(vault, query, seed_items_map)

    # 2. Apply include filter
    filtered: dict[str, _Candidate] = {}
    for path, cand in seed_items_map.items():
        if include == "wiki" and cand.kind == "source":
            continue
        if include == "sources" and cand.kind == "page":
            continue
        filtered[path] = cand

    # 3. Graph expansion
    if depth >= 1:
        _expand_graph(vault, filtered, seed_items_map, depth=depth)

    # 4. Sort by score descending
    ranked = sorted(filtered.values(), key=lambda c: (-c.score, c.path))

    # 5. Apply exclusions
    warnings: list[str] = []
    final_candidates: list[_Candidate] = []
    for cand in ranked:
        if _is_excluded(cand.path):
            if include_indexes and cand.path.startswith("Wiki/"):
                pass  # allow generated indexes
            else:
                continue
        if cand.score < min_score:
            continue
        final_candidates.append(cand)

    # 6. Apply budgets
    total_candidates = len(final_candidates)
    selected: list[ContextItem] = []
    running_bytes = 0
    running_tokens = 0

    for cand in final_candidates:
        if len(selected) >= max_files:
            warnings.append(f"max-files limit ({max_files}) reached; {total_candidates - len(selected)} candidates omitted")
            break

        file_path = vault / cand.path
        if not file_path.exists():
            continue

        try:
            text = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        tokens = _estimate_tokens(text)
        size = len(text.encode("utf-8"))

        if running_tokens + tokens > max_tokens:
            # Try summary mode instead
            summary = _extract_summary(vault, cand.path)
            if summary:
                selected.append(ContextItem(
                    path=cand.path,
                    kind=cand.kind,
                    score=cand.score,
                    reasons=cand.reasons,
                    include="summary",
                    estimated_tokens=_estimate_tokens(summary),
                    sha256=hashlib.sha256(text.encode("utf-8")).hexdigest()[:12],
                ))
                warnings.append(f"{cand.path} truncated to summary (token budget)")
            continue

        if running_bytes + size > max_bytes:
            summary = _extract_summary(vault, cand.path)
            if summary:
                selected.append(ContextItem(
                    path=cand.path,
                    kind=cand.kind,
                    score=cand.score,
                    reasons=cand.reasons,
                    include="summary",
                    estimated_tokens=_estimate_tokens(summary),
                    sha256=hashlib.sha256(text.encode("utf-8")).hexdigest()[:12],
                ))
                warnings.append(f"{cand.path} truncated to summary (byte budget)")
            continue

        running_bytes += size
        running_tokens += tokens
        selected.append(ContextItem(
            path=cand.path,
            kind=cand.kind,
            score=cand.score,
            reasons=cand.reasons,
            include="full",
            estimated_tokens=tokens,
            sha256=hashlib.sha256(text.encode("utf-8")).hexdigest()[:12],
        ))

    total_tokens = sum(item.estimated_tokens for item in selected)

    return ContextPlan(
        query=query,
        items=tuple(selected),
        total_candidates=total_candidates,
        selected_count=len(selected),
        estimated_tokens=total_tokens,
        warnings=tuple(warnings),
    )


def render_context_markdown(vault: Path, plan: ContextPlan) -> str:
    """Render a :class:`ContextPlan` into a deterministic Markdown string."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines: list[str] = []

    # YAML frontmatter
    lines.append("---")
    lines.append(f"wikimason_context_export: 1")
    lines.append(f'query: "{plan.query}"')
    lines.append(f'generated_at: "{now}"')
    lines.append(f"selected_count: {plan.selected_count}")
    lines.append(f"estimated_tokens: {plan.estimated_tokens}")
    lines.append("---")
    lines.append("")

    # Title
    lines.append(f"# WikiMason Context Export: {plan.query}")
    lines.append("")

    # Selection manifest table
    lines.append("## Selection Manifest")
    lines.append("")
    lines.append("| Rank | Score | Kind | Path | Reason |")
    lines.append("| ---: | ----: | ---- | ---- | ------ |")
    for i, item in enumerate(plan.items, start=1):
        reason_str = ", ".join(item.reasons)
        lines.append(f"| {i} | {item.score:.1f} | {item.kind} | {item.path} | {reason_str} |")
    lines.append("")

    if plan.warnings:
        lines.append("## Warnings")
        lines.append("")
        for w in plan.warnings:
            lines.append(f"- {w}")
        lines.append("")

    # File contents
    for i, item in enumerate(plan.items, start=1):
        lines.append(f"## File {i}: {item.path}")
        lines.append("")
        lines.append(
            f'<!-- wikimason:begin-file path="{item.path}" kind="{item.kind}" '
            f'sha256="{item.sha256}" score="{item.score:.1f}" -->'
        )
        lines.append("")

        file_path = vault / item.path
        if file_path.exists():
            try:
                content = file_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                content = f"(could not read {item.path})"
        else:
            content = f"(file not found: {item.path})"

        if item.include == "summary":
            summary = _extract_summary(vault, item.path)
            content = summary or content

        lines.append(content)
        if not content.endswith("\n"):
            lines.append("")
        lines.append("<!-- wikimason:end-file -->")
        lines.append("")

    return "\n".join(lines)


def export_context(
    vault: Path,
    query: str,
    output: Path,
    *,
    allow_sensitive: bool = False,
    **options: Any,
) -> ContextPlan:
    """Plan, render, and write context export in one step."""
    plan = plan_context(vault, query, **options)

    # Credential safety check
    md = render_context_markdown(vault, plan)
    cred_findings: list[Any] = []
    check_credentials(md, "<export>", cred_findings)
    if cred_findings and not allow_sensitive:
        raise ValueError(
            f"Context export contains {len(cred_findings)} potential credential leak(s). "
            "Use --allow-sensitive to proceed."
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(md, encoding="utf-8")
    return plan


def plan_to_json(plan: ContextPlan) -> dict[str, Any]:
    """Convert a :class:`ContextPlan` to a JSON-serializable dict."""
    return {
        "query": plan.query,
        "total_candidates": plan.total_candidates,
        "selected_count": plan.selected_count,
        "estimated_tokens": plan.estimated_tokens,
        "items": [
            {
                "path": item.path,
                "kind": item.kind,
                "score": item.score,
                "reasons": list(item.reasons),
                "include": item.include,
                "estimated_tokens": item.estimated_tokens,
            }
            for item in plan.items
        ],
        "warnings": list(plan.warnings),
    }


# ---------------------------------------------------------------------------
# Internal candidate accumulator
# ---------------------------------------------------------------------------


@dataclass
class _Candidate:
    path: str
    kind: str
    score: float
    reasons: list[str] = field(default_factory=list)

    def add_reason(self, reason: str) -> None:
        if reason not in self.reasons:
            self.reasons.append(reason)

    def update_score(self, score: float, reason: str) -> None:
        if score > self.score:
            self.score = score
        self.add_reason(reason)


# ---------------------------------------------------------------------------
# Seed candidate generators
# ---------------------------------------------------------------------------


def _merge_catalog_seeds(
    vault: Path, query: str, acc: dict[str, _Candidate]
) -> None:
    from .search import normalize_query
    from .search_backends import CatalogBackend

    norm = normalize_query(query)
    backend = CatalogBackend(vault)
    candidates = backend.candidates(query, limit=500)
    if not candidates:
        return

    from rapidfuzz import fuzz

    for cand in candidates:
        if not cand.path:
            continue
        path = cand.path
        score = 0.0
        reasons: list[str] = []

        # Title scoring
        title_norm = cand.label.casefold()
        if title_norm == norm:
            score = WEIGHTS["title_exact"]
            reasons.append("title:exact")
        elif norm in title_norm:
            score = WEIGHTS["title_fuzzy"]
            reasons.append("title:contains")
        else:
            ratio = fuzz.WRatio(norm, title_norm)
            if ratio >= 70:
                score = max(score, WEIGHTS["title_fuzzy"] * ratio / 100)
                reasons.append("title:fuzzy")

        # Path scoring
        if cand.path:
            path_norm = cand.path.casefold()
            path_ratio = fuzz.WRatio(norm, path_norm)
            if path_ratio >= 65:
                score = max(score, WEIGHTS["path_fuzzy"] * path_ratio / 100)
                if "path:fuzzy" not in reasons:
                    reasons.append("path:fuzzy")

        # Alias scoring
        for alias in cand.aliases:
            alias_norm = alias.casefold()
            if norm == alias_norm:
                score = max(score, WEIGHTS["alias"])
                reasons.append("alias:exact")
            else:
                ratio = fuzz.WRatio(norm, alias_norm)
                if ratio >= 70:
                    score = max(score, WEIGHTS["alias"] * ratio / 100)
                    reasons.append("alias:fuzzy")

        # Tag scoring
        tags_str = cand.fields.get("tags", "")
        if tags_str:
            tags = tags_str.lower().split()
            for tag in tags:
                if norm == tag:
                    score = max(score, WEIGHTS["tag"])
                    reasons.append("tag:exact")
                elif norm in tag:
                    score = max(score, WEIGHTS["tag"] * 0.9)
                    reasons.append("tag:partial")

        # Topic scoring
        topics_str = cand.fields.get("topics", "")
        if topics_str:
            topics = topics_str.lower().split()
            for topic in topics:
                if norm == topic:
                    score = max(score, WEIGHTS["topic"])
                    reasons.append("topic:exact")

        # Summary scoring
        summary = cand.fields.get("summary", "")
        if summary and norm in summary.casefold():
            score = max(score, WEIGHTS["summary_fts"])
            reasons.append("summary:match")

        if score > 0:
            if path in acc:
                acc[path].update_score(score, "seed")
                for r in reasons:
                    acc[path].add_reason(r)
            else:
                acc[path] = _Candidate(
                    path=path,
                    kind=cand.kind,
                    score=score,
                    reasons=["seed"] + reasons,
                )


def _merge_source_seeds(
    vault: Path, query: str, acc: dict[str, _Candidate]
) -> None:
    from .search import normalize_query
    from rapidfuzz import fuzz

    norm = normalize_query(query)
    for path in source_md_files(vault):
        rel = rel_to_vault(vault, path)
        stem_norm = path.stem.casefold()
        ratio = fuzz.WRatio(norm, stem_norm)
        if ratio >= 65:
            score = WEIGHTS["source_filename"] * ratio / 100
            if rel in acc:
                acc[rel].update_score(score, "source:fuzzy")
            else:
                acc[rel] = _Candidate(
                    path=rel,
                    kind="source",
                    score=score,
                    reasons=["seed", "source:fuzzy"],
                )


def _merge_filename_seeds(
    vault: Path, query: str, acc: dict[str, _Candidate]
) -> None:
    from .search import normalize_query
    from rapidfuzz import fuzz

    norm = normalize_query(query)
    for path in vault.rglob("*.md"):
        rel = rel_to_vault(vault, path)
        if _is_excluded(rel):
            continue
        stem_norm = path.stem.casefold()
        ratio = fuzz.WRatio(norm, stem_norm)
        if ratio >= 70:
            kind = _infer_kind_from_path(rel)
            score = WEIGHTS["path_fuzzy"] * ratio / 100
            if rel in acc:
                acc[rel].update_score(score, "filename:fuzzy")
            else:
                acc[rel] = _Candidate(
                    path=rel,
                    kind=kind,
                    score=score,
                    reasons=["seed", "filename:fuzzy"],
                )


def _merge_fts_seeds(
    vault: Path, query: str, acc: dict[str, _Candidate]
) -> None:
    """Merge FTS5 search results into candidates."""
    from .search_index import DEFAULT_INDEX_PATH

    db_path = vault / DEFAULT_INDEX_PATH
    if not db_path.exists():
        return
    from .search_index import SQLiteSearchIndex

    idx = SQLiteSearchIndex(db_path)
    try:
        results = idx.query(query, limit=50)
    except Exception:
        return
    finally:
        idx.close()

    for result in results:
        path = str(result["path"])
        score = float(result.get("score", 0))
        reason = str(result.get("reason", "body:fts"))
        if score <= 0:
            continue
        kind = str(result.get("kind", "page"))
        if path in acc:
            acc[path].update_score(score, reason)
        else:
            acc[path] = _Candidate(
                path=path,
                kind=kind,
                score=score,
                reasons=["seed", reason],
            )


# ---------------------------------------------------------------------------
# Graph expansion
# ---------------------------------------------------------------------------


def _expand_graph(
    vault: Path,
    acc: dict[str, _Candidate],
    seed_map: dict[str, _Candidate],
    *,
    depth: int = 1,
) -> None:
    """Expand from top candidates through links, backlinks, and sources."""
    from .links import backlinks, outgoing_links

    config = load_runtime_config(vault)
    # Collect paths of top-scoring candidates for expansion
    top_paths = sorted(acc.values(), key=lambda c: -c.score)[:10]
    visited = set(acc.keys())

    for _round in range(depth):
        new_paths: list[str] = []
        for cand in list(acc.values()):
            if cand.path in visited and cand.score < WEIGHTS["outlink_depth_1"]:
                continue
            full_path = vault / cand.path
            if not full_path.exists():
                continue

            # Outgoing links
            try:
                out = outgoing_links(full_path)
            except Exception:
                out = []
            for linked in out:
                if linked not in acc and linked not in visited:
                    score = WEIGHTS["outlink_depth_1"]
                    acc[linked] = _Candidate(
                        path=linked,
                        kind=_infer_kind_from_path(linked),
                        score=score,
                        reasons=[f"outlink:{cand.path}"],
                    )
                    new_paths.append(linked)

            # Backlinks
            try:
                backs = backlinks(vault, cand.path)
            except Exception:
                backs = []
            for back in backs:
                if back not in acc and back not in visited:
                    score = WEIGHTS["backlink_depth_1"]
                    acc[back] = _Candidate(
                        path=back,
                        kind=_infer_kind_from_path(back),
                        score=score,
                        reasons=[f"backlink:{cand.path}"],
                    )
                    new_paths.append(back)

            # Declared sources from frontmatter
            if cand.kind == "page":
                try:
                    text = full_path.read_text(encoding="utf-8")
                    data, _ = split_page_text(text, config=config)
                    sources = data.get("sources", [])
                    if isinstance(sources, list):
                        for src in sources:
                            src_str = str(src).strip()
                            if src_str not in acc and src_str not in visited:
                                acc[src_str] = _Candidate(
                                    path=src_str,
                                    kind="source",
                                    score=WEIGHTS["declared_source"],
                                    reasons=[f"declared-source-of:{cand.path}"],
                                )
                                new_paths.append(src_str)
                except Exception:
                    pass

        visited.update(new_paths)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _extract_summary(vault: Path, rel: str) -> str | None:
    """Extract a summary for a file: frontmatter summary, first heading, first paragraph."""
    path = vault / rel
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    config = load_runtime_config(vault)
    data, body = split_page_text(text, config=config)

    # Check frontmatter summary
    summary = str(data.get("summary", "")).strip()
    if summary:
        return f"# {data.get('title', rel)}\n\n{summary}"

    # Check title + first paragraph
    lines = body.splitlines()
    title_line = ""
    first_para = ""
    for line in lines:
        stripped = line.strip()
        if not title_line and stripped.startswith("# "):
            title_line = stripped
            continue
        if not stripped:
            continue
        if not first_para:
            first_para = stripped
            break

    if title_line and first_para:
        return f"{title_line}\n\n{first_para}"
    if first_para:
        return first_para
    return None


def _infer_kind_from_path(rel: str) -> str:
    if rel.startswith("Wiki/"):
        return "page"
    if rel.startswith("Raw/Sources/"):
        return "source"
    return "file"
