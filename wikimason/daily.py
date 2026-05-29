from __future__ import annotations

from datetime import date
from pathlib import Path

from .files import append_file, prepend_file, read_file


def daily_note_path(vault: Path, day: date | None = None) -> Path:
    active_day = day or date.today()
    return vault / f"{active_day.isoformat()}.md"


def ensure_daily_note(vault: Path, day: date | None = None) -> Path:
    path = daily_note_path(vault, day)
    if not path.exists():
        path.write_text(f"# {(day or date.today()).isoformat()}\n", encoding="utf-8")
    return path


def read_daily(vault: Path, day: date | None = None) -> str:
    path = ensure_daily_note(vault, day)
    return read_file(vault, path.relative_to(vault).as_posix())


def append_daily(vault: Path, content: str, day: date | None = None) -> Path:
    path = ensure_daily_note(vault, day)
    return append_file(vault, path.relative_to(vault).as_posix(), content)


def prepend_daily(vault: Path, content: str, day: date | None = None) -> Path:
    path = ensure_daily_note(vault, day)
    return prepend_file(vault, path.relative_to(vault).as_posix(), content)
