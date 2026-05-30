from pathlib import Path

from wikimason.commands import (
    render_command_reference_markdown,
    render_skill_markdown,
)
from wikimason.skills import skill_install


def test_skill_install_only_wikimason(tmp_path: Path):
    repo_root = Path(__file__).resolve().parent.parent
    target = tmp_path / "skills"
    out = skill_install(repo_root, target, symlink=False)
    assert out.exists()
    assert out.relative_to(target).as_posix() == "wikimason/SKILL.md"


def test_skill_matches_generated_runbook() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    skill_text = (repo_root / "skills/wikimason/SKILL.md").read_text(encoding="utf-8")

    assert skill_text == render_skill_markdown()
    assert "workflow: wiki-management" in skill_text
    assert "wikimason source delta" in skill_text
    assert "wikimason source read" in skill_text
    assert "wikimason source coverage" in skill_text
    assert "wikimason source lint" in skill_text
    assert "wikimason page update" in skill_text
    assert "wikimason note validate" in skill_text
    assert "wikimason note normalize" in skill_text
    assert "wikimason agents check" in skill_text
    assert "wikimason ingest finish" in skill_text
    assert "wikimason obsidian" not in skill_text
    assert "scripts/wiki_tool.py" in skill_text


def test_generated_command_reference_is_current() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    expected = render_command_reference_markdown()
    actual = (repo_root / "docs/command-reference.md").read_text(encoding="utf-8")
    assert actual == expected


def test_command_reference_includes_catalog_search() -> None:
    from wikimason.commands import render_command_reference_markdown

    text = render_command_reference_markdown()
    assert "catalog search" in text
    assert "QUERY|--query QUERY" in text


def test_command_reference_includes_public_workflow_commands() -> None:
    text = render_command_reference_markdown()
    for phrase in [
        "wikimason init",
        "source scan",
        "source delta",
        "ingest plan",
        "ingest finish",
        "note new",
        "page update",
    ]:
        assert phrase in text


def test_readme_documents_core_workflows() -> None:
    text = Path("README.md").read_text(encoding="utf-8")
    for phrase in [
        "wikimason init markdown",
        "wikimason init obsidian",
        "wikimason init logseq",
        "wikimason source scan",
        "wikimason source delta",
        "wikimason note new",
        "wikimason page update",
        "wikimason ingest finish",
        "wikimason vault maintain",
        "Raw/Sources/",
        "Schema/source-manifest.jsonl",
        "AGENTS.md",
    ]:
        assert phrase in text


def test_docs_index_exposes_main_pages() -> None:
    text = Path("docs/index.rst").read_text(encoding="utf-8")
    for page in [
        "architecture",
        "profiles",
        "config",
        "raw-sources",
        "agent-workflow",
        "commands",
        "command-reference",
        "logseq",
        "migration",
    ]:
        assert page in text


def test_docs_and_scaffold_do_not_reference_removed_maintain_command() -> None:
    checked = [
        "README.md",
        "docs",
        "skills/wikimason/SKILL.md",
        "wikimason/scaffold.py",
        "wikimason/git_hooks.py",
    ]
    offenders = []
    for item in checked:
        path = Path(item)
        files = path.rglob("*") if path.is_dir() else [path]
        for file in files:
            if file.is_file() and file.suffix in {".md", ".rst", ".py"}:
                content = file.read_text(encoding="utf-8")
                has_bare = "wikimason maintain" in content
                has_vault = "wikimason vault maintain" in content
                if has_bare and not has_vault:
                    offenders.append(str(file))
    assert not offenders
