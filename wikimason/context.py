from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import (
    WikiMasonConfig,
    default_config,
    default_env_config_path,
    env_config_path,
    find_local_config,
    find_wiki_root,
    load_config_file,
    resolve_existing_env_config_path,
)
from .errors import UsageError
from .vault_registry import VaultRegistry


@dataclass(frozen=True)
class WikiContext:
    root: Path
    config_path: Path | None
    env: str | None
    config: WikiMasonConfig
    resolution: str
    diagnostics: tuple[str, ...] = ()


def resolve_context(
    *,
    cwd: Path | None = None,
    env: str | None = None,
    config_path: str | Path | None = None,
    vault: str | Path | None = None,
) -> WikiContext:
    working_dir = (cwd or Path.cwd()).expanduser().resolve()

    if config_path is not None:
        resolved_path = Path(config_path).expanduser().resolve()
        config = load_config_file(resolved_path)
        return WikiContext(
            root=config.root,
            config_path=resolved_path,
            env=env,
            config=config,
            resolution="explicit_config",
        )

    local_path = find_local_config(working_dir)
    if local_path is not None:
        config = load_config_file(local_path)
        return WikiContext(
            root=config.root,
            config_path=local_path,
            env=env,
            config=config,
            resolution="local_config",
            diagnostics=(
                (
                    f"Using local {local_path.name}; --env {env} ignored because "
                    "local config has precedence."
                ),
            )
            if env is not None
            else (),
        )

    if env is not None:
        resolved_path = resolve_existing_env_config_path(env) or env_config_path(env)
        config = load_config_file(resolved_path)
        return WikiContext(
            root=config.root,
            config_path=resolved_path,
            env=env,
            config=config,
            resolution="explicit_env",
        )

    default_env_path = resolve_existing_env_config_path("default")
    if default_env_path is None and default_env_config_path().exists():
        default_env_path = default_env_config_path()
    if default_env_path is not None:
        config = load_config_file(default_env_path)
        return WikiContext(
            root=config.root,
            config_path=default_env_path,
            env="default",
            config=config,
            resolution="default_env",
        )

    if vault is not None:
        root = _resolve_existing_root(Path(vault))
        return _default_context(root)

    wiki_root = find_wiki_root(working_dir)
    if wiki_root is not None:
        return _default_context(wiki_root)

    legacy_root = _legacy_registry_root()
    if legacy_root is not None:
        return _default_context(legacy_root)

    raise UsageError(
        "could not resolve wiki context; pass --config PATH, "
        "--env NAME, --vault PATH, or run inside a wiki"
    )


def _default_context(root: Path) -> WikiContext:
    config = default_config("markdown", root)
    return WikiContext(
        root=config.root,
        config_path=None,
        env=None,
        config=config,
        resolution="built_in_defaults",
    )


def _resolve_existing_root(path: Path) -> Path:
    root = path.expanduser().resolve()
    if not root.exists():
        raise UsageError(f"vault path not found: {root}")
    return root


def _legacy_registry_root() -> Path | None:
    registry = VaultRegistry.default().load()
    last_used = registry.get("last_used")
    vaults = registry.get("vaults")
    if not isinstance(last_used, str) or not isinstance(vaults, dict):
        return None
    entry = vaults.get(last_used)
    if not isinstance(entry, dict):
        return None
    path_value = entry.get("path")
    if not isinstance(path_value, str):
        return None
    candidate = Path(path_value).expanduser().resolve()
    if not candidate.exists():
        return None
    return candidate
