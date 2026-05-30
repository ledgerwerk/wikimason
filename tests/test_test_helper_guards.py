from __future__ import annotations

import ast
from pathlib import Path


DUPLICATE_HELPER_NAMES = {"_strip_ansi", "write_source", "read_json"}


def test_no_duplicate_test_helper_definitions_outside_conftest() -> None:
    offenders: list[str] = []
    for path in sorted(Path("tests").glob("test_*.py")):
        module = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
        for node in ast.walk(module):
            if isinstance(node, ast.FunctionDef) and node.name in DUPLICATE_HELPER_NAMES:
                offenders.append(f"{path.as_posix()} defines {node.name}")

    assert not offenders, "duplicate test helpers must live in tests/conftest.py: " + ", ".join(
        offenders
    )
