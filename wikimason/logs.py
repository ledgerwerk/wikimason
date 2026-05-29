from __future__ import annotations

from datetime import date
from pathlib import Path


def append_log(vault: Path, title: str, details: str) -> Path:
    target = vault / "Wiki/log.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    existing = target.read_text(encoding="utf-8") if target.exists() else "# Wiki Log\n"
    block = f"\n## {date.today().isoformat()} - {title}\n\n{details.strip()}\n"
    target.write_text(existing.rstrip() + "\n" + block, encoding="utf-8")
    return target
