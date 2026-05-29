from pathlib import Path

from wikimason.build import build_vault
from wikimason.lint import lint_vault
from wikimason.scaffold import init_vault
from wikimason.search import search_catalog
from wikimason.sources import source_coverage, source_scan


def test_lint_and_search_catalog(tmp_path: Path):
    vault = tmp_path / "vault"
    init_vault(vault, demo=True)
    build_vault(vault)
    errors = lint_vault(vault, strict=False)
    assert errors == []
    hits = search_catalog(vault, "compiled knowledge", limit=10)
    assert hits
    assert hits[0]["title"] == "Compiled Knowledge"


def test_source_coverage(tmp_path: Path):
    vault = tmp_path / "vault"
    init_vault(vault, demo=True)
    source_scan(vault, update=True, accept_covered=True)
    covered, total = source_coverage(vault)
    assert total >= 1
    assert covered >= 1
