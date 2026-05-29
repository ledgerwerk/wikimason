from __future__ import annotations

import re

_CREDENTIAL_PATTERNS: list[re.Pattern] = [
    re.compile(r"token[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"password[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"secret[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"api[_-]?key[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"api[_-]?secret[:=]\s*\S+", re.IGNORECASE),
]


def check_credentials(text: str, rel: str, findings: list) -> None:
    """Scan *text* for potential credential leaks."""
    from .lint import LintFinding

    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("<!--"):
            continue
        for pattern in _CREDENTIAL_PATTERNS:
            if pattern.search(stripped):
                findings.append(
                    LintFinding(
                        path=rel,
                        line=line_number,
                        code="credential_leak",
                        message=f"potential credential leak: {pattern.pattern}",
                    )
                )
                break
