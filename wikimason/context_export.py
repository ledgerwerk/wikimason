"""Context export engine for WikiMason.

Selects relevant wiki pages and sources for a topic query, merges and ranks
them, then renders into a deterministic Markdown context file.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from .search import SearchCandidate

from .config import load_runtime_config
from .lint_credentials import check_credentials
from .page_profiles import split_page_text
from .paths import rel_to_vault, source_md_files

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
    sha256_short: str = ""
    rank: int | None = None
    omitted_reason: str | None = None


@dataclass(frozen=True)
class QueryDiagnostics:
    original: str
    normalized: str
    removed_stopwords: tuple[str, ...] = ()
    fts_mode: str = "broad"
    used_stopword_fallback: bool = False


@dataclass(frozen=True)
class SourceClosureGap:
    source_path: str
    required_by: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class ContextPlan:
    query: str
    items: tuple[ContextItem, ...]
    total_candidates: int
    selected_count: int
    estimated_tokens: int
    omitted: tuple[ContextItem, ...] = ()
    source_closure_gaps: tuple[SourceClosureGap, ...] = ()
    query_diagnostics: QueryDiagnostics | None = None
    stats: dict[str, int] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def plan_context(  # noqa: C901
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
    purpose: str = "chat",
    source_closure: bool = True,
    show_omitted: int = 20,
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
    fts_query_plan = _merge_fts_seeds(vault, query, seed_items_map)
    query_diagnostics = _build_query_diagnostics(query, fts_query_plan=fts_query_plan)

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

    # 4. Sort by tier ascending, then score descending, then kind priority
    _kind_priority = {"page": 0, "source": 1, "file": 2}
    ranked = sorted(
        filtered.values(),
        key=lambda c: (c.tier, -c.score, _kind_priority.get(c.kind, 3), c.path),
    )

    # 5. Apply exclusions
    generated_paths: set[str] = set()
    if include_generated:
        from .schema import load_vault_schema, schema_generated_paths

        schema = load_vault_schema(vault)
        generated_paths = schema_generated_paths(schema)
    warnings: list[str] = []
    final_candidates: list[_Candidate] = []
    for cand in ranked:
        if _is_excluded(cand.path):
            if include_indexes and cand.path.startswith("Wiki/"):
                pass  # allow generated indexes
            elif include_generated and cand.path in generated_paths:
                pass  # allow schema-generated files
            else:
                continue
        if cand.score < min_score:
            continue
        final_candidates.append(cand)

    # 6. Apply budgets
    total_candidates = len(final_candidates)
    selected: list[ContextItem] = []
    omitted: list[ContextItem] = []
    running_bytes = 0
    running_tokens = 0

    for rank, cand in enumerate(final_candidates, start=1):
        if len(selected) >= max_files:
            warnings.append(
                f"max-files limit ({max_files}) reached; "
                f"{total_candidates - len(selected)} candidates omitted"
            )
            omitted.extend(
                _build_omitted_item(
                    cand=remaining,
                    rank=index,
                    omitted_reason="max-files",
                )
                for index, remaining in enumerate(
                    final_candidates[rank - 1 :], start=rank
                )
            )
            break

        file_path = vault / cand.path
        if not file_path.exists():
            omitted.append(
                _build_omitted_item(
                    cand=cand,
                    rank=rank,
                    omitted_reason="missing-file",
                )
            )
            continue

        try:
            text = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            if include_binary and cand.kind == "file":
                # Include as metadata-only item for binary files
                sha256 = ""
                try:
                    import hashlib as _hl

                    sha256 = _hl.sha256(file_path.read_bytes()).hexdigest()
                except OSError:
                    pass
                selected.append(
                    ContextItem(
                        path=cand.path,
                        kind=cand.kind,
                        score=cand.score,
                        reasons=tuple(cand.reasons),
                        include="metadata",
                        estimated_tokens=1,
                        sha256=sha256,
                        sha256_short=sha256[:12] if sha256 else "",
                        rank=len(selected) + 1,
                    )
                )
                running_tokens += 1
                continue
            omitted.append(
                _build_omitted_item(
                    cand=cand,
                    rank=rank,
                    omitted_reason="unreadable",
                )
            )
            continue

        tokens = _estimate_tokens(text)
        size = len(text.encode("utf-8"))
        sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
        sha256_short = sha256[:12]

        if running_tokens + tokens > max_tokens:
            # Try summary mode instead
            summary = _extract_summary(vault, cand.path)
            if summary:
                summary_tokens = _estimate_tokens(summary)
                summary_size = len(summary.encode("utf-8"))
                if (
                    running_tokens + summary_tokens <= max_tokens
                    and running_bytes + summary_size <= max_bytes
                ):
                    running_tokens += summary_tokens
                    running_bytes += summary_size
                    selected.append(
                        ContextItem(
                            path=cand.path,
                            kind=cand.kind,
                            score=cand.score,
                            reasons=tuple(cand.reasons),
                            include="summary",
                            estimated_tokens=summary_tokens,
                            sha256=sha256,
                            sha256_short=sha256_short,
                            rank=len(selected) + 1,
                        )
                    )
                    warnings.append(f"{cand.path} truncated to summary (token budget)")
                    continue
            omitted.append(
                _build_omitted_item(
                    cand=cand,
                    rank=rank,
                    omitted_reason="max-tokens",
                )
            )
            continue

        if running_bytes + size > max_bytes:
            summary = _extract_summary(vault, cand.path)
            if summary:
                summary_tokens = _estimate_tokens(summary)
                summary_size = len(summary.encode("utf-8"))
                if (
                    running_tokens + summary_tokens <= max_tokens
                    and running_bytes + summary_size <= max_bytes
                ):
                    running_tokens += summary_tokens
                    running_bytes += summary_size
                    selected.append(
                        ContextItem(
                            path=cand.path,
                            kind=cand.kind,
                            score=cand.score,
                            reasons=tuple(cand.reasons),
                            include="summary",
                            estimated_tokens=summary_tokens,
                            sha256=sha256,
                            sha256_short=sha256_short,
                            rank=len(selected) + 1,
                        )
                    )
                    warnings.append(f"{cand.path} truncated to summary (byte budget)")
                    continue
            omitted.append(
                _build_omitted_item(
                    cand=cand,
                    rank=rank,
                    omitted_reason="max-bytes",
                )
            )
            continue

        running_bytes += size
        running_tokens += tokens
        selected.append(
            ContextItem(
                path=cand.path,
                kind=cand.kind,
                score=cand.score,
                reasons=tuple(cand.reasons),
                include="full",
                estimated_tokens=tokens,
                sha256=sha256,
                sha256_short=sha256_short,
                rank=len(selected) + 1,
            )
        )

    # 7. Source-closure analysis
    if source_closure:
        source_closure_gaps = _check_source_closure(vault, selected, omitted)
    else:
        source_closure_gaps = ()

    total_tokens = sum(item.estimated_tokens for item in selected)
    stats = _build_plan_stats(
        selected=selected,
        omitted=omitted,
        warnings=warnings,
        total_candidates=total_candidates,
    )

    return ContextPlan(
        query=query,
        items=tuple(selected),
        total_candidates=total_candidates,
        selected_count=len(selected),
        estimated_tokens=total_tokens,
        omitted=tuple(omitted),
        source_closure_gaps=source_closure_gaps,
        query_diagnostics=query_diagnostics,
        stats=stats,
        warnings=tuple(warnings),
    )


def render_context_markdown(
    vault: Path,
    plan: ContextPlan,
    *,
    show_omitted: int = 20,
) -> str:
    """Render a :class:`ContextPlan` into a deterministic Markdown string."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines: list[str] = []

    # YAML frontmatter
    lines.append("---")
    lines.append("wikimason_context_export: 1")
    lines.append(f'query: "{plan.query}"')
    if plan.query_diagnostics is not None:
        lines.append(f'query_normalized: "{plan.query_diagnostics.normalized}"')
        lines.append(f'query_fts_mode: "{plan.query_diagnostics.fts_mode}"')
    lines.append(f'generated_at: "{now}"')
    lines.append(f"selected_count: {plan.selected_count}")
    lines.append(f"omitted_count: {len(plan.omitted)}")
    lines.append(f"estimated_tokens: {plan.estimated_tokens}")
    lines.append("---")
    lines.append("")

    # Title
    lines.append(f"# WikiMason Context Export: {plan.query}")
    lines.append("")

    lines.append("## Export Summary")
    lines.append("")
    lines.append(f"- Selected files: {plan.selected_count}")
    lines.append(f"- Omitted candidates: {len(plan.omitted)}")
    lines.append(f"- Estimated tokens: {plan.estimated_tokens}")
    if plan.query_diagnostics is not None:
        lines.append(f"- Query normalized: `{plan.query_diagnostics.normalized}`")
        lines.append(f"- FTS mode: `{plan.query_diagnostics.fts_mode}`")
        if plan.query_diagnostics.removed_stopwords:
            lines.append(
                "- Removed stopwords: "
                + ", ".join(
                    f"`{term}`" for term in plan.query_diagnostics.removed_stopwords
                )
            )
    lines.append("")

    # Selection manifest table
    lines.append("## Selection Manifest")
    lines.append("")
    lines.append("| Rank | Score | Kind | Include | SHA256 | Path | Reason |")
    lines.append("| ---: | ----: | ---- | ------- | ------ | ---- | ------ |")
    for i, item in enumerate(plan.items, start=1):
        reason_str = ", ".join(item.reasons)
        lines.append(
            f"| {i} | {item.score:.1f} | {item.kind} | {item.include} | "
            f"{item.sha256_short or item.sha256[:12]} | {item.path} | {reason_str} |"
        )
    lines.append("")

    if plan.warnings:
        lines.append("## Warnings")
        lines.append("")
        for w in plan.warnings:
            lines.append(f"- {w}")
        lines.append("")

    if plan.omitted:
        lines.append("## Omitted Candidates")
        lines.append("")
        lines.append("| Rank | Score | Kind | Path | Omitted reason |")
        lines.append("| ---: | ----: | ---- | ---- | -------------- |")
        for item in plan.omitted[:show_omitted]:
            lines.append(
                f"| {item.rank or '-'} | {item.score:.1f} | {item.kind} | "
                f"{item.path} | {item.omitted_reason or ''} |"
                f"{item.omitted_reason or ''} |"
            )
        lines.append("")

    if plan.source_closure_gaps:
        lines.append("## Source Closure Gaps")
        lines.append("")
        lines.append("| Source | Required by | Reason |")
        lines.append("| ------ | ----------- | ------ |")
        for gap in plan.source_closure_gaps:
            required = ", ".join(gap.required_by)
            lines.append(f"| {gap.source_path} | {required} | {gap.reason} |")
        lines.append("")
    # File contents
    for i, item in enumerate(plan.items, start=1):
        lines.append(f"## File {i}: {item.path}")
        lines.append("")
        lines.append(
            f'<!-- wikimason:begin-file path="{item.path}" kind="{item.kind}" '
            f'<!-- wikimason:begin-file path="{item.path}" kind="{item.kind}" '
            f'sha256="{item.sha256_short or item.sha256[:12]}" '
            f'score="{item.score:.1f}" -->'
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

        if item.include == "metadata":
            content = (
                f"(binary/metadata-only: {item.path}, "
                f"sha256={item.sha256_short or item.sha256[:12]})"
            )
        elif item.include == "summary":
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
            f"Context export contains {len(cred_findings)} "
            f"potential credential leak(s). "
            "Use --allow-sensitive to proceed."
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(md, encoding="utf-8")
    return plan


def plan_to_json(plan: ContextPlan) -> dict[str, Any]:
    """Convert a :class:`ContextPlan` to a JSON-serializable dict."""
    omitted_top = list(plan.omitted[:20])
    return {
        "query": plan.query,
        "total_candidates": plan.total_candidates,
        "selected_count": plan.selected_count,
        "omitted_count": len(plan.omitted),
        "estimated_tokens": plan.estimated_tokens,
        "items": [
            {
                "path": item.path,
                "kind": item.kind,
                "score": item.score,
                "reasons": list(item.reasons),
                "include": item.include,
                "estimated_tokens": item.estimated_tokens,
                "sha256": item.sha256,
                "sha256_short": item.sha256_short or item.sha256[:12],
                "rank": item.rank,
            }
            for item in plan.items
        ],
        "omitted_top": [
            {
                "path": item.path,
                "kind": item.kind,
                "score": item.score,
                "reasons": list(item.reasons),
                "rank": item.rank,
                "omitted_reason": item.omitted_reason,
            }
            for item in omitted_top
        ],
        "omitted": [
            {
                "path": item.path,
                "kind": item.kind,
                "score": item.score,
                "reasons": list(item.reasons),
                "rank": item.rank,
                "omitted_reason": item.omitted_reason,
            }
            for item in plan.omitted
        ],
        "query_diagnostics": (
            {
                "original": plan.query_diagnostics.original,
                "normalized": plan.query_diagnostics.normalized,
                "removed_stopwords": list(plan.query_diagnostics.removed_stopwords),
                "fts_mode": plan.query_diagnostics.fts_mode,
                "used_stopword_fallback": plan.query_diagnostics.used_stopword_fallback,
            }
            if plan.query_diagnostics is not None
            else None
        ),
        "source_closure_gaps": [
            {
                "source_path": gap.source_path,
                "required_by": list(gap.required_by),
                "reason": gap.reason,
            }
            for gap in plan.source_closure_gaps
        ],
        "stats": dict(plan.stats),
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
    tier: int = 0  # 0=seed, 1=declared-source, 2=graph-expansion

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


def _score_catalog_candidate(
    cand: SearchCandidate,
    norm: str,
    fuzz: Any,
) -> tuple[float, list[str]]:
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

    return score, reasons


def _merge_catalog_seeds(vault: Path, query: str, acc: dict[str, _Candidate]) -> None:
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
        score, reasons = _score_catalog_candidate(cand, norm, fuzz)

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


def _merge_source_seeds(vault: Path, query: str, acc: dict[str, _Candidate]) -> None:
    from rapidfuzz import fuzz

    from .search import normalize_query

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


def _merge_filename_seeds(vault: Path, query: str, acc: dict[str, _Candidate]) -> None:
    from rapidfuzz import fuzz

    from .search import normalize_query

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
    vault: Path,
    query: str,
    acc: dict[str, _Candidate],
) -> object | None:
    """Merge FTS5 search results into candidates."""
    from .search_index import (
        CONTEXT_EXPORT_STOPWORDS,
        DEFAULT_INDEX_PATH,
        SQLiteSearchIndex,
        build_fts_query_plan,
    )

    db_path = vault / DEFAULT_INDEX_PATH
    if not db_path.exists():
        return None

    idx = SQLiteSearchIndex(db_path)
    chosen_plan = None
    results: list[dict[str, object]] = []
    try:
        for mode in ("strict", "balanced", "broad"):
            query_plan = build_fts_query_plan(
                query,
                mode=mode,
                stopwords=CONTEXT_EXPORT_STOPWORDS,
            )
            if not query_plan.query:
                continue
            weight_profile = "context" if mode != "broad" else "broad"
            results = idx.query_prepared(
                query_plan.query,
                limit=50,
                weight_profile=weight_profile,
            )
            chosen_plan = query_plan
            if results:
                break
    except Exception:
        return None
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

    return chosen_plan


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
                        tier=2,
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
                        tier=2,
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
                            normalized = _normalize_declared_source(vault, src_str)
                            if normalized is None:
                                # Invalid path: skip silently; closure gap
                                # will be reported by _check_source_closure.
                                continue
                            if normalized not in acc and normalized not in visited:
                                acc[normalized] = _Candidate(
                                    path=normalized,
                                    kind="source",
                                    score=WEIGHTS["declared_source"],
                                    reasons=[f"declared-source-of:{cand.path}"],
                                    tier=1,
                                )
                                new_paths.append(normalized)
                            elif normalized in acc:
                                acc[normalized].add_reason(
                                    f"declared-source-of:{cand.path}"
                                )
                except Exception:
                    pass
                    pass

        visited.update(new_paths)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _check_source_closure(
    vault: Path,
    selected: list[ContextItem],
    omitted: list[ContextItem],
    warnings: list[str] | None = None,
) -> tuple[SourceClosureGap, ...]:
    """Check declared sources of selected pages and report closure gaps."""
    config = load_runtime_config(vault)
    selected_paths = {item.path for item in selected}
    omitted_paths = {item.path for item in omitted}
    gaps: list[SourceClosureGap] = []

    for item in selected:
        if item.kind != "page":
            continue
        file_path = vault / item.path
        if not file_path.exists():
            continue
        try:
            text = file_path.read_text(encoding="utf-8")
            data, _ = split_page_text(text, config=config)
        except Exception:
            continue
        sources = data.get("sources", [])
        if not isinstance(sources, list):
            continue
        for src in sources:
            src_str = str(src).strip()
            # Normalize the source path
            normalized = _normalize_declared_source(vault, src_str)
            if normalized is None:
                gaps.append(
                    SourceClosureGap(
                        source_path=src_str,
                        required_by=(item.path,),
                        reason="invalid-path",
                    )
                )
                continue
            if normalized in selected_paths:
                continue
            if normalized in omitted_paths:
                omitted_item = next(o for o in omitted if o.path == normalized)
                gaps.append(
                    SourceClosureGap(
                        source_path=normalized,
                        required_by=(item.path,),
                        reason=(
                            "budget-excluded:"
                            f"{omitted_item.omitted_reason or 'unknown'}"
                        ),
                    )
                )
            else:
                gaps.append(
                    SourceClosureGap(
                        source_path=normalized,
                        required_by=(item.path,),
                        reason="not-in-candidates",
                    )
                )

    return tuple(gaps)


def _normalize_declared_source(vault: Path, src_path: str) -> str | None:
    """Normalize and validate a declared source path. Returns None if invalid."""
    if not src_path:
        return None
    # Strip leading slashes
    cleaned = src_path.lstrip("/")
    # Reject paths with upward traversal
    if ".." in cleaned.split("/"):
        return None
    # Must be a relative path within the vault
    resolved = (vault / cleaned).resolve()
    try:
        resolved.relative_to(vault.resolve())
    except ValueError:
        return None
    return cleaned


def _build_query_diagnostics(
    query: str,
    *,
    fts_query_plan: object | None = None,
) -> QueryDiagnostics:
    cleaned = re.sub(r"\s+", " ", query).strip()
    if fts_query_plan is None:
        return QueryDiagnostics(original=query, normalized=cleaned or query.strip())

    normalized = " ".join(
        getattr(fts_query_plan, "effective_terms", ())
        or getattr(fts_query_plan, "terms", ())
    )
    return QueryDiagnostics(
        original=query,
        normalized=normalized or cleaned or query.strip(),
        removed_stopwords=tuple(getattr(fts_query_plan, "removed_stopwords", ()) or ()),
        fts_mode=str(getattr(fts_query_plan, "mode", "broad")),
        used_stopword_fallback=bool(
            getattr(fts_query_plan, "used_stopword_fallback", False)
        ),
    )


def _build_omitted_item(
    *,
    cand: _Candidate,
    rank: int,
    omitted_reason: str,
) -> ContextItem:
    return ContextItem(
        path=cand.path,
        kind=cand.kind,
        score=cand.score,
        reasons=tuple(cand.reasons),
        rank=rank,
        omitted_reason=omitted_reason,
    )


def _build_plan_stats(
    *,
    selected: list[ContextItem],
    omitted: list[ContextItem],
    warnings: list[str],
    total_candidates: int,
) -> dict[str, int]:
    stats = {
        "total_candidates": total_candidates,
        "selected_count": len(selected),
        "omitted_count": len(omitted),
        "warning_count": len(warnings),
        "selected_full": sum(1 for item in selected if item.include == "full"),
        "selected_summary": sum(1 for item in selected if item.include == "summary"),
        "selected_metadata": sum(1 for item in selected if item.include == "metadata"),
        "selected_pages": sum(1 for item in selected if item.kind == "page"),
        "selected_sources": sum(1 for item in selected if item.kind == "source"),
        "selected_files": sum(1 for item in selected if item.kind == "file"),
    }
    return stats


def _extract_summary(vault: Path, rel: str) -> str | None:
    """Extract a summary for a file: frontmatter summary, first heading,
    first paragraph."""
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
