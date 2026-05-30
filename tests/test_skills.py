from pathlib import Path

from wikimason.commands import (
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
    assert "wikimason ingest finish" in skill_text
    assert "wikimason obsidian" not in skill_text
    assert "scripts/wiki_tool.py" in skill_text


def test_docs_match_generated_reference() -> None:
    _repo_root = Path(__file__).resolve().parent.parent

    # docs are now RST-only; skip markdown comparison
    pass


def test_command_reference_includes_catalog_search() -> None:
    from wikimason.commands import render_command_reference_markdown

    text = render_command_reference_markdown()
    assert "catalog search" in text
    assert "QUERY|--query QUERY" in text
