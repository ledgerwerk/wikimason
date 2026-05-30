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


SCHEMA_VERSION = 1


def result_payload(
    *,
    command: str,
    status: str,
    data: object,
    exit_code: int = 0,
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
    next_action: str | None = None,
) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": exit_code == 0,
        "command": command,
        "status": status,
        "exit_code": exit_code,
        "data": data,
        "errors": errors or [],
        "warnings": warnings or [],
        "next_action": next_action,
    }


def emit(
    payload: object,
    text: str,
    fmt: str | OutputFormat,
    *,
    exit_code: int = 0,
    command: str | None = None,
    status: str | None = None,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
    next_action: str | None = None,
) -> int:
    normalized = normalize_format(fmt)
    if normalized is OutputFormat.json:
        # Wrap raw payloads in the standard envelope.
        if command is not None and not isinstance(payload, dict):
            payload = emit_json_envelope(
                command=command,
                data=payload,
                exit_code=exit_code,
                status=status,
                warnings=warnings,
                errors=errors,
                next_action=next_action,
            )
        elif (
            command is not None
            and isinstance(payload, dict)
            and "schema_version" not in payload
        ):
            payload = emit_json_envelope(
                command=command,
                data=payload,
                exit_code=exit_code,
                status=status,
                warnings=warnings,
                errors=errors,
                next_action=next_action,
            )
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


def emit_json_envelope(
    *,
    command: str,
    data: object,
    exit_code: int = 0,
    status: str | None = None,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
    next_action: str | None = None,
) -> dict[str, object]:
    """Build a standard JSON envelope for agent-facing output."""
    status_value = status or ("clean" if exit_code == 0 else "error")
    return {
        "schema_version": SCHEMA_VERSION,
        "command": command,
        "ok": exit_code == 0,
        "status": status_value,
        "exit_code": exit_code,
        "data": data,
        "warnings": warnings or [],
        "errors": errors or [],
        "next_action": next_action,
    }
