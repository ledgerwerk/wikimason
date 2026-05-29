from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from .config import WikiMasonConfig, load_runtime_config
from .link_format import format_link
from .page_profiles import split_page_text
from .paths import compiled_md_files
from .schema import load_vault_schema, note_kind_for_path


def iter_catalog_entries(vault: Path) -> Iterator[dict[str, object]]:
    schema = load_vault_schema(vault)
    config = load_runtime_config(vault)
    for path in compiled_md_files(vault):
        rel = path.relative_to(vault).as_posix()
        data, body = split_page_text(path.read_text(encoding="utf-8"), config=config)
        entry = {
            "path": rel,
            "title": extract_title(data, body, path),
            "kind": _infer_kind(schema, rel),
            "tags": data.get("tags", []),
            "topics": data.get("topics", []),
            "status": data.get("status", ""),
            "summary": extract_summary(data, body),
            "sources": data.get("sources", []),
            "source_count": data.get("source_count", 0),
            "aliases": data.get("aliases", []),
        }
        yield entry


def extract_title(data: dict[str, object], body: str, path: Path) -> str:
    title = str(data.get("title") or "").strip()
    if title:
        return title
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem.replace("-", " ").title()


def extract_summary(data: dict[str, object], body: str) -> str:
    summary = str(data.get("summary", "")).strip()
    if summary:
        return summary
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        return stripped
    return ""


def write_catalog(vault: Path, entries: list[dict[str, object]]) -> None:
    target = vault / "Wiki/catalog.jsonl"
    target.write_text(render_catalog_text(entries), encoding="utf-8")


def render_catalog_text(entries: list[dict[str, object]]) -> str:
    rows = [json.dumps(entry, sort_keys=True, ensure_ascii=False) for entry in entries]
    return "\n".join(rows) + ("\n" if rows else "")


def catalog_status(vault: Path) -> dict[str, object]:
    entries = list(iter_catalog_entries(vault))
    expected = render_catalog_text(entries)
    target = vault / "Wiki/catalog.jsonl"
    current = target.read_text(encoding="utf-8") if target.exists() else ""
    return {
        "ok": current == expected,
        "path": "Wiki/catalog.jsonl",
        "count": len(entries),
    }


def link_for_catalog(
    entry: dict[str, object],
    *,
    config: WikiMasonConfig | None = None,
    source_path: str | None = None,
) -> str:
    path = str(entry["path"])
    title = str(entry["title"])
    if config is None:
        return f"[[{path.removesuffix('.md')}|{title}]]"
    return format_link(config.links, path, label=title, source_path=source_path)


def _infer_kind(schema, path: str) -> str:
    return note_kind_for_path(schema, path) or "note"
