"""Test vault maintain command — the single post-run gate for agents."""

from __future__ import annotations

from pathlib import Path

from conftest import read_json, write_source

from wikimason.build import build_vault
from wikimason.cli import main
from wikimason.scaffold import init_vault


def test_vault_maintain_clean_vault(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    init_vault(vault, demo=True)
    build_vault(vault)

    assert (
        main(
            [
                "vault",
                "maintain",
                "--vault",
                str(vault),
                "--format",
                "json",
            ]
        )
        == 0
    )

    payload = read_json(capsys)
    data = payload["data"]
    assert payload["ok"] is True
    assert data["doctor_ok"] is True
    assert data["lint_ok"] is True
    assert data["source_lint_ok"] is True
    assert data["links_ok"] is True
    assert data["agents_ok"] is True
    assert "sources" in data
    assert "coverage_percent" in data["sources"]
    assert "catalog_count" in data
    assert payload["next_action"] == "maintain_clean_vault"


def test_vault_maintain_with_accept_covered(tmp_path: Path, capsys) -> None:
    """Test vault maintain --accept-covered after note creation."""
    vault = tmp_path / "vault"
    init_vault(vault)
    write_source(vault, "foo")

    # Create note covering the source
    assert (
        main(
            [
                "note",
                "new",
                "--vault",
                str(vault),
                "--kind",
                "topic",
                "--title",
                "Foo",
                "--source",
                "Raw/Sources/foo.md",
                "--allow-incomplete",
                "--format",
                "json",
            ]
        )
        == 0
    )

    # Run maintain with --accept-covered
    assert (
        main(
            [
                "vault",
                "maintain",
                "--accept-covered",
                "--vault",
                str(vault),
                "--format",
                "json",
            ]
        )
        == 0
    )

    payload = read_json(capsys)
    data = payload["data"]
    assert payload["ok"] is True
    assert data["sources"]["total"] == 1
    assert data["sources"]["covered"] == 1
    assert data["sources"]["coverage_percent"] == 100.0
    assert data["sources"]["actionable_count"] == 0


def test_vault_maintain_acceptance_scenario(tmp_path: Path, capsys) -> None:
    """End-to-end acceptance: create vault, add source, create notes, maintain."""
    vault = tmp_path / "vault"
    init_vault(vault)
    write_source(vault, "test-source", title="Test Source")

    # Create topic + concept + log notes
    for kind, title in [
        ("topic", "Test Source"),
        ("concept", "Test Source Concept"),
        ("log", "Initial Test Source Ingest"),
    ]:
        argv = [
            "note",
            "new",
            "--vault",
            str(vault),
            "--kind",
            kind,
            "--title",
            title,
            "--source",
            "Raw/Sources/test-source.md",
            "--allow-incomplete",
        ]
        assert main(argv) == 0

    # Run full maintain
    assert (
        main(
            [
                "vault",
                "maintain",
                "--accept-covered",
                "--vault",
                str(vault),
                "--format",
                "json",
            ]
        )
        == 0
    )

    payload = read_json(capsys)
    data = payload["data"]
    assert payload["ok"] is True
    assert data["sources"]["coverage_percent"] == 100.0
    assert data["sources"]["actionable_count"] == 0

    # Verify status
    assert main(["status", "--vault", str(vault), "--format", "json"]) == 0
    status = read_json(capsys)
    assert status["data"]["next_action"] == "maintain_clean_vault"
