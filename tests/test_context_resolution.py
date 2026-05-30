from __future__ import annotations

import json
from pathlib import Path

from wikimason.config import (
    default_config,
    default_env_config_path,
    load_config_file,
    write_config_file,
)
from wikimason.context import resolve_context
from wikimason.paths import is_vault, resolve_vault


def test_load_config_file_resolves_relative_root_and_logseq_profile(
    tmp_path: Path,
) -> None:
    root = tmp_path / "wiki"
    root.mkdir()
    config_path = root / "wikimason.toml"
    config_path.write_text(
        """config_version = 1

[wiki]
name = "local"
root = "."
profile = "logseq"

[profile.logseq]
pages_dir = "pages"
""",
        encoding="utf-8",
    )

    config = load_config_file(config_path)

    assert config.root == root.resolve()
    assert config.profile == "logseq"
    assert config.links.style == "wikilink"
    assert config.profile_config.pages_dir == "pages"
    assert config.profile_config.frontmatter is False


def test_resolve_context_uses_parent_local_config_from_nested_dir(
    tmp_path: Path,
) -> None:
    root = tmp_path / "wiki"
    nested = root / "Wiki/Topics"
    nested.mkdir(parents=True)
    (root / "wikimason.toml").write_text(
        """config_version = 1

[wiki]
root = "."
profile = "markdown"
""",
        encoding="utf-8",
    )

    context = resolve_context(cwd=nested)

    assert context.root == root.resolve()
    assert context.config.profile == "markdown"
    assert context.config_path == (root / "wikimason.toml").resolve()
    assert is_vault(nested) is True
    assert resolve_vault(None, cwd=nested) == root.resolve()


def test_resolve_context_prefers_explicit_config_over_env_and_local(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    local_root = tmp_path / "local"
    local_root.mkdir()
    (local_root / "wikimason.toml").write_text(
        """config_version = 1

[wiki]
root = "."
profile = "markdown"
""",
        encoding="utf-8",
    )

    env_root = tmp_path / "env-root"
    env_root.mkdir()
    env_dir = tmp_path / ".config/wikimason"
    env_dir.mkdir(parents=True)
    (env_dir / "named.toml").write_text(
        f"""config_version = 1

[wiki]
root = {json.dumps(str(env_root))}
profile = "obsidian"
""",
        encoding="utf-8",
    )

    explicit_root = tmp_path / "explicit"
    explicit_root.mkdir()
    explicit_config = tmp_path / "explicit.toml"
    explicit_config.write_text(
        f"""config_version = 1

[wiki]
root = {json.dumps(str(explicit_root))}
profile = "markdown"
""",
        encoding="utf-8",
    )

    context = resolve_context(cwd=local_root, env="named", config_path=explicit_config)

    assert context.root == explicit_root.resolve()
    assert context.config.profile == "markdown"
    assert context.config_path == explicit_config.resolve()


def test_resolve_context_uses_local_before_env_and_emits_diagnostic(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    local_root = tmp_path / "local"
    local_root.mkdir()
    (local_root / "wikimason.toml").write_text(
        """config_version = 1

[wiki]
root = "."
profile = "markdown"
""",
        encoding="utf-8",
    )

    env_root = tmp_path / "env-root"
    env_root.mkdir()
    env_dir = tmp_path / ".config/wikimason"
    env_dir.mkdir(parents=True)
    (env_dir / "named.toml").write_text(
        f"""config_version = 1

[wiki]
root = {json.dumps(str(env_root))}
profile = "obsidian"
""",
        encoding="utf-8",
    )

    context = resolve_context(cwd=local_root, env="named")

    assert context.root == local_root.resolve()
    assert context.config.profile == "markdown"
    assert context.env == "named"
    assert context.diagnostics == (
        "Using local wikimason.toml; --env named ignored because local config has precedence.",  # noqa: E501
    )


def test_resolve_context_uses_default_env_before_built_in_defaults(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    env_root = tmp_path / "env-root"
    env_root.mkdir()
    default_path = default_env_config_path()
    default_path.parent.mkdir(parents=True, exist_ok=True)
    default_path.write_text(
        f"""config_version = 1

[wiki]
root = {json.dumps(str(env_root))}
profile = "logseq"
""",
        encoding="utf-8",
    )

    context = resolve_context(cwd=tmp_path / "nowhere")

    assert context.root == env_root.resolve()
    assert context.config.profile == "logseq"
    assert context.resolution == "default_env"


def test_default_env_config_path_honors_home_for_ci_sandbox(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    assert default_env_config_path() == (tmp_path / ".config/wikimason/default.toml")


def test_resolve_context_prefers_explicit_vault_over_default_env(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    env_root = tmp_path / "env-root"
    env_root.mkdir()
    vault_root = tmp_path / "vault"
    vault_root.mkdir()
    default_path = default_env_config_path()
    default_path.parent.mkdir(parents=True, exist_ok=True)
    default_path.write_text(
        f"""config_version = 1

[wiki]
root = {json.dumps(str(env_root))}
profile = "logseq"
""",
        encoding="utf-8",
    )

    context = resolve_context(cwd=tmp_path / "nowhere", vault=vault_root)

    assert context.root == vault_root.resolve()
    assert context.resolution == "built_in_defaults"


def test_write_config_file_round_trips(tmp_path: Path) -> None:
    root = tmp_path / "wiki"
    root.mkdir()
    config = default_config("markdown", root, name="roundtrip")
    config_path = tmp_path / "wikimason.toml"

    write_config_file(config_path, config)
    loaded = load_config_file(config_path)

    assert loaded.root == root.resolve()
    assert loaded.profile == "markdown"
    assert loaded.name == "roundtrip"
