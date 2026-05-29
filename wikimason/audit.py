from __future__ import annotations

import re
from pathlib import Path

SECRET_PATTERNS = [
    re.compile(r"(?i)api[_-]?key\s*[:=]\s*\S+"),
    re.compile(r"(?i)secret\s*[:=]\s*\S+"),
    re.compile(r"(?i)token\s*[:=]\s*\S+"),
]


def audit_vault(vault: Path) -> list[str]:
    findings: list[str] = []
    for p in sorted(vault.rglob("*")):
        if p.is_dir():
            continue
        rel = p.relative_to(vault).as_posix()
        if ".obsidian/workspace" in rel or ".obsidian/cache/" in rel:
            findings.append(f"tracked local obsidian state: {rel}")
            continue
        if (
            p.suffix.lower() in {".png", ".jpg", ".jpeg", ".pdf", ".zip"}
            and "/Wiki/" in rel
        ):
            findings.append(f"binary in text area: {rel}")
            continue
        if p.suffix.lower() in {".md", ".txt", ".json", ".yml", ".yaml"}:
            text = p.read_text(encoding="utf-8", errors="ignore")
            if "/Users/" in text or "C:\\" in text:
                findings.append(f"local path leak: {rel}")
            if ".env" in rel:
                findings.append(f"env file leak: {rel}")
            for pat in SECRET_PATTERNS:
                if pat.search(text):
                    findings.append(f"secret-like pattern in {rel}")
                    break
    return findings
