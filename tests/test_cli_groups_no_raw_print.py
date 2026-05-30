from __future__ import annotations

from pathlib import Path

ALLOWED_RAW_PRINT_GROUPS = {
    "wikimason/cli_groups/root.py",
}


def test_cli_groups_do_not_use_raw_print_outside_whitelist() -> None:
    offenders: list[str] = []
    for path in sorted(Path("wikimason/cli_groups").glob("*.py")):
        posix = path.as_posix()
        if posix in ALLOWED_RAW_PRINT_GROUPS:
            continue
        if "print(" in path.read_text(encoding="utf-8"):
            offenders.append(posix)

    assert not offenders, "raw print() found in cli_groups: " + ", ".join(offenders)
