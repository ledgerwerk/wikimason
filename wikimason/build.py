from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .agents import write_agents_md
from .catalog import iter_catalog_entries, link_for_catalog, write_catalog
from .commands import (
    render_command_reference_markdown,
)
from .config import load_runtime_config
from .link_format import format_link
from .page_profiles import logical_ref_to_relpath, split_page_text, update_page_text
from .paths import compiled_md_files
from .schema import (
    load_vault_schema,
    render_frontmatter_schema_markdown,
    schema_source_label,
)
from .schema_upgrade import migrate_compiled_note_types
from .storage import write_text_atomic


@dataclass(frozen=True)
class BuildResult:
    updated_type_count: int
    updated_source_count: int
    catalog_count: int


def sync_source_count(vault: Path) -> int:
    config = load_runtime_config(vault)
    updated = 0
    for path in compiled_md_files(vault):
        text = path.read_text(encoding="utf-8")
        data, _ = split_page_text(text, config=config)
        sources = data.get("sources", [])
        if not isinstance(sources, list):
            continue
        expected = len(sources)
        source_count: Any = data.get("source_count", 0)
        if int(source_count) == expected:
            continue
        write_text_atomic(
            path,
            update_page_text(text, {"source_count": expected}, config=config),
        )
        updated += 1
    return updated


def build_vault(vault: Path) -> BuildResult:
    config = load_runtime_config(vault)
    schema = load_vault_schema(vault, config=config)
    schema_dir = vault / config.paths.schema
    schema_dir.mkdir(parents=True, exist_ok=True)

    type_result = migrate_compiled_note_types(vault)
    updated = sync_source_count(vault)
    entries = list(iter_catalog_entries(vault))
    write_catalog(vault, entries)
    rebuild_indexes(vault, entries, schema=schema, config=config)

    write_text_atomic(
        schema_dir / "frontmatter-schema.md",
        render_frontmatter_schema_markdown(
            schema,
            source_label=schema_source_label(vault, config=config),
        ),
    )
    write_text_atomic(
        schema_dir / "command-reference.md",
        render_command_reference_markdown(),
    )

    write_agents_md(vault, config=config)

    # Rebuild search index
    try:
        from .search_index import open_search_index

        idx = open_search_index(vault)
        idx.rebuild(vault)
        idx.close()
    except Exception:
        pass  # Search index is optional; build should not fail
    return BuildResult(
        updated_type_count=type_result.updated,
        updated_source_count=updated,
        catalog_count=len(entries),
    )


def rebuild_indexes(
    vault: Path,
    entries: list[dict[str, Any]],
    *,
    schema: Any = None,
    config: Any = None,  # noqa: E501
) -> None:
    for relpath, content in render_index_pages(
        vault, entries, schema=schema, config=config
    ).items():
        target = vault / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        write_text_atomic(target, content)


def render_index_pages(
    vault: Path,
    entries: list[dict[str, Any]],
    *,
    schema: Any = None,
    config: Any = None,  # noqa: E501
) -> dict[str, str]:
    active_schema = schema or load_vault_schema(vault)
    active_config = config or load_runtime_config(vault)
    top_index_rel = logical_ref_to_relpath("Wiki/index", config=active_config)
    top_lines = ["# LLM Wiki", ""]
    rendered: dict[str, str] = {}
    for kind_config in active_schema.note_kinds.values():
        section_name = Path(kind_config.folder).name
        section_index_rel = logical_ref_to_relpath(
            f"{kind_config.folder}/index", config=active_config
        )
        top_lines.append(
            f"- {format_link(active_config.links, section_index_rel, label=section_name, source_path=top_index_rel)}"  # noqa: E501
        )
    top_lines.append("")
    for name, kind_config in active_schema.note_kinds.items():
        folder = kind_config.folder
        section_name = Path(folder).name
        singular = name.replace("-", " ").title()
        section_entries = [entry for entry in entries if str(entry.get("kind")) == name]
        section_index_rel = logical_ref_to_relpath(
            f"{folder}/index", config=active_config
        )
        section_lines = [f"# {singular} Index", ""]
        for entry in sorted(section_entries, key=lambda row: str(row["title"]).lower()):
            summary = str(entry.get("summary", "")).strip()
            suffix = f" - {summary}" if summary else ""
            section_lines.append(
                f"- {link_for_catalog(entry, config=active_config, source_path=section_index_rel)}{suffix}"  # noqa: E501
            )
        if len(section_lines) == 2:
            section_lines.append("- (none)")
        rendered[section_index_rel] = "\n".join(section_lines).rstrip() + "\n"
        top_lines.append(f"## {singular} Index")
        top_lines.extend(section_lines[2:])
        top_lines.append("")
    rendered[top_index_rel] = "\n".join(top_lines).rstrip() + "\n"
    return rendered


def index_status(vault: Path) -> dict[str, Any]:
    expected = render_index_pages(vault, list(iter_catalog_entries(vault)))
    pages: list[dict[str, Any]] = []
    ok = True
    for relpath, expected_text in expected.items():
        target = vault / relpath
        current_text = target.read_text(encoding="utf-8") if target.exists() else ""
        page_ok = current_text == expected_text
        ok = ok and page_ok
        pages.append({"path": relpath, "ok": page_ok})
    return {"ok": ok, "pages": pages}
