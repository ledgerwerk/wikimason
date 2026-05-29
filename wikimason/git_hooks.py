from __future__ import annotations

from pathlib import Path


def install_hooks(vault: Path) -> Path:
    hooks = vault / ".githooks"
    hooks.mkdir(parents=True, exist_ok=True)
    pre = hooks / "pre-commit"
    pre.write_text("#!/usr/bin/env bash\nwikimason maintain\n", encoding="utf-8")
    return pre
