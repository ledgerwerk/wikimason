from __future__ import annotations

from pathlib import Path

from .config import WikiMasonConfig, load_runtime_config
from .frontmatter import render_frontmatter, split_frontmatter, update_frontmatter
from .page_profiles import render_page_text, split_page_text, update_page_text
from .paths import compiled_md_files
from .text import parse_bool, parse_list_or_json, parse_number_or_text


def set_property(
    text: str,
    name: str,
    value: str,
    kind: str | None = None,
    *,
    config: WikiMasonConfig | None = None,
    path: Path | None = None,
) -> str:
    parsed: object = value
    if kind == "list":
        parsed = parse_list_or_json(value)
    elif kind == "number":
        parsed = parse_number_or_text(value)
    elif kind == "checkbox":
        parsed = parse_bool(value)
    elif kind == "date":
        parsed = value
    if _use_page_profile(path, config):
        return update_page_text(text, {name: parsed}, config=config)
    return update_frontmatter(text, {name: parsed})


def read_property(
    text: str,
    name: str,
    *,
    config: WikiMasonConfig | None = None,
    path: Path | None = None,
) -> object | None:
    if _use_page_profile(path, config):
        data, _ = split_page_text(text, config=config)
    else:
        data, _ = split_frontmatter(text)
    return data.get(name)


def remove_property(
    text: str,
    name: str,
    *,
    config: WikiMasonConfig | None = None,
    path: Path | None = None,
) -> str:
    if _use_page_profile(path, config):
        data, body = split_page_text(text, config=config)
        data.pop(name, None)
        return render_page_text(data, body, config=config)
    data, body = split_frontmatter(text)
    data.pop(name, None)
    return f"{render_frontmatter(data)}\n{body.lstrip()}"


def list_property_names(
    vault: Path,
    path: Path | None = None,
    *,
    config: WikiMasonConfig | None = None,
) -> list[str]:
    active_config = config or load_runtime_config(vault)
    if path is not None:
        text = path.read_text(encoding="utf-8")
        if _use_page_profile(path, active_config):
            data, _ = split_page_text(text, config=active_config)
        else:
            data, _ = split_frontmatter(text)
        return sorted(str(key) for key in data.keys())
    rows: dict[str, int] = {}
    for item in compiled_md_files(vault):
        data, _ = split_page_text(
            item.read_text(encoding="utf-8"), config=active_config
        )
        for key in data.keys():
            rows[str(key)] = rows.get(str(key), 0) + 1
    return sorted(rows)


def update_aliases(
    text: str,
    *,
    add: tuple[str, ...] = (),
    remove: tuple[str, ...] = (),
    config: WikiMasonConfig | None = None,
    path: Path | None = None,
) -> str:
    current = read_property(text, "aliases", config=config, path=path)
    values = [str(value) for value in current] if isinstance(current, list) else []
    for item in add:
        if item not in values:
            values.append(item)
    for item in remove:
        values = [value for value in values if value != item]
    if _use_page_profile(path, config):
        return update_page_text(text, {"aliases": values}, config=config)
    return update_frontmatter(text, {"aliases": values})


def _use_page_profile(path: Path | None, config: WikiMasonConfig | None) -> bool:
    if path is None and config is None:
        return False
    if path is None or config is None:
        return True
    try:
        rel = path.resolve().relative_to(config.root.resolve()).as_posix()
    except ValueError:
        rel = path.as_posix()
    return rel.startswith(f"{config.profile_config.pages_dir}/")
