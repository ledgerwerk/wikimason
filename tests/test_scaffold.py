import json
from pathlib import Path

import pytest

from wikimason.scaffold import init_vault


def test_init_demo_creates_core_layout(tmp_path: Path):
    vault = tmp_path / "vault"
    init_vault(vault, demo=True)
    assert (vault / "Raw/Sources/wikimason-demo-source.md").exists()
    assert (vault / "Wiki/Concepts/compiled-knowledge.md").exists()
    assert (vault / "_templates/concept-note.md").exists()
    assert (vault / "wikimason.toml").exists()
    assert not (vault / "Schema/wikimason.json").exists()


@pytest.mark.parametrize(
    ("tool", "expected_prefix"),
    [
        ("obsidian", "[[Wiki/Topics/index|Topics]]"),
        ("markdown", "[[Wiki/Topics/index|Topics]]"),
    ],
)
def test_init_writes_starter_shape_placeholders(
    tmp_path: Path, tool: str, expected_prefix: str
) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=False, tool=tool)

    for rel in [
        "Raw/Sources/.gitkeep",
        "Raw/Files/.gitkeep",
        "Schema/source-manifest.jsonl",
        "Wiki/catalog.jsonl",
        "Wiki/index.md",
        "Wiki/log.md",
        "Wiki/Topics/.gitkeep",
        "Wiki/Topics/index.md",
        "Wiki/Concepts/.gitkeep",
        "Wiki/Concepts/index.md",
        "Wiki/Entities/.gitkeep",
        "Wiki/Entities/index.md",
        "Wiki/Projects/.gitkeep",
        "Wiki/Projects/index.md",
        "Wiki/Logs/.gitkeep",
        "Wiki/Logs/index.md",
        "_templates/.gitkeep",
        "wikimason.toml",
    ]:
        assert (vault / rel).exists(), rel

    assert (vault / "Schema/source-manifest.jsonl").read_text(encoding="utf-8") == ""
    assert (vault / "Wiki/catalog.jsonl").read_text(encoding="utf-8") == ""
    assert (vault / "Wiki/log.md").read_text(encoding="utf-8") == "# Wiki Log\n"
    assert not (vault / "Schema/wikimason.json").exists()

    top_index = (vault / "Wiki/index.md").read_text(encoding="utf-8")
    assert expected_prefix in top_index


def test_demo_init_prebuilds_catalog_indexes_and_manifest(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=True)

    assert (vault / "Wiki/catalog.jsonl").read_text(encoding="utf-8").strip()
    assert (vault / "Wiki/index.md").exists()
    assert (vault / "Wiki/Topics/index.md").exists()
    assert (vault / "Wiki/Concepts/index.md").exists()

    rows = [
        json.loads(line)
        for line in (vault / "Schema/source-manifest.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    assert rows
    assert rows[0]["coverage_status"] in {"covered", "missing"}


def test_init_does_not_overwrite_existing_log(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / "Wiki").mkdir(parents=True)
    (vault / "Wiki/log.md").write_text("# Custom Log\n\nKeep me.\n", encoding="utf-8")

    init_vault(vault, demo=False)

    assert "Keep me." in (vault / "Wiki/log.md").read_text(encoding="utf-8")


def test_init_markdown_skips_obsidian_state(tmp_path: Path) -> None:
    vault = tmp_path / "vault"

    init_vault(vault, tool="markdown")

    assert not (vault / ".obsidian").exists()
    assert 'profile = "markdown"' in (vault / "wikimason.toml").read_text(
        encoding="utf-8"
    )
    assert not (vault / "Schema/wikimason-obsidian-commands.md").exists()
