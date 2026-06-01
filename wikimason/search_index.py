"""SQLite FTS5 search index for WikiMason.

Replaces the previous :class:`StubSearchIndex` with a real full-text search
implementation backed by SQLite FTS5.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

# ---------------------------------------------------------------------------
# Schema DDL
# ---------------------------------------------------------------------------

DOCS_CREATE = """\
CREATE TABLE IF NOT EXISTS search_docs (
    docid INTEGER PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    aliases TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '',
    headings TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);
"""

FTS5_CREATE = """\
CREATE VIRTUAL TABLE IF NOT EXISTS search_fts USING fts5(
    path,
    title,
    aliases,
    tags,
    headings,
    summary,
    body,
    tokenize='unicode61 remove_diacritics 2'
);
"""

META_CREATE = """\
CREATE TABLE IF NOT EXISTS search_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

DEFAULT_INDEX_PATH = ".wikimason/search.sqlite3"

# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class SearchIndex(Protocol):
    def index(self, vault: Path) -> dict[str, object]: ...

    def rebuild(self, vault: Path) -> dict[str, object]: ...

    def query(self, query_text: str, *, limit: int = 20) -> list[dict[str, object]]: ...

    def status(self) -> dict[str, object]: ...


# ---------------------------------------------------------------------------
# SQLite FTS5 implementation
# ---------------------------------------------------------------------------


