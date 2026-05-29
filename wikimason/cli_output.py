from __future__ import annotations

import json


def emit(payload: object, text: str, fmt: str, *, exit_code: int = 0) -> int:
    if fmt == "json":
        print(json.dumps(payload, sort_keys=True))
    else:
        print(text)
    return exit_code


def print_findings_payload(
    payload: dict[str, object], *, success_text: str, fmt: str
) -> int:
    exit_code = 0 if payload["ok"] else 1
    if fmt == "json":
        print(json.dumps(payload, sort_keys=True))
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
