from __future__ import annotations

import re
from pathlib import Path

TASK_RE = re.compile(r"^(\s*)- \[([ xX\-\?])\] (.*)$")


def list_tasks(text: str) -> list[tuple[int, str, str]]:
    rows: list[tuple[int, str, str]] = []
    for i, line in enumerate(text.splitlines(), start=1):
        m = TASK_RE.match(line)
        if m:
            rows.append((i, m.group(2), m.group(3)))
    return rows


def set_task_status(text: str, line_number: int, status: str) -> str:
    lines = text.splitlines()
    idx = line_number - 1
    if idx < 0 or idx >= len(lines):
        raise ValueError("task line out of range")
    line = lines[idx]
    m = TASK_RE.match(line)
    if not m:
        raise ValueError("line is not a task")
    lines[idx] = f"{m.group(1)}- [{status}] {m.group(3)}"
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def list_task_lines(
    paths: list[Path],
    *,
    status_filter: str | None = None,
    verbose: bool = False,
    vault: Path | None = None,
) -> list[str]:
    rows: list[str] = []
    for path in paths:
        if not path.exists():
            continue
        for line_number, status, text in list_tasks(path.read_text(encoding="utf-8")):
            if status_filter == "todo" and status != " ":
                continue
            if status_filter == "done" and status not in {"x", "X"}:
                continue
            prefix = ""
            if verbose and vault is not None:
                prefix = f"{path.relative_to(vault).as_posix()}:{line_number}: "
            rows.append(f"{prefix}- [{status}] {text}")
    return rows


def write_task_status(path: Path, line_number: int, status: str) -> None:
    text = path.read_text(encoding="utf-8")
    path.write_text(set_task_status(text, line_number, status), encoding="utf-8")
