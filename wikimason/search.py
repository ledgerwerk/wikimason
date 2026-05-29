from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

from fuzzysearch import find_near_matches
from rapidfuzz import fuzz, process, utils

SearchKind = Literal[
    "command",
    "page",
    "source",
    "file",
    "heading",
    "tag",
    "alias",
    "body",
]


@dataclass(frozen=True)
class SearchCandidate:
    key: str
    kind: SearchKind
    label: str
    path: str | None = None
    aliases: tuple[str, ...] = ()
    fields: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchResult:
    candidate: SearchCandidate
    score: float
    reason: str
    matched_field: str
    snippet: str | None = None
    spans: tuple[tuple[int, int], ...] = ()


class SearchBackend(Protocol):
    def candidates(self, query: str, *, limit: int = 200) -> list[SearchCandidate]: ...


# ---------------------------------------------------------------------------
# Query normalization
# ---------------------------------------------------------------------------

_PUNCT_RE = re.compile(r"[^\w/.-]+")


def normalize_query(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    value = value.replace("\\", "/").casefold()
    value = _PUNCT_RE.sub(" ", value)
    return " ".join(value.split())


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


def rank_candidates(
    query: str,
    candidates: list[SearchCandidate],
    *,
    limit: int = 20,
    cutoff: float = 55.0,
) -> list[SearchResult]:
    choices: dict[str, str] = {}
    by_key: dict[str, SearchCandidate] = {}

    for candidate in candidates:
        texts = [
            candidate.label,
            candidate.path or "",
            *candidate.aliases,
            *candidate.fields.values(),
        ]
        indexed_text = " | ".join(t for t in texts if t)
        choices[candidate.key] = indexed_text
        by_key[candidate.key] = candidate

    matches = process.extract(
        query,
        choices,
        scorer=fuzz.WRatio,
        processor=utils.default_process,
        limit=limit,
        score_cutoff=cutoff,
    )

    results: list[SearchResult] = []
    for _value, score, key in matches:
        candidate = by_key[key]
        results.append(
            SearchResult(
                candidate=candidate,
                score=float(score),
                reason="rapidfuzz:WRatio",
                matched_field="combined",
            )
        )
    return results


# ---------------------------------------------------------------------------
# Approximate snippets
# ---------------------------------------------------------------------------


def approximate_snippets(
    query: str, text: str, *, limit: int = 3
) -> list[tuple[int, int, int, str]]:
    max_dist = 1 if len(query) < 8 else 2
    matches = find_near_matches(query, text, max_l_dist=max_dist)
    rows: list[tuple[int, int, int, str]] = []
    for match in matches[:limit]:
        start = max(0, match.start - 80)
        end = min(len(text), match.end + 80)
        rows.append((match.start, match.end, match.dist, text[start:end]))
    return rows


# ---------------------------------------------------------------------------
# Backward-compatible catalog search
# ---------------------------------------------------------------------------


def search_catalog(
    vault: Path, query: str, limit: int = 10, tag: str | None = None
) -> list[dict[str, Any]]:
    from .search_backends import CatalogBackend

    backend = CatalogBackend(vault)
    candidates = backend.candidates(query, limit=200)
    if tag:
        wanted = tag.casefold()
        candidates = [
            c
            for c in candidates
            if wanted in {v.casefold() for v in c.fields.get("tags", "").split(" | ")}
        ]
    results = rank_candidates(query, candidates, limit=limit, cutoff=0.0)
    # Map back to catalog row dict shape.
    rows: list[dict[str, Any]] = []
    for result in results:
        c = result.candidate
        row: dict[str, Any] = dict(c.metadata)
        row["path"] = c.path or c.key
        row["title"] = c.label
        rows.append(row)
    return rows[:limit]
