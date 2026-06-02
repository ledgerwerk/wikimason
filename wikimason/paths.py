from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterator
from pathlib import Path

from .config import find_wiki_root, load_runtime_config
from .errors import UsageError
from .page_profiles import relpath_to_logical_ref
from .schema import (
    VaultSchema,
    default_schema,
    load_vault_schema,
)
from .schema import (
    compiled_prefixes as schema_compiled_prefixes,
)
from .schema import (
    kind_to_folder as schema_kind_to_folder,
)

_PATH_PUNCT_TRANSLATION = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u201b": "'",
        "\u2032": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u201e": '"',
        "\u201f": '"',
        "\u2033": '"',
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
    }
)

_UNICODE_ESCAPE_RE = re.compile(r"\\u([0-9a-fA-F]{4})|\\U([0-9a-fA-F]{8})")


def decode_unicode_escape_literals(value: str) -> str:
    """Decode literal Unicode escape sequences from JSON-based agent writes.

    Only decode explicit \\uXXXX and \\UXXXXXXXX forms.  Do not use
    bytes(...).decode("unicode_escape"), because that also rewrites
    unrelated backslash escapes and can corrupt paths.
    """

    def repl(match: re.Match[str]) -> str:
        code = match.group(1) or match.group(2)
        return chr(int(code, 16))

    return _UNICODE_ESCAPE_RE.sub(repl, value)


def normalize_path_text_for_matching(value: str) -> str:
    """Canonical path text for matching."""
    value = decode_unicode_escape_literals(value)
    value = unicodedata.normalize("NFKC", value)
    value = value.translate(_PATH_PUNCT_TRANSLATION)
    value = value.replace("\\", "/")
    value = re.sub(r"\s+", " ", value).strip()
    return value


def is_vault(path: Path) -> bool:
    return find_wiki_root(path) is not None


def resolve_vault(
    path: str | None,
    *,
    env: str | None = None,
    config_path: str | Path | None = None,
    cwd: Path | None = None,
) -> Path:
    from .context import resolve_context

    return resolve_context(
        cwd=cwd,
        env=env,
        config_path=config_path,
        vault=path,
    ).root


def ensure_inside_vault(vault: Path, path: Path) -> Path:
    resolved = path.expanduser().resolve()
    vault_resolved = vault.expanduser().resolve()
    try:
        resolved.relative_to(vault_resolved)
    except ValueError as exc:
        raise UsageError("path traversal or outside-vault write rejected") from exc
    return resolved


def rel_to_vault(vault: Path, path: Path) -> str:
    try:
        return path.relative_to(vault).as_posix()
    except ValueError:
        pass
    try:
        return path.resolve().relative_to(vault.resolve()).as_posix()
    except ValueError:
        pass
    # String-based fallback: strip the vault prefix from the string path.
    # This handles edge cases on Windows where Path.resolve() normalizes
    # the vault differently (UNC prefix, case differences, junction targets).
    vault_str = vault.resolve().as_posix().rstrip("/")
    path_str = path.resolve().as_posix()
    if path_str.startswith(vault_str + "/"):
        return path_str[len(vault_str) + 1 :]
    # Last resort: try case-insensitive match on Windows
    vault_lower = vault_str.casefold()
    path_lower = path_str.casefold()
    if path_lower.startswith(vault_lower + "/"):
        return path_str[len(vault_str) + 1 :]
    raise ValueError(f"{path!s} is not relative to {vault!s}")


def resolve_path_in_vault(vault: Path, rel: str) -> Path:
    candidate = ensure_inside_vault(vault, vault / rel)
    if candidate.exists():
        return candidate
    if not candidate.suffix:
        candidate_md = ensure_inside_vault(vault, vault / f"{rel}.md")
        if candidate_md.exists():
            return candidate_md
    return candidate


def slugify_title(title: str) -> str:
    normalized = (
        unicodedata.normalize("NFKD", title)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    normalized = re.sub(r"\s+", "-", normalized.strip())
    normalized = re.sub(r"[^a-z0-9_-]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized or "note"


def kind_to_folder(
    kind: str, vault: Path | None = None, schema: VaultSchema | None = None
) -> str:
    active_schema = schema or (load_vault_schema(vault) if vault else default_schema())
    return schema_kind_to_folder(active_schema, kind)


def wiki_md_files(vault: Path) -> Iterator[Path]:
    config = load_runtime_config(vault)
    root = vault / config.profile_config.pages_dir
    if not root.exists():
        return
    yield from sorted(root.rglob("*.md"))


def compiled_md_files(vault: Path, schema: VaultSchema | None = None) -> Iterator[Path]:
    config = load_runtime_config(vault)
    pages_dir = config.profile_config.pages_dir
    hub_filename = config.profile_config.hub_filename
    log_rel = config.logging.path
    prefixes = schema_compiled_prefixes(schema or load_vault_schema(vault))
    for path in wiki_md_files(vault):
        rel = rel_to_vault(vault, path)
        logical_ref = relpath_to_logical_ref(rel, config=config) or rel.removesuffix(
            ".md"
        )
        if (
            rel == f"{pages_dir}/log.md"
            or rel == log_rel
            or path.name in {"index.md", hub_filename}
            or path.name.endswith("___index.md")
            or path.name.endswith(f"___{hub_filename}")
        ):
            continue
        if any(
            rel.startswith(prefix)
            or logical_ref.startswith(prefix.removesuffix(".md"))
            or f"{logical_ref}.md".startswith(prefix)
            for prefix in prefixes
        ):
            yield path


def raw_md_files(vault: Path) -> Iterator[Path]:
    yield from sorted((vault / "Raw").rglob("*.md"))


def source_md_files(vault: Path) -> Iterator[Path]:
    yield from sorted((vault / "Raw/Sources").rglob("*.md"))


def path_match_key(value: str) -> str:
    normalized = normalize_path_text_for_matching(value)
    normalized = normalized.casefold()
    return normalized


def build_link_targets(vault: Path) -> set[str]:
    config = load_runtime_config(vault)
    targets: set[str] = set()
    for path in sorted(vault.rglob("*.md")):
        rel = rel_to_vault(vault, path)
        no_ext = rel.removesuffix(".md")
        targets.add(rel)
        targets.add(no_ext)
        targets.add(path.stem)
        targets.add(path.name)
        targets.add(path.stem.lower())
        targets.add(no_ext.lower())
        logical_ref = relpath_to_logical_ref(rel, config=config)
        if logical_ref is not None:
            logical_md = f"{logical_ref}.md"
            targets.add(logical_ref)
            targets.add(logical_md)
            targets.add(logical_ref.lower())
            targets.add(logical_md.lower())
            targets.add(Path(logical_ref).name)
            targets.add(Path(logical_ref).name.lower())
    return targets
