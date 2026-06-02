from __future__ import annotations

from pathlib import Path

import pytest

from wikimason.config import default_config, load_config_file, write_config_file
from wikimason.errors import UsageError


def test_default_config_has_logging_defaults(tmp_path: Path) -> None:
    config = default_config("markdown", tmp_path / "vault")

    assert config.logging.enabled is True
    assert config.logging.path == "Wiki/log.md"
    assert config.logging.mode == "normal"
    assert config.logging.include_counts == "non_clean"
    assert config.logging.rotation.strategy == "size"
    assert config.logging.rotation.archive_dir == "Wiki/logs"


def test_write_config_file_includes_logging_section(tmp_path: Path) -> None:
    config = default_config("markdown", tmp_path / "vault")
    path = tmp_path / "wikimason.toml"

    write_config_file(path, config)
    text = path.read_text(encoding="utf-8")

    assert "[logging]" in text
    assert "[logging.rotation]" in text
    assert 'path = "Wiki/log.md"' in text
    assert 'archive_dir = "Wiki/logs"' in text


def test_load_config_file_overrides_logging_settings(tmp_path: Path) -> None:
    root = tmp_path / "wiki"
    root.mkdir()
    config_path = root / "wikimason.toml"
    config_path.write_text(
        """config_version = 1

[wiki]
root = "."
profile = "markdown"

[logging]
enabled = false
path = "Wiki/ops.md"
mode = "quiet"
min_level = "warning"
include_audit_success = true
include_metadata = true
include_counts = "always"
max_summary_chars = 42
include_commands = ["source.*"]
exclude_commands = ["source.coverage"]

[logging.rotation]
enabled = true
strategy = "size"
max_bytes = 8192
max_files = 2
archive_dir = "Wiki/archive-logs"
""",
        encoding="utf-8",
    )

    loaded = load_config_file(config_path)

    assert loaded.logging.enabled is False
    assert loaded.logging.path == "Wiki/ops.md"
    assert loaded.logging.mode == "quiet"
    assert loaded.logging.min_level == "warning"
    assert loaded.logging.include_audit_success is True
    assert loaded.logging.include_metadata is True
    assert loaded.logging.include_counts == "always"
    assert loaded.logging.max_summary_chars == 42
    assert loaded.logging.include_commands == ("source.*",)
    assert loaded.logging.exclude_commands == ("source.coverage",)
    assert loaded.logging.rotation.max_bytes == 8192
    assert loaded.logging.rotation.max_files == 2
    assert loaded.logging.rotation.archive_dir == "Wiki/archive-logs"


def test_invalid_logging_mode_rejected(tmp_path: Path) -> None:
    root = tmp_path / "wiki"
    root.mkdir()
    config_path = root / "wikimason.toml"
    config_path.write_text(
        """config_version = 1

[wiki]
root = "."
profile = "markdown"

[logging]
mode = "verbose"
""",
        encoding="utf-8",
    )

    with pytest.raises(UsageError):
        load_config_file(config_path)


def test_invalid_rotation_values_rejected(tmp_path: Path) -> None:
    root = tmp_path / "wiki"
    root.mkdir()
    config_path = root / "wikimason.toml"
    config_path.write_text(
        """config_version = 1

[wiki]
root = "."
profile = "markdown"

[logging.rotation]
max_bytes = 128
max_files = -1
""",
        encoding="utf-8",
    )

    with pytest.raises(UsageError):
        load_config_file(config_path)


def test_logging_path_cannot_escape_vault(tmp_path: Path) -> None:
    root = tmp_path / "wiki"
    root.mkdir()
    config_path = root / "wikimason.toml"
    config_path.write_text(
        """config_version = 1

[wiki]
root = "."
profile = "markdown"

[logging]
path = "../outside.md"
""",
        encoding="utf-8",
    )

    with pytest.raises(UsageError):
        load_config_file(config_path)
