from __future__ import annotations

import re
from pathlib import Path

from .errors import UsageError
from .paths import rel_to_vault, slugify_title

WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def clean_link(value: str) -> str:
    target = normalize_wikilink_name(value)
    if target.endswith(".md"):
        target = target[:-3]
    return target.strip()


def ensure_wikilink(value: str) -> str:
    return f"[[{clean_link(value)}]]"


def normalize_wikilink_name(name: str) -> str:
    value = name.strip()
    if value.startswith("[[") and value.endswith("]]"):
        value = value[2:-2]
    value = value.split("|", 1)[0]
    value = value.split("#", 1)[0]
    value = value.split("^", 1)[0]
    return value.strip()


def resolve_file_name(vault: Path, file_name: str) -> Path:
    target = normalize_wikilink_name(file_name)
    target_basename = Path(target).name.lower().removesuffix(".md")
    target_slug = slugify_title(target_basename)
    matches: list[Path] = []
    for p in sorted(vault.rglob("*.md")):
        stem = p.name.lower().removesuffix(".md")
        if stem == target_basename or stem == target_slug:
            matches.append(p)
    if not matches:
        raise UsageError(f"file not found: {file_name}")
    if len(matches) > 1:
        candidates = ", ".join(rel_to_vault(vault, m) for m in matches)
        raise UsageError(
            f"ambiguous file target: {file_name}. candidates: {candidates}"
        )
    return matches[0]


def extract_wikilinks(text: str) -> list[str]:
    return [normalize_wikilink_name(m.group(1)) for m in WIKILINK_RE.finditer(text)]


def extract_links(text: str) -> list[str]:
    return extract_wikilinks(text)
