import builtins
import importlib
import sys
from pathlib import Path

import pytest

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from conftest import _strip_ansi

from wikimason.cli import main
from wikimason.scaffold import init_vault


def test_runtime_dependencies_declared():
    data = tomllib.loads(Path("pyproject.toml").read_text())
    deps = set(data["project"]["dependencies"])
    assert "ledgercore>=0.2.0,<0.3.0" in deps
    assert "typer" in deps
    assert "click" in deps
    # PyYAML is provided transitively via ledgercore; WikiMason no longer
    # imports yaml directly after the front matter facade migration.
    assert "PyYAML" not in deps
    assert "rapidfuzz" in deps
    assert "fuzzysearch" in deps


def test_typer_help_root(capsys):
    assert main(["--help"]) == 0
    out = _strip_ansi(capsys.readouterr().out)
    assert "Usage:" in out
    assert "source" in out
    assert "--config" in out


def test_typer_help_nested(capsys):
    assert main(["source", "verify", "--help"]) == 0
    out = _strip_ansi(capsys.readouterr().out)
    assert "verify" in out
    assert "--format" in out


def test_help_topic_for_nested_command(capsys):
    assert main(["help", "source", "verify"]) == 0
    assert "verify" in _strip_ansi(capsys.readouterr().out)


def test_unknown_command_suggests(capsys):
    assert main(["srouce"]) == 2
    err = capsys.readouterr().err + capsys.readouterr().out
    assert "source" in err.lower()


def test_source_resolve_typo_uses_rapidfuzz(tmp_path: Path, capsys):
    vault = tmp_path / "vault"
    init_vault(vault, demo=True)

    result = main(
        [
            "source",
            "resolve",
            "wikimason demo sorce",
            "--vault",
            str(vault),
            "--format",
            "json",
        ]
    )
    assert result == 0
    payload = __import__("json").loads(capsys.readouterr().out.splitlines()[-1])
    assert payload["data"]["matches"]
    assert any(
        "wikimason-demo-source" in str(m["path"]) for m in payload["data"]["matches"]
    )


def test_fuzzysearch_snippet_only_on_candidate_text():
    from wikimason.search import approximate_snippets

    text = "Run wikimason init obsidian before ingest."
    rows = approximate_snippets("wikimason init obsdian", text)
    assert rows
    assert rows[0][2] <= 2


def test_search_module_imports_without_fuzzysearch(monkeypatch):
    real_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "fuzzysearch" or name.startswith("fuzzysearch."):
            raise ModuleNotFoundError("No module named 'fuzzysearch'")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    sys.modules.pop("fuzzysearch", None)
    sys.modules.pop("wikimason.search", None)
    sys.modules.pop("wikimason.cli_app", None)
    sys.modules.pop("wikimason.cli", None)

    cli_module = importlib.import_module("wikimason.cli")
    assert hasattr(cli_module, "main")

    search = importlib.import_module("wikimason.search")
    from wikimason.errors import UsageError

    with pytest.raises(
        UsageError,
        match="fuzzy snippet search requires the fuzzysearch package",
    ):
        search.approximate_snippets(
            "wikimason init obsdian",
            "Run wikimason init obsidian before ingest.",
        )


def test_frontmatter_yaml_preserves_dates_as_strings():
    from wikimason.frontmatter import split_frontmatter

    data, body = split_frontmatter(
        "---\ncreated: 2026-05-29\naliases:\n  - Demo\n---\nBody"
    )
    assert data["created"] == "2026-05-29"
    assert data["aliases"] == ["Demo"]


def test_frontmatter_no_python_tags():
    from wikimason.frontmatter import render_frontmatter

    rendered = render_frontmatter({"title": "Test", "count": 42})
    assert "!!python" not in rendered
    assert "count: 42" in rendered


def test_search_rank_candidates():
    from wikimason.search import SearchCandidate, rank_candidates

    candidates = [
        SearchCandidate(
            key="a", kind="page", label="Getting Started", path="getting-started.md"
        ),
        SearchCandidate(key="b", kind="page", label="API Reference", path="api.md"),
        SearchCandidate(key="c", kind="page", label="Configuration", path="config.md"),
    ]
    results = rank_candidates("geting started", candidates, cutoff=50.0)
    assert results
    assert results[0].candidate.key == "a"


def test_normalize_query():
    from wikimason.search import normalize_query

    assert normalize_query("Hello/World\\Foo") == "hello/world/foo"
    assert "  " not in normalize_query("hello   world")


def test_command_specs_is_single_source_of_truth():
    """command_specs.COMMAND_SPECS is the only command metadata source."""
    from wikimason.command_registry import COMMAND_REGISTRY
    from wikimason.command_specs import COMMAND_SPECS, CommandSpec
    from wikimason.commands import COMMAND_SPECS as CMDS
    from wikimason.commands import CommandSpec as CmdSpec

    # commands.py imports from command_specs.py
    assert CmdSpec is CommandSpec
    assert CMDS is COMMAND_SPECS

    # command_registry derives from command_specs
    assert len(COMMAND_REGISTRY) >= len(COMMAND_SPECS)

    # No separate MAIN_COMMANDS list in commands.py
    import wikimason.commands as commands_mod

    assert not hasattr(commands_mod, "MAIN_COMMANDS"), (
        "commands.py must not define MAIN_COMMANDS"
    )


def test_runtime_commands_match_specs(capsys):
    """Every command in COMMAND_SPECS exists in runtime CLI help."""
    from wikimason.cli import main
    from wikimason.command_specs import COMMAND_SPECS

    assert main(["--help"]) == 0
    help_out = _strip_ansi(capsys.readouterr().out)

    # All top-level command groups should appear in help
    top_groups = sorted({s.path[0] for s in COMMAND_SPECS})
    for group in top_groups:
        assert group in help_out, f"Command group '{group}' missing from --help"


def test_visible_typer_commands_have_command_specs() -> None:
    import click
    import typer

    from wikimason.cli_app import app
    from wikimason.command_specs import COMMAND_SPECS

    root = typer.main.get_command(app)
    actual: set[tuple[str, ...]] = set()

    for name, command in root.commands.items():
        if getattr(command, "hidden", False):
            continue
        if isinstance(command, click.Group):
            if getattr(command, "invoke_without_command", False):
                actual.add((name,))
            for sub_name, sub_command in command.commands.items():
                if not getattr(sub_command, "hidden", False):
                    actual.add((name, sub_name))
        else:
            actual.add((name,))

    spec_paths = {spec.path for spec in COMMAND_SPECS if not spec.hidden}
    undocumented = actual - spec_paths
    assert not undocumented


def test_frontmatter_facade_matches_current_spacing():
    from wikimason.frontmatter import update_frontmatter

    text = "---\ntitle: T\n---\n\nBody\n"
    assert update_frontmatter(text, {"x": "y"}) == "---\ntitle: T\nx: y\n---\n\nBody\n"


def test_frontmatter_facade_preserves_dates_as_strings():
    from wikimason.frontmatter import split_frontmatter

    data, _ = split_frontmatter("---\ncreated: 2026-01-01\n---\nBody\n")
    assert data["created"] == "2026-01-01"


def test_frontmatter_facade_quotes_mustache_anywhere():
    from wikimason.frontmatter import split_frontmatter

    data, _ = split_frontmatter("---\ntitle: prefix {{ name }} suffix\n---\nBody\n")
    assert data["title"] == "prefix {{ name }} suffix"


def test_frontmatter_facade_missing_returns_original():
    from wikimason.frontmatter import split_frontmatter

    data, body = split_frontmatter("no front matter here\n")
    assert data == {}
    assert body == "no front matter here\n"
