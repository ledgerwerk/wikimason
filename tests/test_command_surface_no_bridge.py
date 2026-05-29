import re


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


from pathlib import Path

from wikimason.cli import main
from wikimason.config import load_config_file


def test_help_has_no_obsidian_or_bridge_surface(capsys) -> None:
    assert main(["--help"]) == 0
    out = _strip_ansi(capsys.readouterr().out)
    assert "wikimason obsidian" not in out
    assert "wikimason bridge" not in out
    assert "page" in out
    assert "status" in out
    # file is a sub-group, shown as a command in Typer help
    # but not as 'wikimason file list'


def test_vault_init_obsidian_profile_still_writes_obsidian_defaults(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"

    assert main(["vault", "init", str(vault), "--tool", "obsidian"]) == 0

    config = load_config_file(vault / "wikimason.toml")
    assert config.profile == "obsidian"
    assert (vault / ".obsidian").exists()
