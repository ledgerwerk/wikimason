from __future__ import annotations

from dataclasses import dataclass

from .errors import UsageError

DEFAULT_PATHS: dict[str, str] = {
    "raw": "Raw",
    "sources": "Raw/Sources",
    "files": "Raw/Files",
    "wiki": "Wiki",
    "schema": "Schema",
    "templates": "_templates",
    "agents": "AGENTS.md",
}


@dataclass(frozen=True)
class WikiProfileDefaults:
    name: str
    links: dict[str, str]
    profile_settings: dict[str, object]


_PROFILE_ALIASES = {
    "generic": "markdown",
}

_PROFILES: dict[str, WikiProfileDefaults] = {
    "markdown": WikiProfileDefaults(
        name="markdown",
        links={
            "style": "wikilink",
            "template": "[[{target}|{label}]]",
            "target": "path_no_ext",
            "label": "title_or_stem",
        },
        profile_settings={
            "create_dot_dir": False,
            "open_uri_template": None,
            "frontmatter": True,
            "nested_dirs": True,
            "flat_pages": False,
            "hub_filename": "index.md",
            "pages_dir": "Wiki",
            "namespace_separator": "___",
            "property_style": "yaml",
            "outliner_prefix": "- ",
            "indent": "\t",
            "journals_dir": None,
            "exclude": [],
        },
    ),
    "obsidian": WikiProfileDefaults(
        name="obsidian",
        links={
            "style": "wikilink",
            "template": "[[{target}|{label}]]",
            "target": "path_no_ext",
            "label": "title_or_stem",
        },
        profile_settings={
            "create_dot_dir": True,
            "open_uri_template": "obsidian://open?path={path}",
            "frontmatter": True,
            "nested_dirs": True,
            "flat_pages": False,
            "hub_filename": "_index.md",
            "pages_dir": "Wiki",
            "namespace_separator": "___",
            "property_style": "yaml",
            "outliner_prefix": "- ",
            "indent": "\t",
            "journals_dir": None,
            "exclude": [
                ".obsidian/workspace.json",
                ".obsidian/workspace-mobile.json",
                ".trash/",
            ],
        },
    ),
    "logseq": WikiProfileDefaults(
        name="logseq",
        links={
            "style": "wikilink",
            "template": "[[{target}|{label}]]",
            "target": "path_no_ext",
            "label": "title_or_stem",
        },
        profile_settings={
            "create_dot_dir": False,
            "open_uri_template": None,
            "frontmatter": False,
            "nested_dirs": False,
            "flat_pages": True,
            "hub_filename": "Wiki___Dashboard.md",
            "pages_dir": "pages",
            "namespace_separator": "___",
            "property_style": "logseq",
            "outliner_prefix": "- ",
            "indent": "\t",
            "journals_dir": "journals",
            "exclude": ["logseq/bak/", "logseq/.recycle/", ".logseq/"],
        },
    ),
}


def supported_profiles() -> tuple[str, ...]:
    return tuple(_PROFILES)


def canonical_profile_name(profile: str) -> str:
    value = profile.strip().lower()
    if not value:
        raise UsageError("wiki profile must not be empty")
    value = _PROFILE_ALIASES.get(value, value)
    if value not in _PROFILES:
        raise UsageError(f"unsupported wiki profile: {profile}")
    return value


def profile_defaults(profile: str) -> dict[str, object]:
    name = canonical_profile_name(profile)
    defaults = _PROFILES[name]
    return {
        "profile": name,
        "paths": dict(DEFAULT_PATHS),
        "links": dict(defaults.links),
        "profile_settings": dict(defaults.profile_settings),
    }


def canonical_tool_name(tool: str) -> str:
    return canonical_profile_name(tool)


def tool_profile_defaults(tool: str) -> dict[str, object]:
    defaults = profile_defaults(tool)
    return {
        "tool": defaults["profile"],
        "paths": dict(defaults["paths"]),
        "links": dict(defaults["links"]),
        "tool_config": dict(defaults["profile_settings"]),
        "profile": defaults["profile"],
        "profile_settings": dict(defaults["profile_settings"]),
    }
