from __future__ import annotations

import json
from enum import Enum
from typing import Any

from .errors import UsageError


class OutputFormat(str, Enum):
    text = "text"
    json = "json"


def normalize_format(fmt: str | OutputFormat) -> OutputFormat:
    if isinstance(fmt, OutputFormat):
        return fmt
    try:
        return OutputFormat(str(fmt))
    except ValueError as exc:
        raise UsageError("--format must be one of: text, json") from exc


def result_payload(
    *,
    command: str,
    status: str,
    data: object,
    exit_code: int = 0,
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, object]:
    return {
        "ok": exit_code == 0,
        "command": command,
        "status": status,
        "exit_code": exit_code,
        "data": data,
        "errors": errors or [],
        "warnings": warnings or [],
    }


def emit(
    payload: object,
    text: str,
    fmt: str | OutputFormat,
    *,
    exit_code: int = 0,
) -> int:
    normalized = normalize_format(fmt)
    if normalized is OutputFormat.json:
        print(json.dumps(payload, sort_keys=True))
    else:
        print(text)
    return exit_code


def print_findings_payload(
    payload: dict[str, Any], *, success_text: str, fmt: str, command: str
) -> int:
    exit_code = 0 if payload["ok"] else 1
    if normalize_format(fmt) is OutputFormat.json:
        findings = payload["findings"]
        status = "clean" if not findings and exit_code == 0 else "invalid"
        wrapped = result_payload(
            command=command,
            status=status,
            data=payload,
            exit_code=exit_code,
        )
        print(json.dumps(wrapped, sort_keys=True))
    else:
        findings = payload["findings"]
        if findings:
            for finding in findings:
                prefix = (
                    f"{finding['path']}:{finding['line']}"
                    if finding["line"]
                    else finding["path"]
                )
                line = f"{prefix}: {finding['message']}"
                if finding["suggestion"]:
                    line += f" (suggestion: {finding['suggestion']})"
                print(line)
        else:
            print(success_text)
    return exit_code
