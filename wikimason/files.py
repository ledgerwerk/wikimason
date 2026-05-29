from __future__ import annotations

import os
import shutil
import webbrowser
from pathlib import Path

from .config import WikiMasonConfig, load_runtime_config
from .errors import UsageError
from .frontmatter import render_frontmatter, split_frontmatter
from .page_profiles import render_page_text, split_page_text
from .paths import rel_to_vault, resolve_path_in_vault, slugify_title
from .templates import resolve_template, template_path
from .wikilinks import resolve_file_name


def resolve_existing_path(vault: Path, target: str) -> Path:
    path = resolve_path_in_vault(vault, target)
    if path.exists():
        return path
    return resolve_file_name(vault, target)


def list_files(
    vault: Path, path: str | None = None, *, ext: str | None = None
) -> list[str]:
    root = resolve_path_in_vault(vault, path) if path else vault
    rows: list[str] = []
    for item in sorted(root.rglob("*")):
        if not item.is_file():
            continue
        if ext and item.suffix.lstrip(".") != ext:
            continue
        rows.append(rel_to_vault(vault, item))
    return rows


def list_folders(vault: Path, path: str | None = None) -> list[str]:
    root = resolve_path_in_vault(vault, path) if path else vault
    return [
        rel_to_vault(vault, item) for item in sorted(root.rglob("*")) if item.is_dir()
    ]


def folder_file_count(vault: Path, path: str | None = None) -> int:
    root = resolve_path_in_vault(vault, path) if path else vault
    return sum(1 for item in root.rglob("*") if item.is_file())


def write_file(
    vault: Path,
    path: str,
    *,
    content: str = "",
    overwrite: bool = False,
    template: str | None = None,
    title: str | None = None,
) -> Path:
    target = resolve_path_in_vault(vault, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not overwrite:
        raise UsageError("target exists; pass --overwrite")
    if template:
        template_text = read_template(vault, template)
        content = resolve_template(
            template_text,
            title or target.stem,
            slug=slugify_title(title or target.stem),
        )
    target.write_text(content, encoding="utf-8")
    return target


def read_template(vault: Path, name: str) -> str:
    path = template_path(vault, name)
    if not path.exists():
        raise UsageError(f"template not found: {name}")
    return path.read_text(encoding="utf-8")


def read_file(vault: Path, path: str) -> str:
    return resolve_existing_path(vault, path).read_text(encoding="utf-8")


def append_file(vault: Path, path: str, content: str, *, inline: bool = False) -> Path:
    target = resolve_path_in_vault(vault, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    if inline:
        updated = existing + content
    else:
        separator = "" if not existing or existing.endswith("\n") else "\n"
        updated = existing + separator + content
    target.write_text(updated, encoding="utf-8")
    return target


def prepend_file(vault: Path, path: str, content: str) -> Path:
    target = resolve_path_in_vault(vault, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    text = target.read_text(encoding="utf-8") if target.exists() else ""
    config = load_runtime_config(vault)
    rel = rel_to_vault(vault, target)
    if rel.startswith(f"{config.profile_config.pages_dir}/"):
        data, body = split_page_text(text, config=config)
        use_page_profile = True
    else:
        data, body = split_frontmatter(text)
        use_page_profile = False
    if data:
        separator = "\n" if content and not content.endswith("\n") else ""
        new_body = f"{content}{separator}{body.lstrip()}"
        updated = (
            render_page_text(data, new_body, config=config)
            if use_page_profile
            else f"{render_frontmatter(data)}\n{new_body}"
        )
    else:
        updated = (
            content + ("\n" if content and not content.endswith("\n") else "") + text
        )
    target.write_text(updated, encoding="utf-8")
    return target


def move_file(vault: Path, source: str, destination: str) -> Path:
    src = resolve_existing_path(vault, source)
    dst = resolve_path_in_vault(vault, destination)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return dst


def rename_file(vault: Path, source: str, new_name: str) -> Path:
    src = resolve_existing_path(vault, source)
    if "/" in new_name or new_name.endswith(".md"):
        dst = resolve_path_in_vault(vault, new_name)
    else:
        dst = src.with_name(f"{slugify_title(new_name)}.md")
    dst.parent.mkdir(parents=True, exist_ok=True)
    src.rename(dst)
    return dst


def delete_file(vault: Path, path: str, *, permanent: bool = False) -> str:
    src = resolve_existing_path(vault, path)
    if permanent:
        src.unlink(missing_ok=True)
        return "deleted"
    trash = vault / ".trash"
    trash.mkdir(parents=True, exist_ok=True)
    dst = trash / src.name
    shutil.move(str(src), str(dst))
    return rel_to_vault(vault, dst)


def open_file(config: WikiMasonConfig, path: Path) -> str:
    template = config.tool_config.open_uri_template
    target = path.expanduser().resolve()
    uri = (
        template.format(path=target.as_posix())
        if template is not None
        else target.as_posix()
    )
    if os.environ.get("WIKIMASON_OPEN_BROWSER", "0") == "1":
        webbrowser.open(uri)
    return uri


def search_files(
    vault: Path,
    query: str,
    *,
    path: str | None = None,
    limit: int = 100,
    context: bool = False,
    case_sensitive: bool = False,
    fuzzy: bool = False,
) -> list[str]:
    root = resolve_path_in_vault(vault, path) if path else vault
    needle = query if case_sensitive else query.lower()
    rows: list[str] = []
    for item in sorted(root.rglob("*")):
        if not item.is_file() or item.suffix.lower() not in {".md", ".txt"}:
            continue
        text = item.read_text(encoding="utf-8", errors="ignore")
        haystack = text if case_sensitive else text.lower()
        if context:
            for index, line in enumerate(text.splitlines(), start=1):
                line_haystack = line if case_sensitive else line.lower()
                if needle in line_haystack:
                    rows.append(f"{rel_to_vault(vault, item)}:{index}:{line}")
                    if len(rows) >= limit:
                        return rows
            continue
        if needle in haystack:
            rows.append(rel_to_vault(vault, item))
            if len(rows) >= limit:
                return rows
    if fuzzy and not rows:
        from .search import approximate_snippets

        for item in sorted(root.rglob("*")):
            if not item.is_file() or item.suffix.lower() not in {".md", ".txt"}:
                continue
            text = item.read_text(encoding="utf-8", errors="ignore")
            spans = approximate_snippets(query, text, limit=1)
            if spans:
                rows.append(rel_to_vault(vault, item))
                if len(rows) >= limit:
                    return rows
    return rows[:limit]
