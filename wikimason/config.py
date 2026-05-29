from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib

from .constants import (
    CORE_VAULT_DIRS,
    DEFAULT_PROFILE,
    DEFAULT_TOOL_PROFILE,
    GLOBAL_CONFIG_DIRNAME,
    LEGACY_GLOBAL_ENV_DIRNAME,
    LOCAL_CONFIG_NAMES,
)
from .errors import UsageError
from .profiles import profile_defaults


@dataclass(frozen=True)
class PathConfig:
    raw: str
    sources: str
    files: str
    wiki: str
    schema: str
    templates: str
    agents: str

    def as_dict(self) -> dict[str, str]:
        return {
            "raw": self.raw,
            "sources": self.sources,
            "files": self.files,
            "wiki": self.wiki,
            "schema": self.schema,
            "templates": self.templates,
            "agents": self.agents,
        }


@dataclass(frozen=True)
class LinkConfig:
    style: str
    template: str
    target: str
    label: str

    def as_dict(self) -> dict[str, str]:
        return {
            "style": self.style,
            "template": self.template,
            "target": self.target,
            "label": self.label,
        }


@dataclass(frozen=True)
class ProfileConfig:
    create_dot_dir: bool
    open_uri_template: str | None
    frontmatter: bool
    nested_dirs: bool
    flat_pages: bool
    hub_filename: str
    pages_dir: str
    namespace_separator: str
    property_style: str
    outliner_prefix: str
    indent: str
    journals_dir: str | None
    exclude: tuple[str, ...]

    def as_dict(self) -> dict[str, bool | str | list[str] | None]:
        return {
            "create_dot_dir": self.create_dot_dir,
            "open_uri_template": self.open_uri_template,
            "frontmatter": self.frontmatter,
            "nested_dirs": self.nested_dirs,
            "flat_pages": self.flat_pages,
            "hub_filename": self.hub_filename,
            "pages_dir": self.pages_dir,
            "namespace_separator": self.namespace_separator,
            "property_style": self.property_style,
            "outliner_prefix": self.outliner_prefix,
            "indent": self.indent,
            "journals_dir": self.journals_dir,
            "exclude": list(self.exclude),
        }


@dataclass(frozen=True)
class WikiMasonConfig:
    config_version: int
    name: str | None
    root: Path
    source_path: Path | None
    profile: str
    paths: PathConfig
    links: LinkConfig
    profile_config: ProfileConfig

    @property
    def tool(self) -> str:
        return self.profile

    @property
    def tool_config(self) -> ProfileConfig:
        return self.profile_config


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def global_config_dir() -> Path:
    return Path.home() / GLOBAL_CONFIG_DIRNAME


def legacy_global_env_dir() -> Path:
    return Path.home() / LEGACY_GLOBAL_ENV_DIRNAME


def default_env_config_path() -> Path:
    return global_config_dir() / "default.toml"


def env_config_path(name: str) -> Path:
    env_name = name.strip()
    if not env_name:
        raise UsageError("env name must not be empty")
    return global_config_dir() / f"{env_name}.toml"


def resolve_existing_env_config_path(name: str) -> Path | None:
    candidates = [env_config_path(name), legacy_global_env_dir() / f"{name}.toml"]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def find_local_config(start: Path) -> Path | None:
    current = start.expanduser().resolve()
    if current.is_file():
        current = current.parent
    for candidate_dir in (current, *current.parents):
        for name in LOCAL_CONFIG_NAMES:
            candidate = candidate_dir / name
            if candidate.exists():
                return candidate
    return None


def looks_like_wiki_root(path: Path) -> bool:
    candidate = path.expanduser().resolve()
    return (
        any((candidate / name).exists() for name in LOCAL_CONFIG_NAMES)
        or (candidate / ".obsidian").exists()
        or any((candidate / name).exists() for name in CORE_VAULT_DIRS)
        or (candidate / "AGENTS.md").exists()
    )


def find_wiki_root(start: Path) -> Path | None:
    current = start.expanduser().resolve()
    if current.is_file():
        current = current.parent
    for candidate_dir in (current, *current.parents):
        if looks_like_wiki_root(candidate_dir):
            return candidate_dir
    return None


