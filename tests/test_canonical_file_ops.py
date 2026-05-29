from datetime import date
from pathlib import Path

from wikimason.cli import main
from wikimason.scaffold import init_vault


def run_cli(vault: Path, *argv: str) -> int:
    return main(["--vault", str(vault), *argv])


def test_file_write_read_append_and_search(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=True)

    assert run_cli(vault, "file", "write", "Scratch.md", "--content", "# Scratch") == 0
    assert (
        run_cli(vault, "file", "append", "Scratch.md", "--content", "- [ ] Follow up")
        == 0
    )
    assert run_cli(vault, "file", "read", "Scratch.md") == 0
    assert "Follow up" in capsys.readouterr().out
    assert run_cli(vault, "file", "search", "--query", "Scratch") == 0


def test_daily_property_task_and_tag_commands(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=True)

    assert (
        run_cli(vault, "daily", "append", "--content", "- [ ] Daily item #project") == 0
    )
    daily_rel = f"{date.today().isoformat()}.md"
    assert run_cli(vault, "property", "set", "Welcome.md", "status", "draft") == 0
    assert run_cli(vault, "property", "get", "Welcome.md", "status") == 0
    assert "draft" in capsys.readouterr().out
    assert run_cli(vault, "task", "list", "--daily", "--verbose") == 0
    lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert lines
    line_no = int(lines[0].split(":", 2)[1])
    assert run_cli(vault, "task", "toggle", daily_rel, str(line_no)) == 0
    assert run_cli(vault, "tag", "list", "--counts") == 0
    assert "#project" in capsys.readouterr().out


def test_template_text_and_links_commands(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=True)

    assert run_cli(vault, "template", "list") == 0
    assert "topic-note" in capsys.readouterr().out
    assert run_cli(vault, "text", "outline", "Welcome.md") == 0
    assert "Welcome" in capsys.readouterr().out
    assert (
        run_cli(
            vault,
            "file",
            "write",
            "Link Note.md",
            "--content",
            "# Link Note\n\n[[Welcome]]\n",
        )
        == 0
    )
    assert run_cli(vault, "links", "outgoing", "Link Note.md") == 0
    assert "Welcome" in capsys.readouterr().out
    assert run_cli(vault, "links", "backlinks", "Welcome.md") == 0
    assert "Link Note.md" in capsys.readouterr().out


def test_page_update_body_file_preserves_sources(tmp_path: Path, capsys) -> None:
    from conftest import write_source_rel

    from wikimason.frontmatter import split_frontmatter

    vault = tmp_path / "vault"
    init_vault(vault)
    source_rel = write_source_rel(vault, "Agent Skills \u2013 O'Reilly.md")
    main([
        "note",
        "new",
        "--vault",
        str(vault),
        "--kind",
        "topic",
        "--title",
        "Agent Skills",
        "--source",
        source_rel,
        "--allow-incomplete",
    ])
    body = tmp_path / "body.md"
    body.write_text("# Agent Skills\n\nNew body\n", encoding="utf-8")

    assert main([
        "page",
        "update",
        "Wiki/Topics/agent-skills.md",
        "--vault",
        str(vault),
        "--body-file",
        str(body),
        "--format",
        "json",
    ]) == 0

    data, body_text = split_frontmatter(
        (vault / "Wiki/Topics/agent-skills.md").read_text(encoding="utf-8")
    )
    assert data["sources"] == [source_rel]
    assert "New body" in body_text
