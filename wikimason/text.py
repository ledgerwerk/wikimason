from __future__ import annotations

import json


def decode_escapes(value: str) -> str:
    return value.replace("\\n", "\n").replace("\\t", "\t")


def parse_bool(value: str) -> bool:
    return value.lower() in {"1", "true", "yes", "on"}


def parse_number_or_text(value: str) -> object:
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def parse_list_or_json(value: str) -> list[str]:
    raw = value.strip()
    if raw.startswith("[") and raw.endswith("]"):
        parsed = parse_json_list_or_none(value)
        if parsed is not None:
            return parsed
    return [v.strip() for v in value.split(",") if v.strip()]


def parse_json_list_or_none(value: str) -> list[str] | None:
    raw = value.strip()
    if not (raw.startswith("[") and raw.endswith("]")):
        return None
    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        raise ValueError("expected JSON array")
    return [str(v) for v in parsed]