def default_config(
    profile: str, root: Path, *, name: str | None = None
) -> WikiMasonConfig:
    resolved_root = root.expanduser().resolve()
    defaults = profile_defaults(profile)
    return WikiMasonConfig(
        config_version=1,
        name=name if name is not None else resolved_root.name,
        root=resolved_root,
        source_path=None,
        profile=str(defaults["profile"]),
        paths=PathConfig(
            **_string_table(defaults["paths"], table_name="paths defaults")
        ),
        links=LinkConfig(
            **_string_table(defaults["links"], table_name="links defaults")
        ),
        profile_config=ProfileConfig(
            **_profile_table(
                defaults["profile_settings"], table_name="profile defaults"
            )
        ),
    )


def load_runtime_config(root: Path) -> WikiMasonConfig:
    local_path = find_local_config(root)
    if local_path is not None:
        config = load_config_file(local_path)
        try:
            root.resolve().relative_to(config.root)
        except ValueError:
            return default_config(DEFAULT_PROFILE, root)
        return config
    return default_config(DEFAULT_PROFILE, root)


def load_config_data(path: Path) -> dict[str, object]:
    config_path = path.expanduser().resolve()
    if not config_path.exists():
        raise UsageError(f"config path not found: {config_path}")
    try:
        raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise UsageError(f"invalid config TOML: {exc}") from exc
    if not isinstance(raw, dict):
        raise UsageError("invalid config: expected a TOML table")
    return raw


def load_config_file(path: Path) -> WikiMasonConfig:
    config_path = path.expanduser().resolve()
    raw = load_config_data(config_path)
    wiki_table = _optional_table(raw.get("wiki"), table_name="wiki")
    profile_value = _profile_name(raw, wiki_table)
    name_value = _config_name(raw, wiki_table)
    root = _resolve_config_root(config_path, _config_root_value(raw, wiki_table))
    base = default_config(profile_value, root, name=name_value)
    config_version = _config_version(
        raw.get("config_version", wiki_table.get("config_version", base.config_version))
        if wiki_table is not None
        else raw.get("config_version", base.config_version)
    )

    path_values = base.paths.as_dict()
    path_values.update(_string_table(raw.get("paths", {}), table_name="paths"))

    link_values = base.links.as_dict()
    link_values.update(_string_table(raw.get("links", {}), table_name="links"))

    profile_values = base.profile_config.as_dict()
    profile_values.update(_load_profile_overrides(raw, base.profile))

    return WikiMasonConfig(
        config_version=config_version,
        name=name_value if name_value is not None else base.name,
        root=root,
        source_path=config_path,
        profile=base.profile,
        paths=PathConfig(**path_values),
        links=LinkConfig(**link_values),
        profile_config=ProfileConfig(
            **_profile_table(profile_values, table_name="profile settings")
        ),
    )


