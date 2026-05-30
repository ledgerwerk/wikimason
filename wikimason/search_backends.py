from __future__ import annotations

import json
from pathlib import Path

from .paths import compiled_md_files, rel_to_vault, source_md_files
from .search import SearchCandidate


def _as_list(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    return []


# ---------------------------------------------------------------------------
# CatalogBackend
# ---------------------------------------------------------------------------


class CatalogBackend:
    def __init__(self, vault: Path) -> None:
        self._vault = vault

    def candidates(self, query: str, *, limit: int = 200) -> list[SearchCandidate]:
        catalog = self._vault / "Wiki/catalog.jsonl"
        if not catalog.exists():
            return []
        rows = [
            json.loads(line)
            for line in catalog.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        results: list[SearchCandidate] = []
        for row in rows:
            title = str(row.get("title", ""))
            path = str(row.get("path", ""))
            aliases = tuple(str(a) for a in _as_list(row.get("aliases", [])))
            summary = str(row.get("summary", ""))
            tags = " ".join(str(v) for v in _as_list(row.get("tags", [])))
            topics = " ".join(str(v) for v in _as_list(row.get("topics", [])))
            results.append(
                SearchCandidate(
                    key=path,
                    kind="page",
                    label=title,
                    path=path,
                    aliases=aliases,
                    fields={
                        "summary": summary,
                        "tags": tags,
                        "topics": topics,
                    },
                    metadata=row,
                )
            )
        return results[:limit]


# ---------------------------------------------------------------------------
# SourceBackend
# ---------------------------------------------------------------------------


class SourceBackend:
    def __init__(self, vault: Path) -> None:
        self._vault = vault

    def candidates(self, query: str, *, limit: int = 200) -> list[SearchCandidate]:
        results: list[SearchCandidate] = []
        for path in source_md_files(self._vault):
            rel = rel_to_vault(self._vault, path)
            name = path.name
            stem = path.stem
            results.append(
                SearchCandidate(
                    key=rel,
                    kind="source",
                    label=name,
                    path=rel,
                    fields={"stem": stem, "name": name},
                )
            )
        return results[:limit]


# ---------------------------------------------------------------------------
# PathBackend
# ---------------------------------------------------------------------------


class PathBackend:
    def __init__(self, vault: Path) -> None:
        self._vault = vault

    def candidates(self, query: str, *, limit: int = 200) -> list[SearchCandidate]:
        results: list[SearchCandidate] = []
        for path in compiled_md_files(self._vault):
            rel = rel_to_vault(self._vault, path)
            results.append(
                SearchCandidate(
                    key=rel,
                    kind="file",
                    label=path.stem,
                    path=rel,
                )
            )
        return results[:limit]


# ---------------------------------------------------------------------------
# LinkBackend
# ---------------------------------------------------------------------------


class LinkBackend:
    def __init__(self, vault: Path) -> None:
        self._vault = vault

    def candidates(self, query: str, *, limit: int = 200) -> list[SearchCandidate]:
        from .catalog import iter_catalog_entries

        results: list[SearchCandidate] = []
        for entry in iter_catalog_entries(self._vault):
            path = str(entry.get("path", ""))
            title = str(entry.get("title", ""))
            aliases = tuple(str(a) for a in _as_list(entry.get("aliases", [])))
            results.append(
                SearchCandidate(
                    key=path,
                    kind="page",
                    label=title,
                    path=path,
                    aliases=aliases,
                )
            )
        return results[:limit]


# ---------------------------------------------------------------------------
# FileNameBackend
# ---------------------------------------------------------------------------


class FileNameBackend:
    def __init__(self, vault: Path) -> None:
        self._vault = vault

    def candidates(self, query: str, *, limit: int = 200) -> list[SearchCandidate]:
        results: list[SearchCandidate] = []
        for path in self._vault.rglob("*.md"):
            rel = rel_to_vault(self._vault, path)
            results.append(
                SearchCandidate(
                    key=rel,
                    kind="file",
                    label=path.stem,
                    path=rel,
                )
            )
        results.sort(key=lambda row: row.key)
        return results[:limit]


# ---------------------------------------------------------------------------
# CommandBackend
# ---------------------------------------------------------------------------


class CommandBackend:
    def candidates(self, query: str, *, limit: int = 200) -> list[SearchCandidate]:
        from .command_registry import COMMAND_REGISTRY

        results: list[SearchCandidate] = []
        for info in COMMAND_REGISTRY:
            if info.legacy_aliases:
                continue
            path_str = " ".join(info.path)
            results.append(
                SearchCandidate(
                    key=path_str,
                    kind="command",
                    label=path_str,
                    fields={"summary": info.summary},
                )
            )
        return results[:limit]