class SQLiteSearchIndex:
    """Real SQLite FTS5 search index.

    Stores page and source documents in a content table and a corresponding
    FTS5 virtual table for fast full-text search with BM25 ranking.
    """

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    # -- connection management --

    def _connect(self) -> sqlite3.Connection:
        if self._conn is not None:
            return self._conn
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(DOCS_CREATE + FTS5_CREATE + META_CREATE)
        conn.commit()
        self._conn = conn
        return conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # -- indexing --

    def index(self, vault: Path) -> dict[str, object]:
        """Index all vault documents. Returns counts."""
        return self.rebuild(vault)

    def rebuild(self, vault: Path) -> dict[str, object]:
        """Rebuild the entire index from scratch."""
        conn = self._connect()
        # Clear existing data
        conn.execute("DELETE FROM search_fts")
        conn.execute("DELETE FROM search_docs")
        conn.execute("DELETE FROM search_meta")

        page_count = 0
        source_count = 0

        # Index compiled pages
        from .paths import compiled_md_files, rel_to_vault
        from .page_profiles import split_page_text
        from .config import load_runtime_config

        config = load_runtime_config(vault)
        for path in compiled_md_files(vault):
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            rel = rel_to_vault(vault, path)
            data, body = split_page_text(text, config=config)
            sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
            title = str(data.get("title", ""))
            aliases = " ".join(str(a) for a in _as_list(data.get("aliases")))
            tags = " ".join(str(t) for t in _as_list(data.get("tags")))
            summary = str(data.get("summary", ""))
            headings = _extract_headings(body)

            self._upsert_doc(
                conn,
                path=rel,
                kind="page",
                sha256=sha,
                title=title,
                aliases=aliases,
                tags=tags,
                headings=headings,
                summary=summary,
                body=_strip_frontmatter_from_text(text),
            )
            page_count += 1

        # Index raw sources
        from .paths import source_md_files

        for path in source_md_files(vault):
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            rel = rel_to_vault(vault, path)
            sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
            body = _strip_frontmatter_from_text(text)
            self._upsert_doc(
                conn,
                path=rel,
                kind="source",
                sha256=sha,
                title=path.stem,
                aliases="",
                tags="",
                headings=_extract_headings(body),
                summary="",
                body=body,
            )
            source_count += 1

        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO search_meta (key, value) VALUES (?, ?)",
            ("last_rebuild", now),
        )
        conn.commit()

        return {
            "ok": True,
            "page_count": page_count,
            "source_count": source_count,
            "total": page_count + source_count,
        }

    def _upsert_doc(
        self,
        conn: sqlite3.Connection,
        *,
        path: str,
        kind: str,
        sha256: str,
        title: str = "",
        aliases: str = "",
        tags: str = "",
        headings: str = "",
        summary: str = "",
        body: str = "",
    ) -> None:
        """Insert or update a single document and its FTS row."""
        now = datetime.now(timezone.utc).isoformat()
        # Check existing
        row = conn.execute(
            "SELECT docid, sha256 FROM search_docs WHERE path = ?",
            (path,),
        ).fetchone()
        if row is not None:
            docid = row[0]
            # Remove old FTS row
            conn.execute("DELETE FROM search_fts WHERE rowid = ?", (docid,))
            conn.execute(
                "UPDATE search_docs SET kind=?, sha256=?, title=?, aliases=?, "
                "tags=?, headings=?, summary=?, updated_at=? WHERE docid=?",
                (kind, sha256, title, aliases, tags, headings, summary, now, docid),
            )
        else:
            cursor = conn.execute(
                "INSERT INTO search_docs (path, kind, sha256, title, aliases, "
                "tags, headings, summary, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (path, kind, sha256, title, aliases, tags, headings, summary, now),
            )
            docid = cursor.lastrowid

        conn.execute(
            "INSERT INTO search_fts (rowid, path, title, aliases, tags, "
            "headings, summary, body) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (docid, path, title, aliases, tags, headings, summary, body),
        )

    # -- querying --

    def query(self, query_text: str, *, limit: int = 20) -> list[dict[str, object]]:
        """Run an FTS5 query and return ranked results."""
        conn = self._connect()
        fts_query = to_safe_fts_query(query_text)
        if not fts_query:
            return []
        try:
            rows = conn.execute(
                """
                SELECT d.path, d.kind, d.title, d.tags, d.summary,
                       bm25(search_fts, 2.0, 4.0, 3.0, 2.0, 2.5, 1.0, 1.0) AS rank
                FROM search_fts
                JOIN search_docs d ON d.docid = search_fts.rowid
                WHERE search_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (fts_query, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            return []

        results: list[dict[str, object]] = []
        for row in rows:
            # BM25 rank is negative (more negative = better match).
            # Convert to a 0-100 score.
            score = _bm25_to_score(row[5])
            results.append({
                "path": row[0],
                "kind": row[1],
                "title": row[2],
                "tags": row[3],
                "summary": row[4],
                "score": score,
                "reason": "body:fts",
            })
        return results

    def status(self) -> dict[str, object]:
        """Return index status."""
        try:
            conn = self._connect()
            count = conn.execute("SELECT COUNT(*) FROM search_docs").fetchone()[0]
            last_rebuild = conn.execute(
                "SELECT value FROM search_meta WHERE key = 'last_rebuild'"
            ).fetchone()
            return {
                "ok": True,
                "doc_count": count,
                "last_rebuild": last_rebuild[0] if last_rebuild else None,
                "db_path": str(self._db_path),
            }
        except Exception as exc:
            return {"ok": False, "reason": str(exc)}


# ---------------------------------------------------------------------------
# Placeholder (backward compat)
# ---------------------------------------------------------------------------


class StubSearchIndex:
    """Placeholder for the SQLite FTS5 search index.

    This stub exists so that downstream code can depend on the protocol
    without requiring an actual SQLite database. Replace with a real
    implementation when FTS5 indexing is enabled.
    """

    def index(self, vault: Path) -> dict[str, object]:
        return {"ok": False, "reason": "FTS5 index not yet implemented"}

    def rebuild(self, vault: Path) -> dict[str, object]:
        return {"ok": False, "reason": "FTS5 index not yet implemented"}

    def query(self, query_text: str, *, limit: int = 20) -> list[dict[str, object]]:
        return []

    def status(self) -> dict[str, object]:
        return {"ok": False, "reason": "FTS5 index not yet implemented"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def open_search_index(vault: Path, *, index_path: str | None = None) -> SQLiteSearchIndex:
    """Open (or create) a search index for *vault*."""
    path = vault / (index_path or DEFAULT_INDEX_PATH)
    return SQLiteSearchIndex(path)


def index_status(vault: Path) -> dict[str, object]:
    """Quick status check for the vault search index."""
    db_path = vault / DEFAULT_INDEX_PATH
    if not db_path.exists():
        return {"ok": False, "reason": "search index does not exist"}
    idx = SQLiteSearchIndex(db_path)
    return idx.status()


def to_safe_fts_query(query_text: str) -> str:
    """Convert a user query into a safe FTS5 expression.

    For ``llm wiki`` this generates ``"llm" OR "wiki" OR "llm wiki"``.
    Special FTS syntax characters are stripped from individual terms.
    """
    # Strip FTS special characters
    cleaned = re.sub(r'[{}()"*:^|!~+-]', " ", query_text).strip()
    if not cleaned:
        return ""
    terms = cleaned.split()
    if not terms:
        return ""
    parts: list[str] = []
    # Individual terms
    for term in terms:
        if term:
            parts.append(f'"{term}"')
    # Full phrase
    if len(terms) > 1:
        parts.append(f'"{cleaned}"')
    return " OR ".join(parts)


def _as_list(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    return []


def _extract_headings(body: str) -> str:
    """Extract Markdown headings from body text."""
    headings: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip()
            if heading:
                headings.append(heading)
    return " ".join(headings)

def _strip_frontmatter_from_text(text: str) -> str:
    """Remove YAML frontmatter from text for indexing."""
    if not text.startswith("---"):
        return text
    end = text.find("---", 3)
    if end == -1:
        return text
    return text[end + 3:].lstrip("\n")


def _bm25_to_score(rank: float) -> float:
    """Convert a BM25 rank value (negative, more negative = better) to a 0-100 score."""
    if rank >= 0:
        return 50.0
    # Typical FTS5 BM25 values range from -0.5 to -10+ for good matches.
    # Map: rank=-0.5 → ~100, rank=-10 → ~50, rank > -0.5 → 100
    raw = min(100.0, max(0.0, 100.0 + rank * 10.0))
    return round(raw, 1)
