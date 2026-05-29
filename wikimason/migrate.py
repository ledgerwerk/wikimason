from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .build import build_vault
from .config import default_config, write_config_file
from .lint import lint_vault
from .page_profiles import (
    logical_ref_to_relpath,
    profile_for_config,
    relpath_to_logical_ref,
    render_page_text,
    split_page_text,
)
from .paths import rel_to_vault
from .profiles import canonical_profile_name
from .schema import default_schema, schema_toml_lines
from .sources import source_scan


def migrate_vault(
    source_vault: Path,
    target_vault: Path,
    target_profile: str,
) -> dict[str, Any]:
    """Migrate pages from *source_vault* to *target_vault* under *target_profile*.

    Returns a summary dict with:
      - migrated_pages: count of pages converted
      - source_vault: str
      - target_vault: str
      - target_profile: str
      - errors: list[str]
      - lint_errors: list[str]
    """
    errors: list[str] = []

    if not source_vault.exists():
        return {"error": f"source vault not found: {source_vault}"}

    target_profile = canonical_profile_name(target_profile)
    source_config = default_config("markdown", source_vault)
    target_config = default_config(target_profile, target_vault)
    source_profile = profile_for_config(source_config)
    target_profile_obj = profile_for_config(target_config)

    target_vault.mkdir(parents=True, exist_ok=True)

    # Create required directories
    _ensure_dirs(target_vault, target_config)

    # Write config with schema
    schema = default_schema()
    config_path = target_vault / "wikimason.toml"
    write_config_file(config_path, target_config, root_value=".")
    config_path.write_text(
        config_path.read_text(encoding="utf-8")
        + "\n"
        + "\n".join(schema_toml_lines(schema))
        + "\n",
        encoding="utf-8",
    )

    # Collect source pages
    source_pages: list[tuple[str, str]] = []  # (relpath, content)
    for md_file in sorted(source_vault.rglob("*.md")):
        rel = rel_to_vault(source_vault, md_file)
        if _is_operational_file(rel):
            continue
        content = md_file.read_text(encoding="utf-8")
        source_pages.append((rel, content))

    # Convert and write each page
    migrated = 0
    for rel, content in source_pages:
        try:
            _migrate_one_page(
                source_vault,
                target_vault,
                rel,
                content,
                source_profile,
                target_profile_obj,
                source_config,
                target_config,
            )
            migrated += 1
        except Exception as exc:
            errors.append(f"{rel}: {exc}")

    # Copy raw sources
    raw_src = source_vault / "Raw"
    raw_dst = target_vault / "Raw"
    if raw_src.exists():
        _copy_tree(raw_src, raw_dst)

    # Build and scan
    try:
        build_vault(target_vault)
    except Exception as exc:
        errors.append(f"build: {exc}")

    try:
        source_scan(target_vault, update=True, accept_covered=True)
    except Exception as exc:
        errors.append(f"source scan: {exc}")

    lint_results = lint_vault(target_vault)

    return {
        "migrated_pages": migrated,
        "source_vault": str(source_vault),
        "target_vault": str(target_vault),
        "target_profile": target_profile,
        "errors": errors,
        "lint_errors": lint_results if isinstance(lint_results, list) else [],
    }


def _is_operational_file(rel: str) -> bool:
    """Return True if *rel* is an operational file, not a wiki page."""
    name = Path(rel).name
    if name == ".gitkeep":
        return True
    if rel.startswith("Schema/") or rel.startswith("_templates/"):
        return True
    if rel.startswith("Raw/"):
        return True
    if rel in {"source-manifest.jsonl", "wikimason.toml", "AGENTS.md"}:
        return True
    if rel.endswith(".jsonl"):
        return True
    return False


def _migrate_one_page(
    source_vault: Path,
    target_vault: Path,
    rel: str,
    content: str,
    source_profile: Any,
    target_profile: Any,
    source_config: Any,
    target_config: Any,
) -> None:
    """Read, convert, and write a single page from source to target."""
    # Parse source
    metadata, body = split_page_text(content, config=source_config)

    # Get logical ref from source relpath
    logical_ref = relpath_to_logical_ref(rel, config=source_config)
    if logical_ref is None:
        logical_ref = rel.removesuffix(".md").replace("\\", "/")

    # Compute target path
    target_rel = logical_ref_to_relpath(logical_ref, config=target_config)
    target_path = (target_vault / target_rel).resolve()

    # Ensure parent exists
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # Render page in target format
    target_content = render_page_text(metadata, body, config=target_config)
    target_path.write_text(target_content, encoding="utf-8")


def _copy_tree(src: Path, dst: Path) -> None:
    """Copy a directory tree, preserving .gitkeep and empty dirs."""
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, symlinks=False, dirs_exist_ok=False)


def _ensure_dirs(vault: Path, config: Any) -> None:
    """Create the directory structure needed for a wiki vault."""
    from .scaffold import CORE_EMPTY_FILES, _core_keep_files

    for rel in _core_keep_files(config):
        parent = (vault / rel).parent
        parent.mkdir(parents=True, exist_ok=True)
    for rel in CORE_EMPTY_FILES:
        parent = (vault / rel).parent
        parent.mkdir(parents=True, exist_ok=True)
    # Also ensure pages dir and config dirs exist
    (vault / config.profile_config.pages_dir).mkdir(parents=True, exist_ok=True)
    (vault / config.paths.schema).mkdir(parents=True, exist_ok=True)
    (vault / config.paths.templates).mkdir(parents=True, exist_ok=True)
