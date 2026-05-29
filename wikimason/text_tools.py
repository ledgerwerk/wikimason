from __future__ import annotations

import json


def wordcount(text: str) -> dict[str, int]:
    words = len([word for word in text.replace("\n", " ").split(" ") if word])
    return {"words": words, "characters": len(text)}


def outline(text: str) -> tuple[list[str], list[dict[str, object]]]:
    lines: list[str] = []
    payload: list[dict[str, object]] = []
    for index, line in enumerate(text.splitlines(), start=1):
        if not line.startswith("#"):
            continue
        level = len(line) - len(line.lstrip("#"))
        title = line[level:].strip()
        lines.append(f"{'  ' * (level - 1)}- {title}")
        payload.append({"line": index, "level": level, "title": title})
    return lines, payload


def outline_json(text: str) -> str:
    _, payload = outline(text)
    return json.dumps(payload, sort_keys=True)
