from __future__ import annotations

from pathlib import Path
from typing import Protocol

# ---------------------------------------------------------------------------
# FTS5 table DDL
# ---------------------------------------------------------------------------

FTS5_CREATE = """
CREATE VIRTUAL TABLE IF NOT EXISTS search_fts USING fts5(
  path,
  title,
  aliases,
  tags,
  headings,
  body,
  content='',
  tokenize='unicode61'
);
"""

DOCS_CREATE = """
CREATE TABLE IF NOT EXISTS search_docs (
  path TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  updated_at TEXT NOT NULL
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
# Placeholder implementation
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