def write_config_file(
    path: Path,
    config: WikiMasonConfig,
    *,
    root_value: str | None = None,
) -> None:
    target = path.expanduser().resolve()
    resolved_root_value = root_value if root_value is not None else str(config.root)
    lines = [
        f"config_version = {config.config_version}",
        "",
        "[wiki]",
        f"name = {_toml_string(config.name or config.root.name)}",
        f"root = {_toml_string(resolved_root_value)}",
        f"profile = {_toml_string(config.profile)}",
        "",
        "[paths]",
    ]
    for key, value in config.paths.as_dict().items():
        lines.append(f"{key} = {_toml_string(value)}")
    lines.extend(
        [
            "",
            "[links]",
        ]
    )
    for key, value in config.links.as_dict().items():
        lines.append(f"{key} = {_toml_string(value)}")
    lines.extend(
        [
            "",
            f"[profile.{config.profile}]",
        ]
    )
    for key, value in config.profile_config.as_dict().items():
        if value is None:
            continue
        lines.append(f"{key} = {_toml_value(value)}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _resolve_config_root(config_path: Path, value: object) -> Path:
    if not isinstance(value, str):
        raise UsageError("invalid config: root must be a string")
    root = Path(value).expanduser()
    if not root.is_absolute():
        root = (config_path.parent / root).resolve()
    else:
        root = root.resolve()
    return root


def _optional_string(raw: dict[str, object], key: str) -> str | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise UsageError(f"invalid config: {key} must be a string")
    return value


def _optional_table(raw: object, *, table_name: str) -> dict[str, object] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise UsageError(f"invalid config: {table_name} must be a table")
    return raw


def _config_name(
    raw: dict[str, object], wiki_table: dict[str, object] | None
) -> str | None:
    if wiki_table is not None and "name" in wiki_table:
        return _string_value(wiki_table, "name", table_name="wiki")
    if "name" in raw:
        return _optional_string(raw, "name")
    return None


def _config_root_value(
    raw: dict[str, object], wiki_table: dict[str, object] | None
) -> object:
    if wiki_table is not None and "root" in wiki_table:
        return wiki_table["root"]
    return raw.get("root", ".")


def _profile_name(raw: dict[str, object], wiki_table: dict[str, object] | None) -> str:
    if wiki_table is not None and "profile" in wiki_table:
        return _canonical_profile(
            _string_value(wiki_table, "profile", table_name="wiki")
        )
    top_level_profile = raw.get("profile")
    if isinstance(top_level_profile, str):
        return _canonical_profile(top_level_profile)
    tool_value = raw.get("tool", DEFAULT_TOOL_PROFILE)
    if not isinstance(tool_value, str):
        raise UsageError("invalid config: tool must be a string")
    return _canonical_profile(tool_value)


def _canonical_profile(value: str) -> str:
    from .profiles import canonical_profile_name

    return canonical_profile_name(value)


def _string_value(raw: dict[str, object], key: str, *, table_name: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str):
        raise UsageError(f"invalid config: {table_name}.{key} must be a string")
    return value


def _config_version(value: object) -> int:
    if not isinstance(value, int):
        raise UsageError("invalid config: config_version must be an integer")
    if value < 1:
        raise UsageError("invalid config: config_version must be >= 1")
    return value


def _string_table(raw: object, *, table_name: str) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise UsageError(f"invalid config: {table_name} must be a table")
    values: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise UsageError(f"invalid config: {table_name} values must be strings")
        values[key] = value
    return values


def _profile_table(
    raw: object, *, table_name: str
) -> dict[str, bool | str | tuple[str, ...] | None]:
    if not isinstance(raw, dict):
        raise UsageError(f"invalid config: {table_name} must be a table")
    values: dict[str, bool | str | tuple[str, ...] | None] = {}
    for key, value in raw.items():
        if key in {"create_dot_dir", "frontmatter", "nested_dirs", "flat_pages"}:
            if not isinstance(value, bool):
                raise UsageError(f"invalid config: {table_name}.{key} must be boolean")
            values[key] = value
            continue
        if key in {
            "open_uri_template",
            "hub_filename",
            "pages_dir",
            "namespace_separator",
            "property_style",
            "outliner_prefix",
            "indent",
            "journals_dir",
        }:
            if value is not None and not isinstance(value, str):
                raise UsageError(f"invalid config: {table_name}.{key} must be a string")
            values[key] = value
            continue
        if key == "exclude":
            if not isinstance(value, (list, tuple)) or not all(
                isinstance(item, str) for item in value
            ):
                raise UsageError(
                    f"invalid config: {table_name}.exclude must be a string array"
                )
            values[key] = tuple(value)
            continue
        raise UsageError(f"invalid config: unsupported profile setting {key}")
    return values


def _load_profile_overrides(
    raw: dict[str, object], profile: str
) -> dict[str, bool | str | tuple[str, ...] | None]:
    profile_settings = raw.get("profile")
    if isinstance(profile_settings, dict) and profile in profile_settings:
        overrides = profile_settings[profile]
        return _profile_table(overrides, table_name=f"profile.{profile}")
    tool_settings = raw.get("tool_settings")
    if tool_settings is None:
        return {}
    if not isinstance(tool_settings, dict):
        raise UsageError("invalid config: tool_settings must be a table")
    if profile not in tool_settings:
        return {}
    overrides = tool_settings[profile]
    return _profile_table(overrides, table_name=f"tool_settings.{profile}")


def _toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _toml_bool(value: bool) -> str:
    return "true" if value else "false"


def _toml_string_array(values: list[str] | tuple[str, ...]) -> str:
    return "[" + ", ".join(_toml_string(value) for value in values) + "]"


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return _toml_bool(value)
    if isinstance(value, str):
        return _toml_string(value)
    if isinstance(value, (list, tuple)) and all(
        isinstance(item, str) for item in value
    ):
        return _toml_string_array(list(value))
    raise UsageError(f"unsupported TOML value: {value!r}")
