try:
    import tomllib
except ImportError:
    import tomli as tomllib
from pathlib import Path

from wikimason.cli import main
from wikimason.scaffold import init_vault


def test_runtime_dependencies_declared():
    data = tomllib.loads(Path("pyproject.toml").read_text())
    deps = set(data["project"]["dependencies"])
    assert "typer" in deps
    assert "click" in deps
    assert "PyYAML" in deps
    assert "rapidfuzz" in deps
    assert "fuzzysearch" in deps


def test_typer_help_root(capsys):
    assert main(["--help"]) == 0
    out = capsys.readouterr().out
    assert "Usage:" in out
    assert "source" in out
    assert "--config" in out


def test_typer_help_nested(capsys):
    assert main(["source", "verify", "--help"]) == 0
    out = capsys.readouterr().out
    assert "verify" in out
    assert "--format" in out


def test_legacy_help_topic(capsys):
    assert main(["help", "source", "verify"]) == 0
    assert "verify" in capsys.readouterr().out


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
    assert payload["matches"]
    assert any("wikimason-demo-source" in str(m["path"]) for m in payload["matches"])


def test_fuzzysearch_snippet_only_on_candidate_text():
    from wikimason.search import approximate_snippets

    text = "Run wikimason init obsidian before ingest."
    rows = approximate_snippets("wikimason init obsdian", text)
    assert rows
    assert rows[0][2] <= 2


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
    help_out = capsys.readouterr().out

    # All top-level command groups should appear in help
    top_groups = sorted({s.path[0] for s in COMMAND_SPECS})
    for group in top_groups:
        assert group in help_out, f"Command group '{group}' missing from --help"
