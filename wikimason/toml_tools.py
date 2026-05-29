"""Centralized TOML serialization helpers."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def toml_bool(value: bool) -> str:
    return "true" if value else "false"


def toml_string_array(values: Iterable[str]) -> str:
    return "[" + ", ".join(toml_string(v) for v in values) + "]"


def toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return toml_bool(value)
    if isinstance(value, str):
        return toml_string(value)
    if isinstance(value, (list, tuple)) and all(
        isinstance(item, str) for item in value
    ):
        return toml_string_array(value)
    raise ValueError(f"unsupported TOML value: {value!r}")
