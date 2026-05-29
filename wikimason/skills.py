from __future__ import annotations

import shutil
from pathlib import Path

from .constants import PROJECT_SKILL_PATH


def skill_path(repo_root: Path) -> Path:
    return (repo_root / PROJECT_SKILL_PATH).resolve()


def skill_install(repo_root: Path, target: Path, symlink: bool = False) -> Path:
    src = skill_path(repo_root)
    dest = target / "wikimason"
    dest.mkdir(parents=True, exist_ok=True)
    out = dest / "SKILL.md"
    if out.exists():
        out.unlink()
    if symlink:
        out.symlink_to(src)
    else:
        shutil.copy2(src, out)
    return out
