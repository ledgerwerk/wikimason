from __future__ import annotations

from pathlib import Path

from wikimason.build import build_vault
from wikimason.cli import main
from wikimason.scaffold import init_vault


def test_agents_compiled_from_schema_policy(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)
    (vault / "Schema/policy.md").write_text(
        "# Policy\n\n- Custom hard rule.\n",
        encoding="utf-8",
    )

    build_vault(vault)

    assert "Custom hard rule" in (vault / "AGENTS.md").read_text(encoding="utf-8")


def test_agents_compile_check_detects_stale_file(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)
    (vault / "AGENTS.md").write_text("stale", encoding="utf-8")

    assert main(["agents", "compile", "--vault", str(vault), "--check"]) == 1


def test_agents_compile_preserves_manual_block(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault)
    (vault / "AGENTS.md").write_text(
        "<!-- wikimason:manual:start -->\nLocal note.\n<!-- wikimason:manual:end -->\n",
        encoding="utf-8",
    )

    build_vault(vault)

    assert "Local note." in (vault / "AGENTS.md").read_text(encoding="utf-8")


def test_agents_compile_mentions_markdown_tool_profile(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, tool="markdown")

    build_vault(vault)

    agents_text = (vault / "AGENTS.md").read_text(encoding="utf-8")
    assert "Profile: `markdown`" in agents_text
    assert "Profile Reference" in agents_text
    assert (
        "Generic Markdown wiki with YAML frontmatter and nested directories."
        in agents_text
    )
