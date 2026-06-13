from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib

from ledgercore.paths import find_config_upwards

from .constants import (
    CORE_VAULT_DIRS,
    DEFAULT_PROFILE,
    DEFAULT_TOOL_PROFILE,
    GLOBAL_CONFIG_DIRNAME,
    LOCAL_CONFIG_NAMES,
)
from .errors import UsageError
from .profiles import profile_defaults
from .toml_tools import toml_string, toml_value


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
class LogRotationConfig:
    enabled: bool
    strategy: str
    max_bytes: int
    max_files: int
    archive_dir: str

    def as_dict(self) -> dict[str, bool | int | str]:
        return {
            "enabled": self.enabled,
            "strategy": self.strategy,
            "max_bytes": self.max_bytes,
            "max_files": self.max_files,
            "archive_dir": self.archive_dir,
        }


@dataclass(frozen=True)
class LoggingConfig:
    enabled: bool
    path: str
    mode: str
    min_level: str
    include_audit_success: bool
    include_metadata: bool
    include_counts: str
    max_summary_chars: int
    include_commands: tuple[str, ...]
    exclude_commands: tuple[str, ...]
    rotation: LogRotationConfig

    def as_dict(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "path": self.path,
            "mode": self.mode,
            "min_level": self.min_level,
            "include_audit_success": self.include_audit_success,
            "include_metadata": self.include_metadata,
            "include_counts": self.include_counts,
            "max_summary_chars": self.max_summary_chars,
            "include_commands": list(self.include_commands),
            "exclude_commands": list(self.exclude_commands),
            "rotation": self.rotation.as_dict(),
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
    logging: LoggingConfig

    @property
    def tool(self) -> str:
        return self.profile

    @property
    def tool_config(self) -> ProfileConfig:
        return self.profile_config


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def user_home() -> Path:
    """Return the home directory used for WikiMason config discovery.

    ``Path.home()`` ignores ``HOME`` on Windows, which makes tests and CI leak
    state into the real runner profile.  Honor ``HOME`` first so callers can
    sandbox config discovery portably, then fall back to the platform home.
    """
    home = os.environ.get("HOME")
    if home:
        return Path(home).expanduser()
    return Path.home()


def global_config_dir() -> Path:
    return user_home() / GLOBAL_CONFIG_DIRNAME


def default_env_config_path() -> Path:
    return global_config_dir() / "default.toml"


def env_config_path(name: str) -> Path:
    env_name = name.strip()
    if not env_name:
        raise UsageError("env name must not be empty")
    return global_config_dir() / f"{env_name}.toml"


def resolve_existing_env_config_path(name: str) -> Path | None:
    candidate = env_config_path(name)
    if candidate.exists():
        return candidate
    return None


def find_local_config(start: Path) -> Path | None:
    # Delegated to ledgercore, which walks upward from start.resolve().
    # Behavior matches the previous hand-written walk (first matching file
    # in the nearest enclosing directory).
    return find_config_upwards(start, tuple(LOCAL_CONFIG_NAMES))


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
            **cast(
                dict[str, Any],
                _profile_table(
                    defaults["profile_settings"], table_name="profile defaults"
                ),
            )
        ),
        logging=LoggingConfig(
            enabled=True,
            path="Wiki/log.md",
            mode="normal",
            min_level="info",
            include_audit_success=False,
            include_metadata=False,
            include_counts="non_clean",
            max_summary_chars=160,
            include_commands=(),
            exclude_commands=(
                "doctor",
                "vault.doctor",
                "links.check",
                "source.coverage",
                "ingest.plan",
            ),
            rotation=LogRotationConfig(
                enabled=True,
                strategy="size",
                max_bytes=1_048_576,
                max_files=5,
                archive_dir="Wiki/logs",
            ),
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


def load_config_data(path: Path) -> dict[str, Any]:
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

    profile_values: dict[str, Any] = base.profile_config.as_dict()
    profile_values.update(
        cast(dict[str, Any], _load_profile_overrides(raw, base.profile))
    )  # noqa: E501
    logging_values = base.logging.as_dict()
    logging_overrides = _logging_table(raw.get("logging", {}), table_name="logging")
    rotation_overrides = _rotation_table(
        logging_overrides.pop("rotation", {}), table_name="logging.rotation"
    )
    logging_values.update(logging_overrides)
    rotation_values = base.logging.rotation.as_dict()
    rotation_values.update(rotation_overrides)
    logging_values["rotation"] = rotation_values

    return WikiMasonConfig(
        config_version=config_version,
        name=name_value if name_value is not None else base.name,
        root=root,
        source_path=config_path,
        profile=base.profile,
        paths=PathConfig(**path_values),
        links=LinkConfig(**link_values),
        profile_config=ProfileConfig(
            **cast(
                dict[str, Any],
                _profile_table(profile_values, table_name="profile settings"),
            )  # noqa: E501
        ),
        logging=LoggingConfig(**cast(dict[str, Any], _logging_values(logging_values))),
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
        f"name = {toml_string(config.name or config.root.name)}",
        f"root = {toml_string(resolved_root_value)}",
        f"profile = {toml_string(config.profile)}",
        "",
        "[paths]",
    ]
    for key, value in config.paths.as_dict().items():
        lines.append(f"{key} = {toml_string(value)}")
    lines.extend(
        [
            "",
            "[links]",
        ]
    )
    for key, value in config.links.as_dict().items():
        lines.append(f"{key} = {toml_string(value)}")
    lines.extend(
        [
            "",
            f"[profile.{config.profile}]",
        ]
    )
    for key, p_value in config.profile_config.as_dict().items():
        if p_value is None:
            continue
        lines.append(f"{key} = {_toml_value(p_value)}")
    lines.extend(
        [
            "",
            "[logging]",
        ]
    )
    for key, value in config.logging.as_dict().items():
        if key == "rotation":
            continue
        lines.append(f"{key} = {_toml_config_value(value)}")
    lines.extend(
        [
            "",
            "[logging.rotation]",
        ]
    )
    for key, value in config.logging.rotation.as_dict().items():
        lines.append(f"{key} = {_toml_config_value(value)}")
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


def _optional_string(raw: dict[str, Any], key: str) -> str | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise UsageError(f"invalid config: {key} must be a string")
    return value


def _optional_table(raw: object, *, table_name: str) -> dict[str, Any] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise UsageError(f"invalid config: {table_name} must be a table")
    return raw


def _config_name(raw: dict[str, Any], wiki_table: dict[str, Any] | None) -> str | None:
    if wiki_table is not None and "name" in wiki_table:
        return _string_value(wiki_table, "name", table_name="wiki")
    if "name" in raw:
        return _optional_string(raw, "name")
    return None


def _config_root_value(
    raw: dict[str, Any], wiki_table: dict[str, Any] | None
) -> object:
    if wiki_table is not None and "root" in wiki_table:
        return wiki_table["root"]
    return raw.get("root", ".")


def _profile_name(raw: dict[str, Any], wiki_table: dict[str, Any] | None) -> str:
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


def _string_value(raw: dict[str, Any], key: str, *, table_name: str) -> str:
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
    raw: dict[str, Any], profile: str
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


def _logging_table(raw: object, *, table_name: str) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise UsageError(f"invalid config: {table_name} must be a table")
    values: dict[str, object] = {}
    allowed = {
        "enabled",
        "path",
        "mode",
        "min_level",
        "include_audit_success",
        "include_metadata",
        "include_counts",
        "max_summary_chars",
        "include_commands",
        "exclude_commands",
        "rotation",
    }
    for key, value in raw.items():
        if key not in allowed:
            raise UsageError(f"invalid config: unsupported {table_name} setting {key}")
        if key in {"enabled", "include_audit_success", "include_metadata"}:
            if not isinstance(value, bool):
                raise UsageError(f"invalid config: {table_name}.{key} must be boolean")
            values[key] = value
            continue
        if key in {"path", "mode", "min_level", "include_counts"}:
            if not isinstance(value, str):
                raise UsageError(f"invalid config: {table_name}.{key} must be a string")
            values[key] = value
            continue
        if key == "max_summary_chars":
            if not isinstance(value, int):
                raise UsageError(
                    f"invalid config: {table_name}.{key} must be an integer"
                )
            values[key] = value
            continue
        if key in {"include_commands", "exclude_commands"}:
            if not isinstance(value, (list, tuple)) or not all(
                isinstance(item, str) for item in value
            ):
                raise UsageError(
                    f"invalid config: {table_name}.{key} must be a string array"
                )
            values[key] = tuple(value)
            continue
        if key == "rotation":
            if not isinstance(value, dict):
                raise UsageError(
                    f"invalid config: {table_name}.rotation must be a table"
                )
            values[key] = value
            continue
    return values


def _rotation_table(raw: object, *, table_name: str) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise UsageError(f"invalid config: {table_name} must be a table")
    values: dict[str, object] = {}
    allowed = {"enabled", "strategy", "max_bytes", "max_files", "archive_dir"}
    for key, value in raw.items():
        if key not in allowed:
            raise UsageError(f"invalid config: unsupported {table_name} setting {key}")
        if key == "enabled":
            if not isinstance(value, bool):
                raise UsageError(
                    f"invalid config: {table_name}.enabled must be boolean"
                )
            values[key] = value
            continue
        if key in {"strategy", "archive_dir"}:
            if not isinstance(value, str):
                raise UsageError(f"invalid config: {table_name}.{key} must be a string")
            values[key] = value
            continue
        if key in {"max_bytes", "max_files"}:
            if not isinstance(value, int):
                raise UsageError(
                    f"invalid config: {table_name}.{key} must be an integer"
                )
            values[key] = value
            continue
    return values


def _relative_vault_path(value: str, *, key: str) -> str:
    path = Path(value)
    if path.is_absolute():
        raise UsageError(f"invalid config: {key} must be a relative vault path")
    normalized = Path(value.replace("\\", "/"))
    if any(part == ".." for part in normalized.parts):
        raise UsageError(f"invalid config: {key} must stay inside the vault")
    return normalized.as_posix()


def _logging_values(raw: dict[str, object]) -> dict[str, object]:
    mode = str(raw.get("mode", "normal"))
    if mode not in {"quiet", "normal", "diagnostic"}:
        raise UsageError(
            "invalid config: logging.mode must be one of quiet|normal|diagnostic"
        )
    min_level = str(raw.get("min_level", "info"))
    if min_level not in {"info", "warning", "error"}:
        raise UsageError(
            "invalid config: logging.min_level must be one of info|warning|error"
        )
    include_counts = str(raw.get("include_counts", "non_clean"))
    if include_counts not in {"never", "non_clean", "always"}:
        raise UsageError(
            "invalid config: logging.include_counts must be one of "
            "never|non_clean|always"
        )
    max_summary_chars = int(raw.get("max_summary_chars", 160))
    if max_summary_chars < 1:
        raise UsageError("invalid config: logging.max_summary_chars must be >= 1")
    include_commands = tuple(raw.get("include_commands", ()))
    exclude_commands = tuple(raw.get("exclude_commands", ()))
    rotation_table = raw.get("rotation", {})
    if not isinstance(rotation_table, dict):
        raise UsageError("invalid config: logging.rotation must be a table")
    strategy = str(rotation_table.get("strategy", "size"))
    if strategy not in {"none", "size"}:
        raise UsageError("invalid config: logging.rotation.strategy must be none|size")
    max_bytes = int(rotation_table.get("max_bytes", 1_048_576))
    if max_bytes < 4096:
        raise UsageError("invalid config: logging.rotation.max_bytes must be >= 4096")
    max_files = int(rotation_table.get("max_files", 5))
    if max_files < 0:
        raise UsageError("invalid config: logging.rotation.max_files must be >= 0")
    return {
        "enabled": bool(raw.get("enabled", True)),
        "path": _relative_vault_path(
            str(raw.get("path", "Wiki/log.md")), key="logging.path"
        ),
        "mode": mode,
        "min_level": min_level,
        "include_audit_success": bool(raw.get("include_audit_success", False)),
        "include_metadata": bool(raw.get("include_metadata", False)),
        "include_counts": include_counts,
        "max_summary_chars": max_summary_chars,
        "include_commands": include_commands,
        "exclude_commands": exclude_commands,
        "rotation": LogRotationConfig(
            enabled=bool(rotation_table.get("enabled", True)),
            strategy=strategy,
            max_bytes=max_bytes,
            max_files=max_files,
            archive_dir=_relative_vault_path(
                str(rotation_table.get("archive_dir", "Wiki/logs")),
                key="logging.rotation.archive_dir",
            ),
        ),
    }


def _toml_value(value: Any) -> str:
    try:
        return toml_value(value)
    except ValueError as exc:
        raise UsageError(str(exc)) from exc


def _toml_config_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(value)
    return _toml_value(value)
