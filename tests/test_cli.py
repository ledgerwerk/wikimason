import json
import re
from pathlib import Path

from wikimason.cli import main
from wikimason.commands import render_command_reference_markdown
from wikimason.config import load_config_file
from wikimason.scaffold import init_vault
from wikimason.schema import load_vault_schema, write_default_schema


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def test_cli_help(capsys):
    assert main(["--help"]) == 0
    out = _strip_ansi(capsys.readouterr().out)
    assert "--config" in out
    assert "config" in out
    assert "init" in out
    assert "page" in out
    assert "source" in out
    assert "index" in out
    assert "agents" in out
    assert "bridge" not in out
    assert "obsidian" not in out
    # file is a sub-group, should not appear at root help
    # (Typer shows subgroups as commands)


def test_cli_help_topic(capsys):
    assert main(["help", "source", "scan"]) == 0
    out = _strip_ansi(capsys.readouterr().out)
    assert "scan" in out


def test_cli_doctor_build_lint(tmp_path: Path):
    vault = tmp_path / "vault"
    init_vault(vault, demo=True)
    assert main(["doctor", "--vault", str(vault)]) in {0, 1}
    assert main(["build", "--vault", str(vault)]) == 0
    assert main(["lint", "--vault", str(vault)]) == 0


def test_cli_global_context_options_precede_command(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=False, tool="markdown")

    assert main(["--config", str(vault / "wikimason.toml"), "build"]) == 0
    assert main(["--vault", str(vault), "vault", "doctor"]) in {0, 1}


def test_cli_init_demo_writes_operational_artifacts(tmp_path: Path) -> None:
    vault = tmp_path / "vault"

    assert main(["init", str(vault), "--demo"]) == 0

    assert (vault / "Wiki/catalog.jsonl").read_text(encoding="utf-8").strip()
    assert (vault / "Schema/source-manifest.jsonl").read_text(encoding="utf-8").strip()
    assert (vault / "Wiki/log.md").exists()


def test_cli_init_profile_subcommand_writes_markdown_config(tmp_path: Path) -> None:
    vault = tmp_path / "vault"

    assert main(["init", "markdown", str(vault)]) == 0

    config = load_config_file(vault / "wikimason.toml")
    assert config.profile == "markdown"
    assert not (vault / ".obsidian").exists()


def test_cli_init_profile_subcommand_writes_logseq_config(tmp_path: Path) -> None:
    vault = tmp_path / "vault"

    assert main(["init", "logseq", str(vault)]) == 0

    config = load_config_file(vault / "wikimason.toml")
    assert config.profile == "logseq"
    assert not (vault / ".obsidian").exists()


def test_cli_config_show_reports_local_precedence_over_env(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    vault = tmp_path / "vault"
    init_vault(vault, profile="markdown")
    monkeypatch.chdir(vault)

    env_root = tmp_path / "env-root"
    env_root.mkdir()
    config_dir = tmp_path / ".config/wikimason"
    config_dir.mkdir(parents=True)
    (config_dir / "named.toml").write_text(
        f"""config_version = 1

[wiki]
root = {json.dumps(str(env_root))}
profile = "obsidian"
""",
        encoding="utf-8",
    )

    assert main(["--env", "named", "config", "show", "--format", "json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["root"] == str(vault.resolve())
    assert payload["profile"] == "markdown"
    assert payload["resolution"] == "local_config"
    assert payload["diagnostics"] == [
        "Using local wikimason.toml; --env named ignored because local config has precedence."  # noqa: E501
    ]


def test_cli_config_validate_accepts_explicit_config(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, profile="logseq")

    assert main(["--config", str(vault / "wikimason.toml"), "config", "validate"]) == 0


def test_cli_config_migrate_restores_toml_from_legacy_root(tmp_path: Path) -> None:
    vault = tmp_path / "legacy"
    init_vault(vault, demo=False, tool="obsidian")
    (vault / "wikimason.toml").unlink()
    write_default_schema(vault)

    legacy_path = vault / "Schema/wikimason.json"
    legacy_raw = json.loads(legacy_path.read_text(encoding="utf-8"))
    legacy_raw["generated"] = [*legacy_raw.get("generated", []), "Schema/custom.md"]
    legacy_path.write_text(json.dumps(legacy_raw, indent=2) + "\n", encoding="utf-8")

    assert main(["config", "migrate", str(vault)]) == 0

    config = load_config_file(vault / "wikimason.toml")
    schema = load_vault_schema(vault, config=config)
    assert config.profile == "obsidian"
    assert "Schema/custom.md" in schema.generated


def test_cli_doctor_json_shape(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=True)

    assert main(["vault", "doctor", "--vault", str(vault), "--format", "json"]) in {
        0,
        1,
    }

    out = capsys.readouterr().out
    assert '"ok"' in out
    assert '"checks"' in out


def test_catalog_rebuild_writes_generated_docs(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=True)

    assert main(["catalog", "rebuild", "--vault", str(vault)]) == 0

    assert (vault / "Schema/command-reference.md").read_text(
        encoding="utf-8"
    ) == render_command_reference_markdown()
    assert not (vault / "Schema/wikimason-obsidian-commands.md").exists()


def test_catalog_search_accepts_query_option(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=True)
    main(["vault", "build", "--vault", str(vault)])

    assert (
        main(
            [
                "catalog",
                "search",
                "--vault",
                str(vault),
                "--query",
                "compiled knowledge",
                "--format",
                "json",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert payload
